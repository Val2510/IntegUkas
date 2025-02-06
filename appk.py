
from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import base64

app = Flask(__name__)

# 🔹 Настройки AmoCRM
AMO_DOMAIN = "fitarena.amocrm.ru"  # ← Измените на ваш домен AmoCRM
AMO_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjAwZjU4YTBlMzFkMmRkNTA5ZjI2ZmNlMGFjNTc5YjZlMDM3YjUwMGQ4Nzg4YzcwOWFkYzVhYzM0ZTFjNjFjNTQ4MjI5YzU3MzliMTZkZjMyIn0.eyJhdWQiOiI0NmMzODZhMi1jYzQ2LTQxNDgtOGU2YS0xOThkZmY0YmNkNjYiLCJqdGkiOiIwMGY1OGEwZTMxZDJkZDUwOWYyNmZjZTBhYzU3OWI2ZTAzN2I1MDBkODc4OGM3MDlhZGM1YWMzNGUxYzYxYzU0ODIyOWM1NzM5YjE2ZGYzMiIsImlhdCI6MTczODgzODY2OCwibmJmIjoxNzM4ODM4NjY4LCJleHAiOjE4OTYwNDgwMDAsInN1YiI6IjMzMjg1MTkiLCJncmFudF90eXBlIjoiIiwiYWNjb3VudF9pZCI6MjUxOTkwMjksImJhc2VfZG9tYWluIjoiYW1vY3JtLnJ1IiwidmVyc2lvbiI6Miwic2NvcGVzIjpbImNybSIsImZpbGVzIiwiZmlsZXNfZGVsZXRlIiwibm90aWZpY2F0aW9ucyIsInB1c2hfbm90aWZpY2F0aW9ucyJdLCJoYXNoX3V1aWQiOiIyY2JjZjIwMC0xNmEyLTRiZWQtYjdhNy1iZjc5ZjczM2M5ZjUiLCJhcGlfZG9tYWluIjoiYXBpLWIuYW1vY3JtLnJ1In0.B0elZrHP_aclPIYfOLOuO8VA8XHJQRf7Ras6W2b58Yg1V5TZMalm0EvdqKDx-Ygb8onU8JAbThzCGOaz_JD7eheimbKQHNXtB-IArAFxSNc4KEkgMtpP-HphUCVhsLi2_0STYZItSBHlyIoqjlR8wdls_ZbUiJ9kmUnXk5Qcfx6KUXbKcuGL7oQPB_ywvliR1c1-HWnrHtg-8mlkqIR3g64_ZFhgR0z4IDLP0SABljLsl6jjD5P3Lu9ua3efBC7TrGy7e8XNegbKNscdvViB4oVuDSRO-u0zJf0AsSsrt0d17bwNdEtQhgIoljUnhBzZGj_z9F0iAj2nSOplpBQZ9Q"  # ← Укажите актуальный токен API
PAYMENT_STATUS_FIELD_ID = 704249  # ← ID поля "Статус оплаты" в AmoCRM

# 🔹 Настройки ЮKassa
YOOKASSA_SECRET_KEY = "live_fiBWt7qk-rZFAr3utLXCLZ3Uc-nTDBYZjiMBUPV-Qp8"  # ← секретный ключ

# ✅ Функция проверки подлинности вебхуков ЮKassa
def verify_yookassa_signature(request):
    signature = request.headers.get("X-Content-HMAC")
    if not signature:
        return False

    body = request.data
    hmac_obj = hmac.new(YOOKASSA_SECRET_KEY.encode(), body, hashlib.sha256)
    expected_signature = base64.b64encode(hmac_obj.digest()).decode()

    return hmac.compare_digest(signature, expected_signature)

# ✅ Функция поиска лида по `order_id` в AmoCRM
def find_lead_by_order_id(order_id):
    url = f"https://{AMO_DOMAIN}/api/v4/leads"
    headers = {"Authorization": f"Bearer {AMO_ACCESS_TOKEN}"}
    
    params = {"query": order_id}  # Поиск по order_id
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200 and response.json().get('_embedded'):
        leads = response.json()['_embedded']['leads']
        return leads[0] if leads else None  

    return None

# ✅ Функция обновления поля "Статус оплаты" в AmoCRM
def update_lead_payment_status(lead_id, payment_status):
    url = f"https://{AMO_DOMAIN}/api/v4/leads/{lead_id}"
    headers = {
        "Authorization": f"Bearer {AMO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    new_status = "Оплачено" if payment_status == "succeeded" else "Не оплачено"

    data = {
        "custom_fields_values": [
            {
                "field_id": PAYMENT_STATUS_FIELD_ID,
                "values": [{"value": new_status}]
            }
        ]
    }

    response = requests.patch(url, headers=headers, json=data)
    return response.status_code == 200  

# ✅ Обработчик вебхуков от ЮKassa
@app.route("/payment_status", methods=["POST"])
def payment_status():
    try:
        # Проверка подлинности вебхука
        if not verify_yookassa_signature(request):
            return jsonify({"error": "Invalid signature"}), 403

        data = request.json
        order_id = data.get("object", {}).get("metadata", {}).get("order_id")
        status = data.get("object", {}).get("status")  # "succeeded" или "canceled"

        if not order_id or not status:
            return jsonify({"error": "Missing order_id or status"}), 400

        lead = find_lead_by_order_id(order_id)

        if not lead:
            return jsonify({"error": "Lead not found"}), 404

        lead_id = lead["id"]

        if update_lead_payment_status(lead_id, status):
            return jsonify({"success": f"Payment status updated in lead {lead_id}"}), 200
        else:
            return jsonify({"error": "Failed to update payment status"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



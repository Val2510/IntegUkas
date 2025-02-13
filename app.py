from flask import Flask, request, jsonify
import requests
import logging
import threading
import time
from yookassa import Configuration, Payment

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# 🔹 Настройки AmoCRM
AMO_DOMAIN = "fitarena.amocrm.ru"
AMO_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjAwZjU4YTBlMzFkMmRkNTA5ZjI2ZmNlMGFjNTc5YjZlMDM3YjUwMGQ4Nzg4YzcwOWFkYzVhYzM0ZTFjNjFjNTQ4MjI5YzU3MzliMTZkZjMyIn0.eyJhdWQiOiI0NmMzODZhMi1jYzQ2LTQxNDgtOGU2YS0xOThkZmY0YmNkNjYiLCJqdGkiOiIwMGY1OGEwZTMxZDJkZDUwOWYyNmZjZTBhYzU3OWI2ZTAzN2I1MDBkODc4OGM3MDlhZGM1YWMzNGUxYzYxYzU0ODIyOWM1NzM5YjE2ZGYzMiIsImlhdCI6MTczODgzODY2OCwibmJmIjoxNzM4ODM4NjY4LCJleHAiOjE4OTYwNDgwMDAsInN1YiI6IjMzMjg1MTkiLCJncmFudF90eXBlIjoiIiwiYWNjb3VudF9pZCI6MjUxOTkwMjksImJhc2VfZG9tYWluIjoiYW1vY3JtLnJ1IiwidmVyc2lvbiI6Miwic2NvcGVzIjpbImNybSIsImZpbGVzIiwiZmlsZXNfZGVsZXRlIiwibm90aWZpY2F0aW9ucyIsInB1c2hfbm90aWZpY2F0aW9ucyJdLCJoYXNoX3V1aWQiOiIyY2JjZjIwMC0xNmEyLTRiZWQtYjdhNy1iZjc5ZjczM2M5ZjUiLCJhcGlfZG9tYWluIjoiYXBpLWIuYW1vY3JtLnJ1In0.B0elZrHP_aclPIYfOLOuO8VA8XHJQRf7Ras6W2b58Yg1V5TZMalm0EvdqKDx-Ygb8onU8JAbThzCGOaz_JD7eheimbKQHNXtB-IArAFxSNc4KEkgMtpP-HphUCVhsLi2_0STYZItSBHlyIoqjlR8wdls_ZbUiJ9kmUnXk5Qcfx6KUXbKcuGL7oQPB_ywvliR1c1-HWnrHtg-8mlkqIR3g64_ZFhgR0z4IDLP0SABljLsl6jjD5P3Lu9ua3efBC7TrGy7e8XNegbKNscdvViB4oVuDSRO-u0zJf0AsSsrt0d17bwNdEtQhgIoljUnhBzZGj_z9F0iAj2nSOplpBQZ9Q"  # ← Укажите актуальный токен API
PAYMENT_STATUS_FIELD_ID = 704249
PAYMENT_ID_FIELD_ID = 571561
ORDER_ID_FIELD_ID = 571559  # Добавьте ID поля "order_id" в AmoCRM

YOOKASSA_SHOP_ID = "278210"  # ← ID магазина
YOOKASSA_SECRET_KEY = "live_fiBWt7qk-rZFAr3utLXCLZ3Uc-nTDBYZjiMBUPV-Qp8"  # ← Секретный ключ

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# ✅ Функция поиска сделки по payment_id
def find_lead_by_payment_id(payment_id):
    url = f"https://{AMO_DOMAIN}/api/v4/leads"
    headers = {"Authorization": f"Bearer {AMO_ACCESS_TOKEN}"}
    params = {f"filter[custom_fields_values][{PAYMENT_ID_FIELD_ID}]": payment_id}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200 and "_embedded" in response.json():
        leads = response.json()['_embedded']['leads']
        return leads[0] if leads else None
    return None

# ✅ Функция поиска сделки по order_id
def find_lead_by_order_id(order_id):
    url = f"https://{AMO_DOMAIN}/api/v4/leads"
    headers = {"Authorization": f"Bearer {AMO_ACCESS_TOKEN}"}
    params = {f"filter[custom_fields_values][{ORDER_ID_FIELD_ID}]": order_id}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200 and "_embedded" in response.json():
        leads = response.json()['_embedded']['leads']
        return leads[0] if leads else None
    return None

# ✅ Функция обновления статуса сделки в AmoCRM
def update_lead_payment_status(lead_id, new_status):
    url = f"https://{AMO_DOMAIN}/api/v4/leads/{lead_id}"
    headers = {
        "Authorization": f"Bearer {AMO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "custom_fields_values": [
            {
                "field_id": PAYMENT_STATUS_FIELD_ID,
                "values": [{"value": new_status}]
            }
        ]
    }
    response = requests.patch(url, headers=headers, json=data)
    if response.status_code == 200:
        logging.info(f"✅ Сделка {lead_id} обновлена до '{new_status}'")
    else:
        logging.error(f"❌ Ошибка обновления сделки {lead_id}: {response.text}")

# ✅ Обработчик вебхуков от ЮKassa
@app.route("/payment_status", methods=["POST"])
def payment_status():
    try:
        data = request.json
        logging.info(f"📩 Получен вебхук: {data}")

        payment_id = data.get("object", {}).get("id")
        status = data.get("object", {}).get("status")
        order_id = data.get("object", {}).get("metadata", {}).get("order_id")

        if not status:
            return jsonify({"error": "Missing status"}), 400

        lead = None
        if payment_id:
            lead = find_lead_by_payment_id(payment_id)
        
        if not lead and order_id:
            lead = find_lead_by_order_id(order_id)

        if not lead:
            logging.warning(f"⚠ Лид с payment_id {payment_id} и order_id {order_id} не найден в AmoCRM")
            return jsonify({"error": "Lead not found"}), 404

        lead_id = lead["id"]
        new_status = "Оплачено" if status == "succeeded" else "Не оплачено"

        update_lead_payment_status(lead_id, new_status)

        return jsonify({"success": f"Payment status updated in lead {lead_id}"}), 200

    except Exception as e:
        logging.error(f"❌ Ошибка обработки вебхука: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


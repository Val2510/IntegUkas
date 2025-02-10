
import time
from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import base64
import logging
from yookassa import Configuration, Payment # type: ignore

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

@app.route("/")
def home():
    return "Flask is running!"

# 🔹 Настройки AmoCRM
AMO_DOMAIN = "fitarena.amocrm.ru"  # ← Измените на ваш домен AmoCRM
AMO_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjAwZjU4YTBlMzFkMmRkNTA5ZjI2ZmNlMGFjNTc5YjZlMDM3YjUwMGQ4Nzg4YzcwOWFkYzVhYzM0ZTFjNjFjNTQ4MjI5YzU3MzliMTZkZjMyIn0.eyJhdWQiOiI0NmMzODZhMi1jYzQ2LTQxNDgtOGU2YS0xOThkZmY0YmNkNjYiLCJqdGkiOiIwMGY1OGEwZTMxZDJkZDUwOWYyNmZjZTBhYzU3OWI2ZTAzN2I1MDBkODc4OGM3MDlhZGM1YWMzNGUxYzYxYzU0ODIyOWM1NzM5YjE2ZGYzMiIsImlhdCI6MTczODgzODY2OCwibmJmIjoxNzM4ODM4NjY4LCJleHAiOjE4OTYwNDgwMDAsInN1YiI6IjMzMjg1MTkiLCJncmFudF90eXBlIjoiIiwiYWNjb3VudF9pZCI6MjUxOTkwMjksImJhc2VfZG9tYWluIjoiYW1vY3JtLnJ1IiwidmVyc2lvbiI6Miwic2NvcGVzIjpbImNybSIsImZpbGVzIiwiZmlsZXNfZGVsZXRlIiwibm90aWZpY2F0aW9ucyIsInB1c2hfbm90aWZpY2F0aW9ucyJdLCJoYXNoX3V1aWQiOiIyY2JjZjIwMC0xNmEyLTRiZWQtYjdhNy1iZjc5ZjczM2M5ZjUiLCJhcGlfZG9tYWluIjoiYXBpLWIuYW1vY3JtLnJ1In0.B0elZrHP_aclPIYfOLOuO8VA8XHJQRf7Ras6W2b58Yg1V5TZMalm0EvdqKDx-Ygb8onU8JAbThzCGOaz_JD7eheimbKQHNXtB-IArAFxSNc4KEkgMtpP-HphUCVhsLi2_0STYZItSBHlyIoqjlR8wdls_ZbUiJ9kmUnXk5Qcfx6KUXbKcuGL7oQPB_ywvliR1c1-HWnrHtg-8mlkqIR3g64_ZFhgR0z4IDLP0SABljLsl6jjD5P3Lu9ua3efBC7TrGy7e8XNegbKNscdvViB4oVuDSRO-u0zJf0AsSsrt0d17bwNdEtQhgIoljUnhBzZGj_z9F0iAj2nSOplpBQZ9Q"  # ← Укажите актуальный токен API
PAYMENT_STATUS_FIELD_ID = 704249  # ← ID поля "Статус оплаты" в AmoCRM
PAYMENT_ID_FIELD_ID = 571561  # ← ID поля "ID платежа" в AmoCRM

YOOKASSA_SHOP_ID = "278210"  # ← ID магазина
YOOKASSA_SECRET_KEY = "live_fiBWt7qk-rZFAr3utLXCLZ3Uc-nTDBYZjiMBUPV-Qp8"  # ← Секретный ключ

# ✅ Настройка конфигурации ЮKassa через SDK
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

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
    logging.debug(f"🔍 Поиск лида в AmoCRM по order_id: {order_id}")
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200 and response.json().get('_embedded'):
        leads = response.json()['_embedded']['leads']
        if leads:
            logging.debug(f"✅ Лид найден: {leads[0]['id']}")
            return leads[0]  
    logging.warning(f"⚠ Лид не найден по order_id: {order_id}")
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

    logging.debug(f"🔄 Обновляем статус лида {lead_id} на: {new_status}")
    response = requests.patch(url, headers=headers, json=data)

    if response.status_code == 200:
        logging.info(f"✅ Успешное обновление статуса сделки {lead_id} на '{new_status}'")
        return True
    else:
        logging.error(f"❌ Ошибка обновления лида {lead_id}. Код: {response.status_code}, Ответ: {response.text}")
        return False

# ✅ Функция получения статуса платежа через API ЮKassa
def get_payment_status(payment_id):
    try:
        payment = Payment.find(payment_id)  # Получаем статус платежа
        return payment.status  # "succeeded" или "canceled"
    except Exception as e:
        logging.error(f"❌ Ошибка получения статуса платежа: {e}")
        return str(e)

# ✅ Обработчик вебхуков от ЮKassa
@app.route("/payment_status", methods=["POST"])
def payment_status():
    try:
        # Проверка подлинности вебхука
        #if not verify_yookassa_signature(request):
         #   return jsonify({"error": "Invalid signature"}), 403

        data = request.json
        logging.debug(f"📩 Получен вебхук: {data}")
        order_id = data.get("object", {}).get("metadata", {}).get("order_id") or data.get("object", {}).get("metadata", {}).get("order_id")
        status = data.get("object", {}).get("status")  # "succeeded" или "canceled"
        logging.debug(f"📌 Извлечён order_id: {order_id}, статус: {status}")

        if not order_id or not status:
            logging.warning("⚠ Отсутствует order_id или статус платежа в вебхуке")
            return jsonify({"error": "Missing order_id or status"}), 400

        lead = find_lead_by_order_id(order_id)

        if not lead:
            logging.warning(f"⚠ Лид с order_id {order_id} не найден в AmoCRM")
            return jsonify({"error": "Lead not found"}), 404

        lead_id = lead["id"]

        if update_lead_payment_status(lead_id, status):
            return jsonify({"success": f"Payment status updated in lead {lead_id}"}), 200
        else:
            return jsonify({"error": "Failed to update payment status"}), 500

    except Exception as e:
        logging.error(f"❌ Ошибка обработки вебхука: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ Проверка статуса платежа по `payment_id`
@app.route("/check_payment/<payment_id>", methods=["GET"])
def check_payment(payment_id):
    try:
        status = get_payment_status(payment_id)
        logging.debug(f"🔎 Проверка статуса платежа {payment_id}: {status}")
        return jsonify({"payment_id": payment_id, "status": status}), 200
    except Exception as e:
        logging.error(f"❌ Ошибка при проверке платежа {payment_id}: {e}")
        return jsonify({"error": str(e)}), 500
    
# ✅ Функция поиска сделок в AmoCRM, где статус оплаты = "Не оплачено"
def get_unpaid_leads():
    url = f"https://{AMO_DOMAIN}/api/v4/leads"
    headers = {"Authorization": f"Bearer {AMO_ACCESS_TOKEN}"}

    params = {
        f"filter[custom_fields_values][{PAYMENT_STATUS_FIELD_ID}]": "Не оплачено"
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200 and "_embedded" in response.json():
        leads = response.json()['_embedded']['leads']
        logging.info(f"🔍 Найдено {len(leads)} неоплаченных сделок")
        return leads
    else:
        logging.warning("⚠ Не найдены сделки со статусом 'Не оплачено'")
        return []

# ✅ Функция получения `payment_id` из сделки
def get_payment_id_from_lead(lead):
    for field in lead.get("custom_fields_values", []):
        if field["field_id"] == PAYMENT_ID_FIELD_ID:
            return field["values"][0]["value"]
    return None

# ✅ Функция обновления статуса сделки
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

# ✅ Основной цикл авто-обновления сделок
def auto_update_payments():
    while True:
        logging.info("🔄 Начало проверки неоплаченных сделок...")

        leads = get_unpaid_leads()

        for lead in leads:
            payment_id = get_payment_id_from_lead(lead)
            if payment_id:
                status = get_payment_status(payment_id)

                if status == "succeeded":
                    update_lead_payment_status(lead["id"], "Оплачено")
                else:
                    logging.info(f"⏳ Платёж {payment_id} ещё не завершён, статус: {status}")

        logging.info("⏸ Ожидание 10 минут перед следующей проверкой...")
        time.sleep(600)  # Ждём 10 минут перед следующей проверкой

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



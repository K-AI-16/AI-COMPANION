import os
import time
import requests
from datetime import datetime, timedelta

WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
_API_URL = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
_HEADERS = {"Content-Type": "application/json"}


def _auth():
    return {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}


class WhatsAppService:

    @staticmethod
    def send_text(to: str, message: str) -> bool:
        if not WHATSAPP_PHONE_NUMBER_ID or not WHATSAPP_ACCESS_TOKEN:
            print("WhatsApp skipped: credentials not configured")
            return False
        try:
            res = requests.post(
                _API_URL,
                headers={**_HEADERS, **_auth()},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": message},
                },
                timeout=10,
            )
            res.raise_for_status()
            return True
        except Exception as e:
            print(f"WhatsApp send_text failed: {e}")
            return False

    @staticmethod
    def mark_read(to: str, message_id: str):
        if not WHATSAPP_PHONE_NUMBER_ID or not WHATSAPP_ACCESS_TOKEN:
            return
        try:
            requests.post(
                _API_URL,
                headers={**_HEADERS, **_auth()},
                json={
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id,
                },
                timeout=5,
            )
        except Exception:
            pass

    @staticmethod
    def send_template(to: str, template_name: str = "hello_world", language: str = "en_US") -> bool:
        if not WHATSAPP_PHONE_NUMBER_ID or not WHATSAPP_ACCESS_TOKEN:
            return False
        try:
            res = requests.post(
                _API_URL,
                headers={**_HEADERS, **_auth()},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": language},
                    },
                },
                timeout=10,
            )
            res.raise_for_status()
            return True
        except Exception as e:
            print(f"WhatsApp send_template failed: {e}")
            return False

    @staticmethod
    def send_replies(to: str, replies: list):
        for i, reply in enumerate(replies):
            if i > 0:
                time.sleep(1.2)
            WhatsAppService.send_text(to, reply)

    @staticmethod
    def send_to_user(db, user_id: str, message: str, last_user_msg_time=None) -> bool:
        if not user_id.startswith("wa_"):
            return False

        phone = user_id[3:]  # strip "wa_" prefix

        within_24h = False
        if last_user_msg_time:
            within_24h = (datetime.utcnow() - last_user_msg_time) < timedelta(hours=24)

        if within_24h:
            return WhatsAppService.send_text(phone, message)
        else:
            # Outside free window — send template to reopen the conversation
            return WhatsAppService.send_template(phone)

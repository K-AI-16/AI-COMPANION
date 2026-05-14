import os
import json

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY_PATH = os.getenv("VAPID_PRIVATE_KEY_PATH", "vapid_private.pem")
VAPID_CLAIMS = {"sub": "mailto:rohit.loves.nature@gmail.com"}


class PushService:

    @staticmethod
    def send(subscription, message: str) -> bool:
        if not VAPID_PUBLIC_KEY or not os.path.exists(VAPID_PRIVATE_KEY_PATH):
            print("Push skipped: VAPID keys not configured")
            return False
        try:
            from pywebpush import webpush, WebPushException
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth_key,
                    },
                },
                data=json.dumps({"title": "Ari", "body": message}),
                vapid_private_key=VAPID_PRIVATE_KEY_PATH,
                vapid_claims=VAPID_CLAIMS,
            )
            return True
        except Exception as e:
            print(f"Push send failed: {e}")
            return False

    @staticmethod
    def send_to_user(db, user_id: str, message: str) -> bool:
        from app.repositories.push_repository import PushRepository
        sub = PushRepository.get(db, user_id)
        if not sub:
            return False
        return PushService.send(sub, message)

    @staticmethod
    def send_expo(token: str, message: str) -> bool:
        try:
            import requests
            res = requests.post(
                "https://exp.host/--/api/v2/push/send",
                json={"to": token, "title": "Ari", "body": message, "sound": "default"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=10,
            )
            return res.status_code == 200
        except Exception as e:
            print(f"Expo push failed: {e}")
            return False

    @staticmethod
    def send_expo_to_user(db, user_id: str, message: str) -> bool:
        from app.repositories.expo_push_repository import ExpoPushRepository
        record = ExpoPushRepository.get(db, user_id)
        if not record:
            return False
        return PushService.send_expo(record.token, message)

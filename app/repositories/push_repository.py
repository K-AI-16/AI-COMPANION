from app.models.push_subscription import PushSubscription


class PushRepository:

    @staticmethod
    def get(db, user_id: str):
        return db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id
        ).first()

    @staticmethod
    def save(db, user_id: str, endpoint: str, p256dh: str, auth_key: str):
        existing = PushRepository.get(db, user_id)
        if existing:
            existing.endpoint = endpoint
            existing.p256dh = p256dh
            existing.auth_key = auth_key
        else:
            existing = PushSubscription(
                user_id=user_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth_key=auth_key,
            )
            db.add(existing)
        db.commit()
        return existing

    @staticmethod
    def delete(db, user_id: str):
        sub = PushRepository.get(db, user_id)
        if sub:
            db.delete(sub)
            db.commit()

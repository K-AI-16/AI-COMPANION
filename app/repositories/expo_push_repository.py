from app.models.expo_push_token import ExpoPushToken


class ExpoPushRepository:

    @staticmethod
    def save(db, user_id: str, token: str) -> ExpoPushToken:
        existing = db.query(ExpoPushToken).filter(ExpoPushToken.user_id == user_id).first()
        if existing:
            existing.token = token
            db.commit()
            db.refresh(existing)
            return existing
        record = ExpoPushToken(user_id=user_id, token=token)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get(db, user_id: str) -> ExpoPushToken | None:
        return db.query(ExpoPushToken).filter(ExpoPushToken.user_id == user_id).first()

from datetime import datetime

from app.models.user import User


class UserRepository:

    @staticmethod
    def get_or_create(db, user_id: str):
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            user = User(id=user_id)
            db.add(user)
            db.commit()
            db.refresh(user)

        return user

    @staticmethod
    def mark_active(db, user_id: str):
        user = UserRepository.get_or_create(db, user_id)
        user.last_active_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user

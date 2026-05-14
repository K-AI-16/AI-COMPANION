from sqlalchemy.orm import Session
from app.models.message import Message
from sqlalchemy import desc

class MessageRepository:

    @staticmethod
    def create_message(db: Session, user_id: str, role: str, content: str):
        message = Message(
            user_id=user_id,
            role=role,
            content=content
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    @staticmethod
    def get_last_user_message(db, user_id: str):
        return (
            db.query(Message)
            .filter(
                Message.user_id == user_id,
                Message.role == "user"
            )
            .order_by(desc(Message.created_at))
            .first()
        )
    @staticmethod
    def get_recent_messages(db, user_id: str, limit: int = 8):
        return (
            db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
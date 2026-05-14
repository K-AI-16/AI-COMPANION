from sqlalchemy.orm import Session
from app.models.signal import Signal

class SignalRepository:

    @staticmethod
    def create_signal(db: Session, data: dict):
        signal = Signal(**data)
        db.add(signal)
        db.commit()
        db.refresh(signal)
        return signal
    @staticmethod
    def get_recent_signals(db: Session, user_id: str, limit: int = 5):
        return (
            db.query(Signal)
            .filter(Signal.user_id == user_id)
            .order_by(Signal.created_at.desc())
            .limit(limit)
            .all()
        )
    @staticmethod
    def get_latest_signal(db, user_id: str):
        return (
            db.query(Signal)
            .filter(Signal.user_id == user_id)
            .order_by(Signal.created_at.desc())
            .first()
        )
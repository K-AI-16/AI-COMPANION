from datetime import datetime, timedelta
from app.models.session_summary import SessionSummary


class SessionSummaryRepository:

    @staticmethod
    def create(db, user_id: str, summary: str):
        record = SessionSummary(user_id=user_id, summary=summary)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_recent(db, user_id: str, limit: int = 3):
        return (
            db.query(SessionSummary)
            .filter(SessionSummary.user_id == user_id)
            .order_by(SessionSummary.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def has_recent_summary(db, user_id: str, since_hours: float = 8) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)
        return (
            db.query(SessionSummary)
            .filter(
                SessionSummary.user_id == user_id,
                SessionSummary.created_at >= cutoff,
            )
            .first()
        ) is not None

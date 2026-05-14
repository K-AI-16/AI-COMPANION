from app.models.trigger_log import TriggerLog
from datetime import datetime, timedelta


class TriggerRepository:

    @staticmethod
    def get_recent_triggers(db, user_id: str, hours: int = 24):
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        return (
            db.query(TriggerLog)
            .filter(
                TriggerLog.user_id == user_id,
                TriggerLog.sent_at >= cutoff
            )
            .all()
        )
    @staticmethod
    def create_trigger(db, user_id, trigger_type=None, confidence=None, message=None):

        if not message or len(message.strip()) == 0:
            print("Skipping empty trigger")
            return None

        trigger = TriggerLog(
            user_id=user_id,
            trigger_type=trigger_type,
            confidence=str(confidence) if confidence is not None else None,
            message=message,
            responded=False,
            delivered=False
        )

        db.add(trigger)
        db.commit()
        db.refresh(trigger)

        return trigger
    @staticmethod
    def get_weekly_trigger_count(db, user_id: str):
        one_week_ago = datetime.utcnow() - timedelta(days=7)

        return db.query(TriggerLog).filter(
            TriggerLog.user_id == user_id,
            TriggerLog.sent_at >= one_week_ago
        ).count()

    @staticmethod
    def get_unresponded_trigger_count(db, user_id: str, limit: int = 2):
        triggers = (
            db.query(TriggerLog)
            .filter(
                TriggerLog.user_id == user_id,
                TriggerLog.delivered == True
            )
            .order_by(TriggerLog.sent_at.desc())
            .limit(limit)
            .all()
        )

        if len(triggers) < limit:
            return 0

        return sum(1 for trigger in triggers if not trigger.responded)

    @staticmethod
    def get_last_delivered_trigger(db, user_id: str):
        return (
            db.query(TriggerLog)
            .filter(
                TriggerLog.user_id == user_id,
                TriggerLog.delivered == True
            )
            .order_by(TriggerLog.sent_at.desc())
            .first()
        )

    @staticmethod
    def get_last_trigger(db, user_id: str):
        return (
            db.query(TriggerLog)
            .filter(TriggerLog.user_id == user_id)
            .order_by(TriggerLog.sent_at.desc())
            .first()
        )
    @staticmethod
    def get_undelivered_triggers(db, user_id: str):
        return (
            db.query(TriggerLog)
            .filter(
                TriggerLog.user_id == user_id,
                TriggerLog.delivered == False
            )
            .order_by(TriggerLog.sent_at.asc())
            .all()
        )
    @staticmethod
    def mark_as_delivered(db, trigger_id: str):
        trigger = db.query(TriggerLog).filter(
            TriggerLog.id == trigger_id
        ).first()

        if trigger:
            trigger.delivered = True
            db.commit()
    @staticmethod
    def mark_as_responded(db, user_id: str):
        triggers = db.query(TriggerLog).filter(
            TriggerLog.user_id == user_id,
            TriggerLog.responded == False
        ).all()

        for t in triggers:
            t.responded = True

        db.commit()

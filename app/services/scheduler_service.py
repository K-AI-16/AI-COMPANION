import time
import random
import datetime as dt
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging_config import get_logger
from app.models.user import User
from app.models.insight import Insight
from app.services.decision_service import DecisionService
from app.services.trigger_service import TriggerService
from app.repositories.trigger_repository import TriggerRepository
from app.repositories.memory_repository import MemoryRepository

logger = get_logger("scheduler")


class SchedulerService:

    _last_cleanup_date = None

    @staticmethod
    def _run_cleanup(db):
        users = db.query(User).all()
        for user in users:
            MemoryRepository.cleanup_low_quality_memories(db, user.id)
        logger.info(f"Memory cleanup ran for {len(users)} user(s)")

    @staticmethod
    def _run_session_summaries(db):
        from app.services.session_summary_service import SessionSummaryService
        from app.repositories.session_summary_repository import SessionSummaryRepository
        from app.repositories.message_repository import MessageRepository

        users = db.query(User).all()
        for user in users:
            last_msg = MessageRepository.get_last_user_message(db, user.id)
            if not last_msg:
                continue
            hours_since = (datetime.utcnow() - last_msg.created_at).total_seconds() / 3600
            if not (6 <= hours_since <= 48):
                continue
            if SessionSummaryRepository.has_recent_summary(db, user.id, since_hours=hours_since - 1):
                continue
            summary = SessionSummaryService.generate(db, user.id)
            if summary:
                SessionSummaryRepository.create(db, user.id, summary)
                logger.info(f"Session summary created for user {user.id}")

    @staticmethod
    def run():
        while True:
            logger.debug("Scheduler tick")

            db: Session = None

            try:
                db = SessionLocal()

                today = dt.date.today()
                if SchedulerService._last_cleanup_date != today:
                    SchedulerService._run_cleanup(db)
                    SchedulerService._last_cleanup_date = today

                SchedulerService._run_session_summaries(db)

                current_hour = datetime.now().hour

                if current_hour < 20 or current_hour > 23:
                    logger.debug("Outside trigger window (20:00–23:59), sleeping")
                    db.close()
                    db = None
                    time.sleep(30 * 60)
                    continue

                users = db.query(User).all()
                logger.info(f"Evaluating {len(users)} user(s) for proactive triggers")

                for user in users:
                    insight = db.query(Insight).filter(
                        Insight.user_id == user.id
                    ).first()

                    if not insight:
                        logger.debug(f"No insight for user {user.id}, skipping")
                        continue

                    decision = DecisionService.evaluate(db, insight.__dict__)

                    if not decision.get("candidate"):
                        logger.debug(f"User {user.id}: no trigger — {decision.get('reason')}")
                        continue

                    memories = MemoryRepository.get_user_memories(db, user.id)
                    last_trigger = TriggerRepository.get_last_trigger(db, user.id)

                    message = TriggerService.generate_trigger_message(
                        insight.__dict__,
                        memories,
                        last_trigger,
                        decision.get("trigger_type")
                    )

                    if not message or len(message.strip()) == 0:
                        logger.warning(f"User {user.id}: empty trigger message, skipping")
                        continue

                    logger.info(f"Triggering user {user.id} [{decision.get('trigger_type')}]: {message!r}")

                    TriggerRepository.create_trigger(
                        db=db,
                        user_id=user.id,
                        trigger_type=decision.get("trigger_type"),
                        confidence=decision.get("score"),
                        message=message
                    )

                    from app.services.push_service import PushService
                    PushService.send_to_user(db, user.id, message)
                    PushService.send_expo_to_user(db, user.id, message)

                    from app.services.whatsapp_service import WhatsAppService
                    from app.repositories.message_repository import MessageRepository
                    last_msg = MessageRepository.get_last_user_message(db, user.id)
                    WhatsAppService.send_to_user(
                        db, user.id, message,
                        last_msg.created_at if last_msg else None
                    )

                    time.sleep(1 + random.random())

            except Exception as e:
                logger.exception(f"Scheduler error: {e}")

            finally:
                if db:
                    db.close()

            sleep_time = (30 * 60) + random.randint(0, 120)
            logger.debug(f"Sleeping {sleep_time}s until next tick")
            time.sleep(sleep_time)

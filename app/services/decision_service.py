from datetime import datetime, timedelta
import random

from app.repositories.trigger_repository import TriggerRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.confidence_gate import ConfidenceGate
from app.utils.memory_filters import is_actionable_state


class DecisionService:

    @staticmethod
    def evaluate(db, insight: dict, overrides: dict = None):
        overrides = overrides or {}
        user_id = insight["user_id"]

        last_user_msg = MessageRepository.get_last_user_message(db, user_id)
        inactivity_hours = 999

        if last_user_msg:
            inactivity_hours = (
                datetime.utcnow() - last_user_msg.created_at
            ).total_seconds() / 3600

        pending_triggers = TriggerRepository.get_undelivered_triggers(
            db,
            user_id
        )

        if pending_triggers:
            return {
                "candidate": False,
                "reason": "trigger already waiting for delivery"
            }

        weekly_count = TriggerRepository.get_weekly_trigger_count(db, user_id)

        if weekly_count >= overrides.get("weekly_limit", 5):
            return {
                "candidate": False,
                "reason": "weekly limit reached"
            }

        ignored_count = TriggerRepository.get_unresponded_trigger_count(
            db,
            user_id,
            limit=2
        )

        if ignored_count >= 2:
            return {
                "candidate": False,
                "reason": "last two triggers were ignored"
            }

        last_delivered_trigger = TriggerRepository.get_last_delivered_trigger(
            db,
            user_id
        )

        if (
            last_delivered_trigger
            and not last_delivered_trigger.responded
            and last_delivered_trigger.sent_at
        ):
            hours_since_trigger = (
                datetime.utcnow() - last_delivered_trigger.sent_at
            ).total_seconds() / 3600

            if hours_since_trigger < overrides.get("followup_wait_hours", 24):
                return {
                    "candidate": False,
                    "reason": "waiting before gentle follow-up"
                }

            if hours_since_trigger <= 72:
                return {
                    "candidate": True,
                    "trigger_type": "gentle_followup",
                    "score": 0.7,
                    "reason": "one ignored trigger; sending one low-pressure follow-up"
                }

            return {
                "candidate": False,
                "reason": "ignored trigger is too old; backing off"
            }

        last_trigger = TriggerRepository.get_last_trigger(db, user_id)
        emotion = insight["dominant_emotion"]
        cooldown_hours = 24 if emotion in ["sad", "anxious"] else 48

        if last_trigger and last_trigger.sent_at:
            time_diff = datetime.utcnow() - last_trigger.sent_at

            if time_diff < timedelta(hours=overrides.get("hard_cooldown_hours", 12)):
                return {
                    "candidate": False,
                    "reason": "recent trigger cooldown active"
                }

        confidence_gate = ConfidenceGate.evaluate(db, user_id, insight)

        if not confidence_gate["passed"]:
            return {
                "candidate": False,
                "reason": confidence_gate["reason"]
            }

        memories = MemoryRepository.get_user_memories(db, user_id, limit=20)
        state_memories = [m for m in memories if is_actionable_state(m)]
        open_threads = [m for m in memories if m.type == "open_thread"]
        emotional_context = [m for m in memories if m.type == "emotional_context"]

        has_memory_reason = bool(
            open_threads
            or state_memories
            or emotional_context
        )

        if inactivity_hours < overrides.get("min_inactivity_hours", 8):
            return {
                "candidate": False,
                "reason": "user active too recently for a natural follow-up"
            }

        if inactivity_hours < 24 and has_memory_reason:
            trigger_type = "open_thread"

            if state_memories and not open_threads:
                trigger_type = "state_followup"

            return {
                "candidate": True,
                "trigger_type": trigger_type,
                "score": 0.72,
                "reason": "memory-based curious follow-up after quiet gap"
            }

        if inactivity_hours < 24:
            return {
                "candidate": False,
                "reason": "no strong memory reason for same-day follow-up"
            }

        if last_trigger and last_trigger.sent_at:
            time_diff = datetime.utcnow() - last_trigger.sent_at

            if time_diff < timedelta(hours=cooldown_hours):
                return {
                    "candidate": False,
                    "reason": f"cooldown active ({cooldown_hours}h)"
                }

        state_boost = 0.2 if state_memories else 0.0
        open_thread_boost = 0.15 if open_threads else 0.0

        emotion_score = {
            "sad": 0.75,
            "anxious": 0.65,
            "neutral": 0.35,
            "happy": 0.15
        }

        trend_multiplier = {
            "negative": 1.2,
            "stable": 1.0,
            "positive": 0.85
        }

        trend = insight["emotion_trend"]
        engagement = insight["engagement_score"]
        recency = insight["recency_score"]

        base_score = emotion_score.get(emotion, 0.3)
        trend_factor = trend_multiplier.get(trend, 1.0)

        engagement_factor = 1 - engagement
        recency_factor = 1 - recency

        score = base_score * trend_factor
        score += 0.25 * engagement_factor
        score += 0.25 * recency_factor

        inactivity_boost = min(0.5, inactivity_hours / 48)

        score += inactivity_boost
        score += state_boost
        score += open_thread_boost

        print("Trigger Score:", score)

        threshold = overrides.get("score_threshold", 0.75)

        if score >= threshold:
            probability = min(0.85, score)

            if overrides.get("skip_randomness") or random.random() < probability:
                trigger_type = "emotional"
                if open_threads and emotion not in ["sad", "anxious"]:
                    trigger_type = "open_thread"

                return {
                    "candidate": True,
                    "trigger_type": trigger_type,
                    "score": round(score, 2),
                    "reason": "trigger conditions met"
                }

            return {
                "candidate": False,
                "score": round(score, 2),
                "reason": "skipped due to randomness"
            }

        return {
            "candidate": False,
            "score": round(score, 2),
            "reason": "score below threshold"
        }

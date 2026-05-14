from app.repositories.signal_repository import SignalRepository


class ConfidenceGate:

    @staticmethod
    def evaluate(db, user_id: str, insight: dict):
        latest_signal = SignalRepository.get_latest_signal(db, user_id)

        if not latest_signal:
            return {
                "passed": False,
                "reason": "no recent signal"
            }

        if latest_signal.confidence is not None and latest_signal.confidence < 0.35:
            return {
                "passed": False,
                "reason": "signal confidence too low"
            }

        if (
            latest_signal.emotion_confidence is not None
            and latest_signal.emotion_confidence < 0.35
        ):
            return {
                "passed": False,
                "reason": "emotion confidence too low"
            }

        if insight.get("recency_score", 0) < 0.3:
            return {
                "passed": False,
                "reason": "insight too stale"
            }

        if insight.get("engagement_score", 0) < 0.2:
            return {
                "passed": False,
                "reason": "engagement too low"
            }

        return {
            "passed": True,
            "reason": "confidence gate passed"
        }

from app.repositories.signal_repository import SignalRepository
from collections import Counter
from datetime import datetime

class InsightService:

    @staticmethod
    def compute_insights(db, user_id: str):

        signals = SignalRepository.get_recent_signals(db, user_id)

        if not signals:
            return None

        # --- dominant emotion ---
        emotions = [s.emotion for s in signals if s.emotion]
        dominant_emotion = Counter(emotions).most_common(1)[0][0]

        # --- emotion trend ---
        negative_emotions = ["sad", "anxious", "angry", "lonely"]
        negative_count = sum(1 for s in signals if s.emotion in negative_emotions)

        if negative_count >= len(signals) / 2:
            emotion_trend = "negative"
        else:
            emotion_trend = "stable"

        # --- engagement score ---
        engagement_map = {
            "low": 0.3,
            "medium": 0.6,
            "high": 1.0
        }

        engagement_score = sum(
            engagement_map.get(s.engagement, 0.5) for s in signals
        ) / len(signals)

        # --- recency score ---
        latest_signal = signals[0]
        time_diff = (datetime.utcnow() - latest_signal.created_at).total_seconds()

        # simple scoring
        if time_diff < 3600:
            recency_score = 1.0
        elif time_diff < 86400:
            recency_score = 0.7
        else:
            recency_score = 0.3

        return {
            "user_id": user_id,
            "dominant_emotion": dominant_emotion,
            "emotion_trend": emotion_trend,
            "engagement_score": engagement_score,
            "recency_score": recency_score
        }
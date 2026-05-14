from app.services.llm_service import client
import json

class SignalService:

    @staticmethod
    def extract_signal(message: str) -> dict:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract structured signals from user message.\n"
                        "Return ONLY valid JSON.\n"
                        "Schema:\n"
                        "{\n"
                        '  "emotion": "sad | happy | anxious | neutral",\n'
                        '  "emotion_confidence": float,\n'
                        '  "intent": string,\n'
                        '  "engagement": "low | medium | high",\n'
                        '  "confidence": float\n'
                        "}\n"
                        "If unsure, map emotion to closest category.\n"
                        "Do not invent new emotion values.\n"
                        "No explanation."
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            max_tokens=100
        )

        content = response.choices[0].message.content

        try:
            data = json.loads(content)
        except Exception:
            # fallback if JSON breaks
            return {
                "emotion": "neutral",
                "emotion_confidence": 0.5,
                "intent": "unknown",
                "engagement": "medium",
                "confidence": 0.5
            }

        # NORMALIZATION LAYER

        allowed_emotions = ["sad", "happy", "anxious", "neutral"]
        allowed_engagement = ["low", "medium", "high"]

        emotion = str(data.get("emotion", "")).lower().strip()

        # map common variants
        if emotion in ["loneliness", "lonely", "depressed", "down"]:
            emotion = "sad"
        elif emotion not in allowed_emotions:
            emotion = "neutral"

        engagement = str(data.get("engagement", "")).lower().strip()
        if engagement not in allowed_engagement:
            engagement = "medium"

        # update normalized values
        data["emotion"] = emotion
        data["engagement"] = engagement

        return data
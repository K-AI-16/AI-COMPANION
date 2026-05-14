from app.services.llm_service import client
import json
import re


class ConversationStateService:

    ALLOWED_STATES = {
        "engaged",
        "neutral",
        "disengaged",
        "vulnerable",
        "playful",
        "practical",
        "rude",
    }

    @staticmethod
    def classify(message: str, signal_data: dict = None):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify the user's conversation state.\n"
                            "Return ONLY valid JSON with fields: state, confidence, reason.\n\n"
                            "Allowed states:\n"
                            "- engaged: meaningful conversational input\n"
                            "- neutral: short/minimal but not rejecting\n"
                            "- disengaged: wants to stop, dismissive, or low-effort closing\n"
                            "- vulnerable: emotionally heavy, lonely, anxious, sad, overwhelmed\n"
                            "- playful: joking, teasing, casual humor\n"
                            "- practical: asking for help, facts, commands, or concrete action\n"
                            "- rude: hostile, insulting, or aggressive\n\n"
                            "Do not over-label mild complaints as vulnerable.\n"
                            "If unsure, use neutral or engaged.\n"
                        )
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                max_tokens=80
            )

            content = response.choices[0].message.content.strip()
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(content)

            state = str(data.get("state", "")).lower().strip()
            confidence = float(data.get("confidence", 0.5))

            if state not in ConversationStateService.ALLOWED_STATES:
                return ConversationStateService._fallback(message, signal_data)

            return {
                "state": state,
                "confidence": max(0.0, min(1.0, confidence)),
                "reason": str(data.get("reason", "")).strip()
            }

        except Exception:
            return ConversationStateService._fallback(message, signal_data)

    @staticmethod
    def _fallback(message: str, signal_data: dict = None):
        signal_data = signal_data or {}
        text = ConversationStateService._normalize(message)
        tokens = ConversationStateService._tokens(text)
        token_count = len(tokens)
        emotion = str(signal_data.get("emotion", "")).lower()
        intent = str(signal_data.get("intent", "")).lower()
        engagement = str(signal_data.get("engagement", "")).lower()

        scores = {
            "engaged": 0.15,
            "neutral": 0.0,
            "disengaged": 0.0,
            "vulnerable": 0.0,
            "playful": 0.0,
            "practical": 0.0,
            "rude": 0.0,
        }

        cue_groups = {
            "disengaged": {
                "terms": {
                    "stop", "enough", "bye", "later", "leave", "done",
                    "busy", "nah", "nope", "whatever",
                },
                "phrases": {
                    "not now", "no mood", "no energy", "leave me",
                    "drop it", "let it be", "can we stop", "don't want",
                    "do not want", "not interested", "not in the mood",
                },
            },
            "vulnerable": {
                "terms": {
                    "alone", "lonely", "empty", "exhausted", "overwhelmed",
                    "anxious", "anxiety", "sad", "low", "depressed",
                    "scared", "panic", "hurt", "crying", "tired",
                    "hopeless", "stressed", "broken",
                },
                "phrases": {
                    "feel like", "feeling low", "can't handle",
                    "cannot handle", "too much", "falling apart",
                    "not okay", "not fine",
                },
            },
            "playful": {
                "terms": {
                    "lol", "lmao", "haha", "hehe", "jk", "bruh",
                    "wild", "dramatic", "roast", "funny",
                },
                "phrases": {
                    "just kidding", "kidding obviously", "villain arc",
                    "main character",
                },
            },
            "practical": {
                "terms": {
                    "how", "what", "why", "when", "where", "can",
                    "could", "should", "help", "explain", "show",
                    "make", "fix", "build", "command", "error",
                },
                "phrases": {
                    "how do", "how can", "what is", "can you",
                    "could you", "help me", "i need", "tell me",
                },
            },
            "rude": {
                "terms": {
                    "stupid", "idiot", "dumb", "useless", "shut",
                    "annoying", "trash",
                },
                "phrases": {
                    "shut up", "go away", "you suck",
                },
            },
        }

        for state, cues in cue_groups.items():
            scores[state] += ConversationStateService._score_cues(
                text,
                tokens,
                cues["terms"],
                cues["phrases"],
            )

        if "?" in text:
            scores["practical"] += 0.35

        if emotion in ["sad", "anxious"]:
            scores["vulnerable"] += 0.45
        elif emotion == "happy":
            scores["playful"] += 0.15

        if engagement == "low":
            scores["neutral"] += 0.25
            scores["engaged"] -= 0.1
        elif engagement == "high":
            scores["engaged"] += 0.25

        if any(word in intent for word in ["ask", "help", "request", "question"]):
            scores["practical"] += 0.35

        if token_count <= 2:
            scores["neutral"] += 0.45
            scores["engaged"] -= 0.1
        elif token_count >= 8:
            scores["engaged"] += 0.25

        if scores["vulnerable"] >= 0.6 and token_count <= 3:
            scores["neutral"] += 0.15

        state = max(scores, key=scores.get)

        if scores[state] < 0.35:
            state = "neutral" if token_count <= 3 else "engaged"

        confidence = max(0.35, min(0.75, scores[state]))

        return {
            "state": state,
            "confidence": round(confidence, 2),
            "reason": f"fallback NLP scorer: {ConversationStateService._top_scores(scores)}"
        }

    @staticmethod
    def _normalize(message: str):
        text = (message or "").lower().strip()
        text = text.replace("’", "'")
        text = text.replace("dont", "don't")
        text = text.replace("cant", "can't")
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _tokens(text: str):
        return re.findall(r"[a-z0-9']+", text)

    @staticmethod
    def _score_cues(text: str, tokens: list, terms: set, phrases: set):
        score = 0.0
        token_set = set(tokens)

        score += 0.2 * len(token_set.intersection(terms))

        for phrase in phrases:
            if phrase in text:
                score += 0.35

        return min(score, 0.9)

    @staticmethod
    def _top_scores(scores: dict):
        top = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
        return ", ".join(f"{state}={round(score, 2)}" for state, score in top)

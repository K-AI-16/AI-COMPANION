from app.services.llm_service import client
from datetime import datetime

NO_NUDGE_STATES = {"disengaged", "rude"}

# Nudge: fires mid-conversation when user goes quiet after an assistant message.
# Goal: soft, thread-specific re-ping — not a generic wellness check-in.


class NudgeService:

    @staticmethod
    def should_nudge(conversation_state: str) -> bool:
        return conversation_state not in NO_NUDGE_STATES

    @staticmethod
    def should_nudge_by_time(db, user_id: str, min_silence_seconds: int = 90) -> bool:
        from app.repositories.message_repository import MessageRepository
        last_user_msg = MessageRepository.get_last_user_message(db, user_id)
        if not last_user_msg:
            return True
        seconds_since = (datetime.utcnow() - last_user_msg.created_at).total_seconds()
        return seconds_since >= min_silence_seconds

    @staticmethod
    def generate(conversation_state: str, db=None, user_id: str = None) -> str:
        context = ""
        last_topic = ""
        if db and user_id:
            from app.repositories.message_repository import MessageRepository
            recent = MessageRepository.get_recent_messages(db, user_id, limit=8)
            if recent:
                msgs = list(reversed(recent))
                context = "\n".join(f"{m.role}: {m.content}" for m in msgs)
                # Pull the last user message as the topic to nudge on
                user_msgs = [m for m in msgs if m.role == "user"]
                if user_msgs:
                    last_topic = user_msgs[-1].content

        prompt = (
            "You are Ari. The user went quiet in the middle of a conversation.\n"
            "Your job: send one very short message (under 10 words) that picks up the thread they dropped.\n\n"
            "What this is NOT:\n"
            "- Not a wellness check ('you okay?', 'everything alright?')\n"
            "- Not a generic ping ('still there?', 'hey', 'you around?')\n"
            "- Not asking a new topic — stay on what they were just talking about\n\n"
            "What this IS:\n"
            "- A light, natural continuation of what they just said\n"
            "- Like a friend texting 'wait what happened after that?'\n"
            "- Specific to the thread — not generic\n\n"
            + (f"Recent conversation:\n{context}\n\n" if context else "")
            + (f"The last thing the user said was: {last_topic}\n\n" if last_topic else "")
            + "Reply with just the message. No emojis."
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=25,
                temperature=1.0,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return "wait, what happened with that?"

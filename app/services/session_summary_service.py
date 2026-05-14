from app.services.llm_service import client
from app.repositories.message_repository import MessageRepository


class SessionSummaryService:

    @staticmethod
    def generate(db, user_id: str) -> str | None:
        messages = MessageRepository.get_recent_messages(db, user_id, limit=20)

        if not messages or len(messages) < 3:
            return None

        convo = "\n".join(
            f"{m.role}: {m.content}" for m in reversed(messages)
        )

        prompt = (
            "Summarize this conversation in 2-3 short bullet points.\n"
            "Focus on: what topics came up, the user's mood/energy, anything notable or unresolved.\n"
            "Be factual and brief. No fluff.\n\n"
            f"{convo}"
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Session summary generation failed: {e}")
            return None

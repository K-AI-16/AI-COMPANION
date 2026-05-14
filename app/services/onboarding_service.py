from app.repositories.user_state_repository import UserStateRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.llm_service import LLMService


class OnboardingService:

    @staticmethod
    def handle(db, user_id: str, message: str, base_llm_messages):

        state = UserStateRepository.get_or_create(db, user_id)
        state.message_count += 1

        onboarding_instructions = (
            "The user is still getting to know you.\n"
            "Be warm, casual, and low-pressure.\n"
            "Do not ask a question in every message. Let the conversation breathe.\n"
        )

        if state.message_count <= 2:
            onboarding_instructions += (
                "Keep it especially natural. No onboarding speech.\n"
            )

        if state.name_captured and state.message_count <= 5:
            onboarding_instructions += (
                "You know the user's name. At most once, ask a natural question "
                "that helps understand their daily life. Do not stack questions.\n"
            )

        base_llm_messages[0]["content"] += (
            "\n\nOnboarding hints:\n" + onboarding_instructions
        )

        reply = LLMService.generate_reply(base_llm_messages).strip()

        if not state.name_captured and state.message_count in [2, 4]:
            reply += " ||| btw what should I call you?"

        if not state.name_captured:
            extracted_name = OnboardingService._extract_name(message)

            if extracted_name:
                state.name = extracted_name
                state.name_captured = True
                MemoryRepository.upsert_by_key(db, user_id, "identity", "name", f"User's name is {extracted_name}")

        should_ask_notification = (
            state.name_captured
            and not state.notification_prompted
            and state.message_count >= 4
        )

        if should_ask_notification and state.message_count in [4, 6]:
            reply += (
                " also, I can occasionally nudge you later if that feels okay. "
                "No dramatic notification campaign, promise."
            )
            state.notification_prompted = True

        if state.name_captured and state.notification_prompted:
            state.stage = "DONE"

        UserStateRepository.update(db, state)

        return reply

    @staticmethod
    def _extract_name(message: str):
        try:
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "The user was just asked what they'd like to be called.\n"
                        "Extract their name from their response.\n"
                        "Return ONLY the name or NULL.\n"
                        "Accept any response as a name — it may be a nickname, word, or unusual name.\n"
                        "Only return NULL if the user clearly refuses or says they don't want to share.\n"
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ]

            result = LLMService.generate_reply(prompt).strip()

            if not result or result.lower() == "null":
                return None

            if len(result) > 20:
                return None

            return result.capitalize()

        except Exception:
            return None

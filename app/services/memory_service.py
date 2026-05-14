from app.services.llm_service import client
from app.core.logging_config import get_logger
import json

logger = get_logger("memory")


class MemoryService:

    ALLOWED_TYPES = {
        "identity",
        "preference",
        "routine",
        "relationship",
        "plan",
        "state",
        "open_thread",
        "emotional_context",
        "boundary",
    }

    NON_ACTIONABLE_STATE_KEYS = {
        "none",
        "day",
        "weather",
        "location",
        "state",
        "mood",
        "state_day",
        "state_weather",
        "state_mood",
        "state_activity",
        "current_feeling",
        "completed_activity",
    }

    EMPTY_VALUES = {"none", "null", "unknown", ""}

    @staticmethod
    def extract_memory(message: str, context: str = "") -> list:
        try:
            context_block = f"\nRecent conversation context:\n{context}\n" if context else ""
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract meaningful memory from the user message.\n"
                            "Return a JSON array with fields: type, key, value.\n"
                            "Use the conversation context to understand what the user's message means.\n"
                            "If the context shows the user was asked for their name, treat the response as identity/name.\n\n"
                            "Memory types:\n"
                            "- identity: stable facts like name, job, lifestyle\n"
                            "- preference: likes, dislikes, interests\n"
                            "- routine: repeated habits or regular activities\n"
                            "- relationship: partner, family, friends, social context\n"
                            "- plan: future events or intentions\n"
                            "- state: current ongoing situation, temporary\n"
                            "- open_thread: unresolved thing worth gently following up on later\n"
                            "- emotional_context: topic plus the feeling attached to it\n"
                            "- boundary: things the user does not want, dislikes, or resists\n\n"
                            "State rules:\n"
                            "1. Use 'state' only for things happening right now.\n"
                            "2. Do not store past or completed actions as state.\n"
                            "3. If an activity is finished or no longer happening, return value 'none' for that activity key.\n"
                            "4. Use specific activity keys:\n"
                            "   reading -> activity_reading\n"
                            "   watching -> activity_watching\n"
                            "   work -> activity_work\n"
                            "   gym/fitness -> activity_fitness\n"
                            "   social -> activity_social\n\n"
                            "Name extraction rules:\n"
                            "- Only extract identity/name when the user is directly stating their own name (e.g. 'I am Nimbi', 'call me X', or responding to being asked their name).\n"
                            "- If a name appears in a sentence about someone else ('Kazi my boyfriend', 'my friend John'), extract it as a relationship, NOT as identity/name.\n"
                            "- A standalone word like 'Kazi' is only identity/name if the prior context shows the user was asked for their name.\n\n"
                            "Human-continuity rules:\n"
                            "- Use open_thread for unresolved stress, plans, conflicts, worries, or pending outcomes.\n"
                            "- Use emotional_context when a topic clearly carries a feeling.\n"
                            "- Use boundary when the user says they dislike a behavior or wants space.\n"
                            "- Keep values clean and natural, not full transcripts.\n"
                            "- Do not guess missing context.\n\n"
                            "Examples:\n"
                            "Input: 'I am watching Dark'\n"
                            "Output: [{\"type\":\"state\",\"key\":\"activity_watching\",\"value\":\"Dark\"}]\n\n"
                            "Input: 'I finished the book'\n"
                            "Output: [{\"type\":\"state\",\"key\":\"activity_reading\",\"value\":\"none\"}]\n\n"
                            "Input: 'work has been killing me this week'\n"
                            "Output: ["
                            "{\"type\":\"open_thread\",\"key\":\"work_stress\",\"value\":\"Work has been stressful this week\"},"
                            "{\"type\":\"emotional_context\",\"key\":\"work\",\"value\":\"Work is linked with stress right now\"}"
                            "]\n\n"
                            "Input: 'I hate when people keep asking if I am okay'\n"
                            "Output: [{\"type\":\"boundary\",\"key\":\"check_in_style\",\"value\":\"Avoid repeated direct 'are you okay' check-ins\"}]\n\n"
                            "Input: 'I like Linkin Park'\n"
                            "Output: [{\"type\":\"preference\",\"key\":\"music\",\"value\":\"Linkin Park\"}]\n\n"
                            "Final rules:\n"
                            "- Extract multiple items if present.\n"
                            "- Prefer no memory over weak memory.\n"
                            "- Use 'none' only to clear an existing state.\n"
                            "- Only return valid JSON.\n"
                        )
                    },
                    {
                        "role": "user",
                        "content": f"{context_block}User message: {message}"
                    }
                ],
                max_tokens=220
            )

            content = response.choices[0].message.content.strip()
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(content)

            return data if isinstance(data, list) else []

        except Exception as e:
            logger.exception(f"Memory extraction error: {e}")
            return []

    @staticmethod
    def save_memories(db, user_id: str, memories: list):

        from app.models.memory import Memory

        upsert_types = {"state", "open_thread", "boundary", "identity", "preference", "routine", "relationship", "emotional_context"}

        for mem in memories:
            try:
                mem_type = mem.get("type")
                key = mem.get("key")
                value = mem.get("value")

                if not mem_type or not key or not value:
                    continue

                mem_type = str(mem_type).strip()
                key = str(key).strip()
                value = str(value).strip()

                if not mem_type or not key or not value:
                    continue

                if mem_type not in MemoryService.ALLOWED_TYPES:
                    continue

                if key.lower() in MemoryService.EMPTY_VALUES:
                    continue

                if mem_type in upsert_types:
                    db.query(Memory).filter(
                        Memory.user_id == user_id,
                        Memory.type == mem_type,
                        Memory.key == key
                    ).delete()

                    if value.lower() == "none":
                        continue

                if value.lower() in MemoryService.EMPTY_VALUES:
                    continue

                if (
                    mem_type == "state"
                    and key.lower() in MemoryService.NON_ACTIONABLE_STATE_KEYS
                ):
                    continue

                if mem_type == "state" and "finished" in value.lower():
                    continue

                new_memory = Memory(
                    user_id=user_id,
                    type=mem_type,
                    key=key,
                    value=value
                )

                db.add(new_memory)

            except Exception as e:
                logger.warning(f"Memory save error for {user_id}: {e}")

        db.commit()

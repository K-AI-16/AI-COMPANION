from app.services.llm_service import client
from app.repositories.memory_repository import MemoryRepository
from app.utils.memory_filters import is_low_stakes_pivot


class PivotService:

    @staticmethod
    def generate(db, user_id: str) -> str | None:
        memories = MemoryRepository.get_user_memories(db, user_id, limit=30)
        boundaries = [m for m in memories if m.type == "boundary"]
        pivot_memories = [
            m for m in memories
            if is_low_stakes_pivot(m, boundary_memories=boundaries)
        ]

        known_types = {m.type for m in memories}
        unknown_areas = []
        if "identity" not in known_types:
            unknown_areas.append("their work or daily life")
        if "preference" not in known_types:
            unknown_areas.append("what they're into — sports, movies, music, food, books")
        if "routine" not in known_types:
            unknown_areas.append("how they spend their time")
        if "relationship" not in known_types:
            unknown_areas.append("who they spend time with")

        if pivot_memories:
            import random
            sample = random.sample(pivot_memories, min(3, len(pivot_memories)))
            topics_block = "Known interests to reference:\n" + "\n".join(
                f"- {m.key.replace('_', ' ')}: {m.value}" for m in sample
            )
        else:
            topics_block = ""

        gaps_block = ""
        if unknown_areas:
            gaps_block = "Things you don't know yet about this person:\n" + "\n".join(
                f"- {a}" for a in unknown_areas
            )

        prompt = (
            "You are Ari. The conversation has stalled — the user is disengaged or giving short replies.\n"
            "Your job: shift direction entirely. Introduce something new.\n\n"
            "What this is NOT:\n"
            "- Not a follow-up on the current topic\n"
            "- Not a generic 'what have you been up to' or 'done anything fun'\n"
            "- Not a wellness check\n"
            "- Not a list of questions — just one line\n\n"
            "What this IS:\n"
            "- A sudden, curious question that reveals Ari's genuine interest in this person\n"
            "- Grounded in something actually known about them (a preference, interest, or detail)\n"
            "- If nothing is known, ask something unexpected that says something about who they are\n"
            "- Under 12 words. Casual. Like Ari just thought of it.\n\n"
            + (topics_block + "\n\n" if topics_block else "")
            + (gaps_block + "\n\n" if gaps_block else "")
            + "Examples of the right energy:\n"
            "- 'okay random thought — do you follow cricket at all?'\n"
            "- 'what's something you'd never order at a restaurant?'\n"
            "- 'is there a show you've been meaning to watch but keep not watching?'\n\n"
            "Reply with just the message. No emojis."
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=30,
                temperature=1.1,
            )
            result = response.choices[0].message.content.strip()
            return result if result else None
        except Exception:
            return None

import random
from datetime import datetime

from app.services.llm_service import client
from app.core.personality_config import PERSONALITY_CONFIG
from app.core.prompt_config import PROACTIVE_PROMPT_CONFIG
from app.services.personality_builder import build_personality_prompt
from app.services.proactive_prompt_builder import ProactivePromptBuilder
from app.utils.memory_filters import is_actionable_state

personality_prompt = build_personality_prompt(PERSONALITY_CONFIG)


class TriggerService:

    @staticmethod
    def generate_trigger_message(
        insight: dict,
        memories: list,
        last_trigger=None,
        trigger_type: str = None
    ):

        now = datetime.now()

        time_context = (
            f"Time: {now.strftime('%I:%M %p')}\n"
            f"Day: {now.strftime('%A')}"
        )

        state_memories = [m for m in memories if is_actionable_state(m)]
        open_threads = [m for m in memories if m.type == "open_thread"]
        emotional_context = [m for m in memories if m.type == "emotional_context"]
        boundaries = [m for m in memories if m.type == "boundary"]
        other_memories = [
            m for m in memories
            if m.type not in ["state", "open_thread", "emotional_context", "boundary"]
        ]

        def format_memories(mem_list):
            formatted = []

            for m in mem_list:
                if not m.value:
                    continue

                value = m.value.strip()

                if len(value) < 3:
                    continue
                if len(value.split()) > 14:
                    continue

                formatted.append(f"- {value}")

            return "\n".join(formatted) if formatted else "None"

        state_context = format_memories(state_memories[:5])
        open_thread_context = format_memories(open_threads[:5])
        emotional_context_text = format_memories(emotional_context[:5])
        boundary_context = format_memories(boundaries[:5])
        if trigger_type in ["open_thread", "state_followup"]:
            memory_context = "None"
        else:
            memory_context = format_memories(other_memories[-5:])

        avoid_text = ""
        if last_trigger and getattr(last_trigger, "message", None):
            avoid_text = f"Do not repeat or paraphrase this message:\n{last_trigger.message}"

        prompt = ProactivePromptBuilder.build(
            personality_prompt=personality_prompt,
            trigger_type=trigger_type or "default",
            time_context=time_context,
            insight=insight,
            state_context=state_context,
            open_thread_context=open_thread_context,
            emotional_context_text=emotional_context_text,
            memory_context=memory_context,
            boundary_context=boundary_context,
            avoid_text=avoid_text,
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                max_tokens=50,
            )

            content = response.choices[0].message.content.strip()

            if not content or len(content) < 3:
                return TriggerService._fallback(trigger_type)

            if not TriggerService._passes_output_guard(content, trigger_type):
                return TriggerService._fallback(trigger_type)

            return content

        except Exception:
            return TriggerService._fallback(trigger_type)

    @staticmethod
    def infer_trigger_type(memories: list):
        open_threads = [m for m in memories if m.type == "open_thread"]
        state_memories = [m for m in memories if is_actionable_state(m)]

        if open_threads:
            return "open_thread"

        if state_memories:
            return "state_followup"

        return "default"

    @staticmethod
    def _passes_output_guard(content: str, trigger_type: str = None):
        lowered = content.lower()
        avoid_phrases = PROACTIVE_PROMPT_CONFIG["avoid_phrases"]

        if any(phrase.lower() in lowered for phrase in avoid_phrases):
            return False

        if trigger_type in ["open_thread", "state_followup"]:
            blocked_terms = PROACTIVE_PROMPT_CONFIG["blocked_topic_terms"]

            if any(term.lower() in lowered for term in blocked_terms):
                return False

        return True

    @staticmethod
    def _fallback(trigger_type: str = None):
        trigger_config = PROACTIVE_PROMPT_CONFIG["trigger_types"].get(
            trigger_type,
            PROACTIVE_PROMPT_CONFIG["trigger_types"]["default"]
        )

        return random.choice(trigger_config["fallbacks"])

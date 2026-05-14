from app.core.prompt_config import PROACTIVE_PROMPT_CONFIG


class ProactivePromptBuilder:

    @staticmethod
    def build(
        personality_prompt: str,
        trigger_type: str,
        time_context: str,
        insight: dict,
        state_context: str,
        open_thread_context: str,
        emotional_context_text: str,
        memory_context: str,
        boundary_context: str,
        avoid_text: str,
    ):
        config = PROACTIVE_PROMPT_CONFIG
        trigger_config = config["trigger_types"].get(
            trigger_type,
            config["trigger_types"]["default"]
        )

        base_rules = ProactivePromptBuilder._bullets(config["base_rules"])
        trigger_rules = ProactivePromptBuilder._bullets(trigger_config["rules"])
        avoid_phrases = ProactivePromptBuilder._bullets(config["avoid_phrases"])
        style_examples = ProactivePromptBuilder._bullets(config["style_examples"])

        return (
            personality_prompt
            + f"""

You are texting someone you know casually.

Goal:
{trigger_config["goal"]}.

Rules:
{base_rules}

Trigger-specific rules:
{trigger_rules}

Avoid these phrases:
{avoid_phrases}

Prefer this kind of shape:
{style_examples}

User context:
{time_context}

emotion: {insight.get("dominant_emotion")}
trend: {insight.get("emotion_trend")}

Current situation:
{state_context}

Open threads:
{open_thread_context}

Emotional context:
{emotional_context_text}

Past memory:
{memory_context}

Boundaries:
{boundary_context}

{avoid_text}

Generate one message.
"""
        )

    @staticmethod
    def _bullets(items):
        return "\n".join(f"- {item}" for item in items)

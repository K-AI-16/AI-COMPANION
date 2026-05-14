from app.core.prompt_config import CHAT_PROMPT_CONFIG


class ChatPromptBuilder:

    @staticmethod
    def build(
        personality_prompt: str,
        time_context: str,
        conversation_state: dict,
        state_context: str,
        open_thread_context: str,
        emotional_context_text: str,
        boundary_context: str,
        session_summary_context: str,
        memory_context: str,
        pivot_context: str,
        insight_context: str,
        intent_context: str,
        curiosity_hint: str = "None",
    ):
        config = CHAT_PROMPT_CONFIG

        base_rules = ChatPromptBuilder._bullets(config["base_rules"])
        tone_rules = ChatPromptBuilder._bullets(config["tone_rules"])
        avoid_phrases = ChatPromptBuilder._bullets(config["avoid_phrases"])
        style_examples = ChatPromptBuilder._bullets(config["style_examples"])
        state_name = (conversation_state or {}).get("state", "engaged")
        state_rules = config["conversation_states"].get(
            state_name,
            config["conversation_states"]["engaged"]
        )
        state_rules_text = ChatPromptBuilder._bullets(state_rules)

        return (
            personality_prompt
            + f"""

Chat reply standards:
{base_rules}

Tone:
{tone_rules}

Avoid these phrases:
{avoid_phrases}

Prefer this kind of shape:
{style_examples}

Conversation state:
- state: {state_name}
- confidence: {(conversation_state or {}).get("confidence", 0.0)}
- reason: {(conversation_state or {}).get("reason", "")}

State-specific behavior:
{state_rules_text}

Context:
{time_context}

Current situation:
{state_context}

Open threads:
{open_thread_context}

Emotional context:
{emotional_context_text}

Boundaries:
{boundary_context}

Recent sessions:
{session_summary_context}

Known about user:
{memory_context}

Low-stakes pivot candidates:
{pivot_context}

What you still want to learn about this user:
{curiosity_hint}

Signals:
{insight_context}
{intent_context}
"""
        )

    @staticmethod
    def _bullets(items):
        return "\n".join(f"- {item}" for item in items)

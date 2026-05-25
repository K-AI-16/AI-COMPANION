import re
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.repositories.message_repository import MessageRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.insight_repository import InsightRepository
from app.repositories.memory_repository import MemoryRepository

from app.services.llm_service import LLMService
from app.services.signal_service import SignalService
from app.services.insight_service import InsightService
from app.services.memory_service import MemoryService
from app.services.conversation_state_service import ConversationStateService

from app.repositories.user_state_repository import UserStateRepository
from app.services.onboarding_service import OnboardingService
from app.repositories.trigger_repository import TriggerRepository
from app.repositories.user_repository import UserRepository

from app.core.personality_config import PERSONALITY_CONFIG
from app.services.personality_builder import build_personality_prompt
from app.services.chat_prompt_builder import ChatPromptBuilder
from app.utils.memory_filters import is_actionable_state, is_low_stakes_pivot
from app.repositories.session_summary_repository import SessionSummaryRepository

class ConversationService:

    @staticmethod
    def handle_user_message(db: Session, user_id: str, message: str, client_time: str | None = None):

        # -------------------------------
        # 0. Ensure user exists and detect session gap before storing
        # -------------------------------
        UserRepository.mark_active(db, user_id)

        last_user_msg = MessageRepository.get_last_user_message(db, user_id)

        is_new_session = False

        if last_user_msg:
            time_diff = datetime.utcnow() - last_user_msg.created_at

            if time_diff > timedelta(hours=6):
                is_new_session = True

        # -------------------------------
        # 1. Store user message
        # -------------------------------
        user_msg = MessageRepository.create_message(db, user_id, "user", message)

        TriggerRepository.mark_as_responded(db, user_id)

        # -------------------------------
        # 2. Extract signal
        # -------------------------------
        signal_data = SignalService.extract_signal(message)
        signal_data["user_id"] = user_id
        signal_data["message_id"] = user_msg.id
        SignalRepository.create_signal(db, signal_data)

        conversation_state = ConversationStateService.classify(
            message,
            signal_data
        )

        # -------------------------------
        # 3. Update insights
        # -------------------------------
        insight_data = InsightService.compute_insights(db, user_id)

        if insight_data:
            InsightRepository.upsert_insight(db, insight_data)

        insight = InsightRepository.get_insight_by_user(db, user_id)
        latest_signal = SignalRepository.get_latest_signal(db, user_id)

        # -------------------------------
        # 4. Fetch context
        # -------------------------------
        recent_messages = MessageRepository.get_recent_messages(db, user_id, limit=20)
        all_memories = MemoryRepository.get_user_memories(db, user_id, limit=50)
        session_summaries = SessionSummaryRepository.get_recent(db, user_id, limit=3)

        # -------------------------------
        # 4b. Memory (with conversation context so extractor understands the message)
        # -------------------------------
        context_lines = [
            f"{m.role}: {m.content}"
            for m in reversed(recent_messages)
        ]
        memory_context_str = "\n".join(context_lines[-4:])  # last 4 turns is enough
        memories = MemoryService.extract_memory(message, context=memory_context_str)

        if memories:
            MemoryService.save_memories(db, user_id, memories)
            all_memories = MemoryRepository.get_user_memories(db, user_id, limit=50)

        # -------------------------------
        # 5b. Compute curiosity gaps + user mode
        # -------------------------------
        known_types = {m.type for m in all_memories}
        known_keys = {(m.type, m.key.lower()) for m in all_memories}
        memory_count = len(all_memories)
        is_new_user = memory_count < 4

        def missing(mtype, key):
            return (mtype, key) not in known_keys

        gaps = []

        # Identity
        if "identity" not in known_types:
            gaps.append("who they are and what they do for work")

        # Relationships
        if "relationship" not in known_types:
            gaps.append("who matters to them — friends, family, partner")

        # Routine
        if "routine" not in known_types:
            gaps.append("what their day-to-day looks like")

        # Entertainment & interests — check specific keys
        if missing("preference", "sports") and missing("preference", "football") and missing("preference", "cricket"):
            gaps.append("whether they follow any sports — football, cricket, anything")
        if missing("preference", "movies") and missing("preference", "films") and missing("preference", "cinema"):
            gaps.append("whether they watch movies or shows, and what kind")
        if missing("preference", "books") and missing("preference", "reading"):
            gaps.append("whether they read — books, articles, anything")
        if missing("preference", "music") and missing("preference", "music taste"):
            gaps.append("what kind of music they're into")
        if missing("preference", "food") and missing("preference", "cuisine"):
            gaps.append("what kind of food they like")

        # General preferences if none at all
        if "preference" not in known_types:
            gaps.append("what they genuinely enjoy or care about outside of work")

        if is_new_user and gaps:
            curiosity_hint = (
                "NEW USER — you barely know this person yet. Your job this conversation: find out who they actually are.\n"
                "After each reply, ask ONE specific natural question. Don't wait for the perfect opening — make one.\n"
                "Never ask two questions at once. Tie each question to something they said.\n"
                "Priority gaps to fill:\n"
                + "\n".join(f"- {g}" for g in gaps[:5])
            )
        elif gaps:
            gaps = gaps[:3]
            curiosity_hint = (
                "Things you don't know yet — learn these naturally when there's a real opening:\n"
                + "\n".join(f"- {g}" for g in gaps)
                + "\nTie it to something they said. Never ask out of thin air."
            )
        else:
            curiosity_hint = ""

        # -------------------------------
        # 6. Build LLM messages with session awareness
        # -------------------------------
        personality_prompt = build_personality_prompt(PERSONALITY_CONFIG)
        llm_messages = ConversationService._build_llm_messages(
            recent_messages,
            all_memories,
            insight,
            latest_signal,
            message,
            is_new_session,
            conversation_state,
            session_summaries,
            curiosity_hint,
            personality_prompt,
            client_time=client_time,
            is_new_user=is_new_user,
        )

        # -------------------------------
        # 7. Onboarding vs Normal
        # -------------------------------
        state = UserStateRepository.get_or_create(db, user_id)

        if state.stage != "DONE":
            reply_text = OnboardingService.handle(
                db,
                user_id,
                message,
                llm_messages
            )
        else:
            reply_text = LLMService.generate_reply(llm_messages)

        # -------------------------------
        # 8. Split, store, and return reply parts
        # -------------------------------
        reply_parts = ConversationService._split_reply(reply_text)

        for part in reply_parts:
            MessageRepository.create_message(db, user_id, "assistant", part)

        return {
            "replies": reply_parts,
            "conversation_state": conversation_state.get("state", "neutral") if isinstance(conversation_state, dict) else conversation_state,
        }

    # =========================================
    # Helper: Split reply into natural bubbles
    # =========================================
    @staticmethod
    def _split_reply(text: str) -> list:
        text = text.strip()

        # Use explicit LLM-provided splits first
        if "|||" in text:
            parts = [p.strip() for p in text.split("|||") if p.strip()]
            if len(parts) > 1:
                return parts

        # Short replies stay as one bubble
        if len(text) < 60:
            return [text]

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return [text]
        if len(sentences) == 2:
            return sentences
        # 3+ sentences → max 3 bubbles
        return [sentences[0], sentences[1], " ".join(sentences[2:])]

    # =========================================
    # Helper: Build LLM messages
    # =========================================
    @staticmethod
    def _build_llm_messages(
        recent_messages,
        memories,
        insight,
        signal,
        current_message,
        is_new_session,
        conversation_state,
        session_summaries=None,
        curiosity_hint="",
        personality_prompt="",
        client_time: str | None = None,
        is_new_user: bool = False,
    ):

        if client_time:
            time_context = f"Current time (user's local): {client_time}"
        else:
            now = datetime.utcnow()
            time_context = f"Current time (UTC): {now.strftime('%I:%M %p, %A')}"

        # -------------------------------
        # CHAT HISTORY
        # -------------------------------
        if is_new_session:
            chat_history = []
        else:
            recent_messages = list(reversed(recent_messages))
            chat_history = [
                {"role": m.role, "content": m.content}
                for m in recent_messages
            ]

        # -------------------------------
        # MEMORY SPLIT
        # -------------------------------
        state_memories = [m for m in memories if is_actionable_state(m)]
        open_threads = [m for m in memories if m.type == "open_thread"]
        emotional_context = [m for m in memories if m.type == "emotional_context"]
        boundaries = [m for m in memories if m.type == "boundary"]
        other_memories = [
            m for m in memories
            if m.type not in ["state", "open_thread", "emotional_context", "boundary"]
        ]
        pivot_memories = [m for m in other_memories if is_low_stakes_pivot(m, boundary_memories=boundaries)]

        # -------------------------------
        # CURRENT STATE
        # -------------------------------
        state_context = ""
        if state_memories:
            state_context = "Current situation:\n"
            for m in state_memories[:5]:
                readable_key = m.key.replace("_", " ")
                state_context += f"- {readable_key}: {m.value}\n"

        open_thread_context = ""
        if open_threads:
            open_thread_context = "Open threads worth gently following up on:\n"
            for m in open_threads[:5]:
                open_thread_context += f"- {m.value}\n"

        emotional_context_text = ""
        if emotional_context:
            emotional_context_text = "Emotional context:\n"
            for m in emotional_context[:5]:
                emotional_context_text += f"- {m.value}\n"

        boundary_context = ""
        if boundaries:
            boundary_context = "User boundaries and preferences:\n"
            for m in boundaries[:5]:
                boundary_context += f"- {m.value}\n"

        # -------------------------------
        # LONG TERM MEMORY
        # -------------------------------
        memory_context = ""
        if other_memories:
            if is_new_user:
                memory_context = "Known about user (very limited — still learning):\n"
            elif len(other_memories) >= 8:
                memory_context = (
                    "Known about user — you know them well. Use this to make the conversation "
                    "feel personal, not like you're meeting them for the first time. "
                    "Reference what you know naturally, like a friend who remembers:\n"
                )
            else:
                memory_context = "Known about user:\n"
            for m in other_memories[:8]:
                memory_context += f"- {m.value}\n"

        pivot_context = ""
        if pivot_memories:
            pivot_context = "Interesting light topics:\n"
            seen = set()

            for m in pivot_memories[:8]:
                value = m.value.strip()

                if value.lower() in seen:
                    continue

                seen.add(value.lower())
                readable_key = m.key.replace("_", " ")
                pivot_context += f"- {readable_key}: {value}\n"

        # -------------------------------
        # INSIGHT
        # -------------------------------
        insight_context = ""
        if insight:
            insight_context = (
                f"emotion: {insight.dominant_emotion}\n"
                f"trend: {insight.emotion_trend}\n"
                f"engagement: {insight.engagement_score}"
            )

        # -------------------------------
        # INTENT
        # -------------------------------
        intent_context = ""
        if signal:
            intent_context = f"intent: {signal.intent}"

        # -------------------------------
        # SESSION SUMMARIES
        # -------------------------------
        session_summary_context = ""
        if session_summaries:
            session_summary_context = "Recent sessions:\n"
            for s in reversed(session_summaries):
                session_summary_context += f"{s.summary}\n"

        # -------------------------------
        # SYSTEM PROMPT
        # -------------------------------
        system_prompt = ChatPromptBuilder.build(
            personality_prompt=personality_prompt,
            time_context=time_context,
            conversation_state=conversation_state,
            state_context=state_context or "None",
            open_thread_context=open_thread_context or "None",
            emotional_context_text=emotional_context_text or "None",
            boundary_context=boundary_context or "None",
            session_summary_context=session_summary_context or "None",
            memory_context=memory_context or "None",
            pivot_context=pivot_context or "None",
            insight_context=insight_context or "None",
            intent_context=intent_context or "None",
            curiosity_hint=curiosity_hint or "None",
            is_new_user=is_new_user,
        )

        return [
            {"role": "system", "content": system_prompt}
        ] + chat_history + [
            {"role": "user", "content": current_message}
        ]

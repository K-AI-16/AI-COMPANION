from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logging_config import setup_logging, get_logger
from app.services.conversation_service import ConversationService
import threading
import os
from app.services.scheduler_service import SchedulerService
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from pydantic import BaseModel
from app.repositories.trigger_repository import TriggerRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.message_repository import MessageRepository
from datetime import datetime

setup_logging()
logger = get_logger("main")

# Sentry — optional, only activates when SENTRY_DSN is set
_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if _SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
    )
    logger.info("Sentry initialised")

_DEBUG_TOKEN = os.getenv("DEBUG_TOKEN", "")


def require_debug_token(x_debug_token: str = Header(default="")):
    if not _DEBUG_TOKEN or x_debug_token != _DEBUG_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

from app.routers.whatsapp import router as whatsapp_router

app = FastAPI()
app.include_router(whatsapp_router)

app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "internal server error"})

class ChatRequest(BaseModel):
    user_id: str
    message: str


class ClassifyRequest(BaseModel):
    message: str


class NudgeRequest(BaseModel):
    user_id: str
    conversation_state: str


class PivotRequest(BaseModel):
    user_id: str

@app.on_event("startup")
def startup():
    from app.core.database import engine, Base
    from app.models.user import User
    from app.models.message import Message
    from app.models.signal import Signal
    from app.models.insight import Insight
    from app.models.trigger_log import TriggerLog
    from app.models.memory import Memory
    from app.models.user_state import UserState
    from app.models.session_summary import SessionSummary
    from app.models.push_subscription import PushSubscription
    from app.models.expo_push_token import ExpoPushToken
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    thread = threading.Thread(target=SchedulerService.run, daemon=True)
    thread.start()
    logger.info("Scheduler started")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": db_ok}

class PushSubscribeRequest(BaseModel):
    user_id: str
    subscription: dict  # { endpoint, keys: { p256dh, auth } }


class ExpoTokenRequest(BaseModel):
    user_id: str
    token: str


@app.get("/v1/push/status/{user_id}")
def push_status(user_id: str, db: Session = Depends(get_db)):
    from app.repositories.push_repository import PushRepository
    from app.repositories.expo_push_repository import ExpoPushRepository
    from app.repositories.message_repository import MessageRepository
    has_sub = PushRepository.get(db, user_id) is not None
    has_expo = ExpoPushRepository.get(db, user_id) is not None
    msg_count = len(MessageRepository.get_recent_messages(db, user_id, limit=100))
    should_ask = not (has_sub or has_expo) and msg_count >= 6
    return {"has_subscription": has_sub or has_expo, "should_ask": should_ask}


@app.post("/v1/push/subscribe")
def push_subscribe(request: PushSubscribeRequest, db: Session = Depends(get_db)):
    from app.repositories.push_repository import PushRepository
    keys = request.subscription.get("keys", {})
    PushRepository.save(
        db,
        user_id=request.user_id,
        endpoint=request.subscription.get("endpoint", ""),
        p256dh=keys.get("p256dh", ""),
        auth_key=keys.get("auth", ""),
    )
    return {"ok": True}


@app.delete("/v1/push/subscribe/{user_id}")
def push_unsubscribe(user_id: str, db: Session = Depends(get_db)):
    from app.repositories.push_repository import PushRepository
    PushRepository.delete(db, user_id)
    return {"ok": True}


@app.post("/v1/push/expo-token")
def expo_token_subscribe(request: ExpoTokenRequest, db: Session = Depends(get_db)):
    from app.repositories.expo_push_repository import ExpoPushRepository
    ExpoPushRepository.save(db, request.user_id, request.token)
    return {"ok": True}


@app.get("/v1/triggers/{user_id}")
def get_triggers(user_id: str, db: Session = Depends(get_db)):

    triggers = TriggerRepository.get_undelivered_triggers(db, user_id)

    response = []

    for t in triggers:
        response.append({
            "id": t.id,
            "message": t.message,
            "sent_at": t.sent_at
        })

        # mark delivered immediately
        TriggerRepository.mark_as_delivered(db, t.id)

    return response
@app.post("/v1/chat/messages")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    result = ConversationService.handle_user_message(
        db,
        request.user_id,
        request.message
    )
    # Push each reply bubble as a separate notification
    if result["replies"]:
        from app.services.push_service import PushService
        for reply in result["replies"]:
            PushService.send_expo_to_user(db, request.user_id, reply)
    return {
        "replies": result["replies"],
        "conversation_state": result["conversation_state"],
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/v1/chat/history/{user_id}")
def get_chat_history(user_id: str, limit: int = 30, db: Session = Depends(get_db)):
    messages = MessageRepository.get_recent_messages(db, user_id, limit=limit)
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in reversed(messages)
    ]


@app.post("/v1/chat/nudge")
def chat_nudge(request: NudgeRequest, db: Session = Depends(get_db)):
    from app.services.nudge_service import NudgeService
    if not NudgeService.should_nudge(request.conversation_state):
        return {"message": None, "skip": True}
    # Skip if user sent a message within the last 90 seconds — no point nudging
    if not NudgeService.should_nudge_by_time(db, request.user_id, min_silence_seconds=90):
        return {"message": None, "skip": True}
    message = NudgeService.generate(request.conversation_state, db, request.user_id)
    if message:
        MessageRepository.create_message(db, request.user_id, "assistant", message)
    return {"message": message, "skip": False}


@app.post("/v1/chat/pivot")
def chat_pivot(request: PivotRequest, db: Session = Depends(get_db)):
    from app.services.pivot_service import PivotService
    # Skip pivot if user was active within the last 5 minutes
    last_user_msg = MessageRepository.get_last_user_message(db, request.user_id)
    if last_user_msg:
        seconds_since = (datetime.utcnow() - last_user_msg.created_at).total_seconds()
        if seconds_since < 300:
            return {"message": None, "skip": True}
    message = PivotService.generate(db, request.user_id)
    if not message:
        return {"message": None, "skip": True}
    MessageRepository.create_message(db, request.user_id, "assistant", message)
    return {"message": message, "skip": False}


@app.get("/debug/memories/{user_id}")
def debug_memories(user_id: str, db: Session = Depends(get_db), _=Depends(require_debug_token)):
    memories = MemoryRepository.get_user_memories(db, user_id, limit=100)

    return [
        {
            "id": memory.id,
            "type": memory.type,
            "key": memory.key,
            "value": memory.value,
            "created_at": memory.created_at.isoformat()
            if memory.created_at else None
        }
        for memory in memories
    ]


@app.post("/debug/classify")
def debug_classify(request: ClassifyRequest, _=Depends(require_debug_token)):
    from app.services.conversation_state_service import ConversationStateService

    return ConversationStateService.classify(request.message)


@app.get("/debug/trigger-preview/{user_id}")
def debug_trigger_preview(
    user_id: str,
    force: bool = False,
    weekly_limit: int = 3,
    min_inactivity_hours: float = 8,
    hard_cooldown_hours: float = 12,
    followup_wait_hours: float = 24,
    score_threshold: float = 0.75,
    skip_randomness: bool = False,
    db: Session = Depends(get_db),
    _=Depends(require_debug_token)
):
    from app.models.insight import Insight
    from app.services.decision_service import DecisionService
    from app.services.trigger_service import TriggerService

    insight = db.query(Insight).filter(Insight.user_id == user_id).first()

    if not insight:
        return {
            "candidate": False,
            "error": "no insight found for user"
        }

    overrides = {
        "weekly_limit": weekly_limit,
        "min_inactivity_hours": min_inactivity_hours,
        "hard_cooldown_hours": hard_cooldown_hours,
        "followup_wait_hours": followup_wait_hours,
        "score_threshold": score_threshold,
        "skip_randomness": skip_randomness,
    }
    decision = DecisionService.evaluate(db, insight.__dict__, overrides=overrides)

    if not decision.get("candidate") and not force:
        return {
            "decision": decision,
            "message": None,
            "saved": False
        }

    memories = MemoryRepository.get_user_memories(db, user_id)
    last_trigger = TriggerRepository.get_last_trigger(db, user_id)
    trigger_type = decision.get("trigger_type")

    if force and not trigger_type:
        trigger_type = TriggerService.infer_trigger_type(memories)

    message = TriggerService.generate_trigger_message(
        insight.__dict__,
        memories,
        last_trigger,
        trigger_type
    )

    return {
        "decision": decision if not force else {
            **decision,
            "candidate": True,
            "forced": True,
            "trigger_type": trigger_type,
            "original_reason": decision.get("reason")
        },
        "message": message,
        "saved": False
    }


@app.get("/debug/decision/{user_id}")
def debug_decision(
    user_id: str,
    weekly_limit: int = 3,
    min_inactivity_hours: float = 8,
    hard_cooldown_hours: float = 12,
    followup_wait_hours: float = 24,
    score_threshold: float = 0.75,
    skip_randomness: bool = False,
    db: Session = Depends(get_db),
    _=Depends(require_debug_token)
):
    from app.models.insight import Insight
    from app.services.decision_service import DecisionService
    from app.services.trigger_service import TriggerService

    insight = db.query(Insight).filter(Insight.user_id == user_id).first()

    if not insight:
        return {"error": "no insight"}

    overrides = {
        "weekly_limit": weekly_limit,
        "min_inactivity_hours": min_inactivity_hours,
        "hard_cooldown_hours": hard_cooldown_hours,
        "followup_wait_hours": followup_wait_hours,
        "score_threshold": score_threshold,
        "skip_randomness": skip_randomness,
    }
    decision = DecisionService.evaluate(db, insight.__dict__, overrides=overrides)

    message = None

    if decision.get("candidate"):
        memories = MemoryRepository.get_user_memories(db, user_id)
        last_trigger = TriggerRepository.get_last_trigger(db, user_id)
        message = TriggerService.generate_trigger_message(
            insight.__dict__,
            memories,
            last_trigger,
            decision.get("trigger_type")
        )

    return {
        "decision": decision,
        "message": message,
        "saved": False
    }


@app.get("/debug/trigger-context/{user_id}")
def debug_trigger_context(user_id: str, db: Session = Depends(get_db), _=Depends(require_debug_token)):
    memories = MemoryRepository.get_user_memories(db, user_id, limit=100)

    buckets = {
        "state": [],
        "open_thread": [],
        "emotional_context": [],
        "boundary": [],
        "other": []
    }

    for memory in memories:
        item = {
            "id": memory.id,
            "type": memory.type,
            "key": memory.key,
            "value": memory.value,
            "created_at": memory.created_at.isoformat()
            if memory.created_at else None
        }

        if memory.type in buckets:
            buckets[memory.type].append(item)
        else:
            buckets["other"].append(item)

    return buckets


@app.post("/debug/trigger-inject/{user_id}")
def debug_trigger_inject(
    user_id: str,
    run_decision: bool = False,
    weekly_limit: int = 100,
    min_inactivity_hours: float = 0,
    hard_cooldown_hours: float = 0,
    followup_wait_hours: float = 0,
    score_threshold: float = 0.5,
    skip_randomness: bool = True,
    db: Session = Depends(get_db),
    _=Depends(require_debug_token)
):
    from app.models.insight import Insight
    from app.services.decision_service import DecisionService
    from app.services.trigger_service import TriggerService
    from app.repositories.trigger_repository import TriggerRepository

    insight = db.query(Insight).filter(Insight.user_id == user_id).first()
    if not insight:
        return {"error": "no insight found for user"}

    overrides = {
        "weekly_limit": weekly_limit,
        "min_inactivity_hours": min_inactivity_hours,
        "hard_cooldown_hours": hard_cooldown_hours,
        "followup_wait_hours": followup_wait_hours,
        "score_threshold": score_threshold,
        "skip_randomness": skip_randomness,
    }

    if run_decision:
        decision = DecisionService.evaluate(db, insight.__dict__, overrides=overrides)
        if not decision.get("candidate"):
            return {"candidate": False, "reason": decision.get("reason"), "saved": False}
        trigger_type = decision.get("trigger_type")
    else:
        decision = None
        trigger_type = None

    memories = MemoryRepository.get_user_memories(db, user_id)
    last_trigger = TriggerRepository.get_last_trigger(db, user_id)

    if not trigger_type:
        trigger_type = TriggerService.infer_trigger_type(memories)

    message = TriggerService.generate_trigger_message(
        insight.__dict__,
        memories,
        last_trigger,
        trigger_type
    )

    saved = TriggerRepository.create_trigger(
        db,
        user_id=user_id,
        trigger_type=trigger_type,
        message=message
    )

    from app.services.push_service import PushService
    push_sent = PushService.send_to_user(db, user_id, message)
    expo_sent = PushService.send_expo_to_user(db, user_id, message)

    return {
        "trigger_type": trigger_type,
        "message": message,
        "saved": saved is not None,
        "trigger_id": saved.id if saved else None,
        "push_sent": push_sent,
        "expo_sent": expo_sent,
        "decision": decision,
    }


@app.post("/debug/push-test/{user_id}")
def debug_push_test(user_id: str, message: str = "test push from Ari", db: Session = Depends(get_db), _=Depends(require_debug_token)):
    from app.services.push_service import PushService
    sent = PushService.send_to_user(db, user_id, message)
    return {"sent": sent}


@app.post("/debug/memories/{user_id}/cleanup")
def debug_cleanup_memories(user_id: str, db: Session = Depends(get_db), _=Depends(require_debug_token)):
    deleted = MemoryRepository.cleanup_low_quality_memories(db, user_id)

    return {
        "deleted_count": len(deleted),
        "deleted": deleted
    }


@app.delete("/debug/memories/entry/{memory_id}")
def debug_delete_memory(memory_id: str, db: Session = Depends(get_db), _=Depends(require_debug_token)):
    deleted = MemoryRepository.delete_memory(db, memory_id)
    if not deleted:
        return {"deleted": False, "error": "not found"}
    return {"deleted": True, "id": memory_id, "key": deleted.key, "value": deleted.value}

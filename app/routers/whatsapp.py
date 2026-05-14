import os
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.conversation_service import ConversationService
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/webhook")

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")


@router.get("/whatsapp")
def whatsapp_verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_incoming(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()

    try:
        entry = body["entry"][0]
        change = entry["changes"][0]["value"]
        messages = change.get("messages")

        if not messages:
            return {"status": "ok"}

        msg = messages[0]
        if msg.get("type") != "text":
            return {"status": "ok"}

        wa_id = msg["from"]
        text = msg["text"]["body"]
        message_id = msg["id"]

        background_tasks.add_task(_handle_message, wa_id, text, message_id)

    except (KeyError, IndexError):
        pass

    return {"status": "ok"}


def _handle_message(wa_id: str, text: str, message_id: str):
    db: Session = SessionLocal()
    try:
        user_id = f"wa_{wa_id}"

        WhatsAppService.mark_read(wa_id, message_id)

        result = ConversationService.handle_user_message(db, user_id, text)
        replies = result.get("replies", [])

        WhatsAppService.send_replies(wa_id, replies)

    except Exception as e:
        print(f"WhatsApp message handling error: {e}")
    finally:
        db.close()

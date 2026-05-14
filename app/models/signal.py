from sqlalchemy import Column, String, Float, DateTime
from app.core.database import Base
import uuid
from datetime import datetime

class Signal(Base):
    __tablename__ = "user_signals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    message_id = Column(String, nullable=False)

    emotion = Column(String)
    emotion_confidence = Column(Float)

    intent = Column(String)
    engagement = Column(String)

    confidence = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
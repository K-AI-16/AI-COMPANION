from sqlalchemy import Column, String, DateTime, Text
from app.core.database import Base
import uuid
from datetime import datetime


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

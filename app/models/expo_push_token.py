from sqlalchemy import Column, String, DateTime
from datetime import datetime
from uuid import uuid4
from app.core.database import Base


class ExpoPushToken(Base):
    __tablename__ = "expo_push_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, unique=True, index=True, nullable=False)
    token = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

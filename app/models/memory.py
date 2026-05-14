from sqlalchemy import Column, String, DateTime
from app.core.database import Base
import uuid
from datetime import datetime

class Memory(Base):
    __tablename__ = "user_memory"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)

    key = Column(String)    # e.g. "likes_activity"
    value = Column(String)  # e.g. "badminton"
    type = Column(String)   # preference, routine, relationship, plan, identity
    created_at = Column(DateTime, default=datetime.utcnow)
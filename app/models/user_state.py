from sqlalchemy import Column, String, Integer, Boolean, DateTime
from datetime import datetime
from app.core.database import Base


class UserState(Base):
    __tablename__ = "user_states"

    user_id = Column(String, primary_key=True)
    stage = Column(String, default="ONBOARDING")  # ONBOARDING / DONE
    message_count = Column(Integer, default=0)

    name = Column(String, nullable=True)
    name_captured = Column(Boolean, default=False)
    notification_prompted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
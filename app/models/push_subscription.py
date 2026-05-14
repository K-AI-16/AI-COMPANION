from sqlalchemy import Column, String, DateTime
from app.core.database import Base
import uuid
from datetime import datetime


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, unique=True)
    endpoint = Column(String, nullable=False)
    p256dh = Column(String, nullable=False)
    auth_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

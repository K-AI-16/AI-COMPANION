from sqlalchemy import Column, String, DateTime, Boolean
from app.core.database import Base
import uuid
from datetime import datetime

class TriggerLog(Base):
    __tablename__ = "trigger_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    trigger_type = Column(String)
    confidence = Column(String)
    message = Column(String) 
    sent_at = Column(DateTime, default=datetime.utcnow)
    responded = Column(Boolean, default=False)
    delivered = Column(Boolean, default=False)

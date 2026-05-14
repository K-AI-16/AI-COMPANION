from sqlalchemy import Column, String, DateTime
from app.core.database import Base
import uuid
from datetime import datetime

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # user / assistant
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
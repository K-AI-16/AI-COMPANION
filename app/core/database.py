from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()
from app.models.user import User
from app.models.message import Message
from app.models.signal import Signal
from sqlalchemy.orm import Session
from app.models.insight import Insight
from app.models.trigger_log import TriggerLog
from app.models.memory import Memory
from app.models.user_state import UserState
from app.models.session_summary import SessionSummary



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

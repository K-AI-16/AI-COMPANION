from app.core.database import engine, Base

# import models
from app.models.user import User
from app.models.message import Message
from app.models.signal import Signal
from app.models.insight import Insight
from app.models.trigger_log import TriggerLog
from app.models.memory import Memory
from app.models.user_state import UserState
from app.models.session_summary import SessionSummary
from app.models.push_subscription import PushSubscription
from app.models.expo_push_token import ExpoPushToken


print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done.")

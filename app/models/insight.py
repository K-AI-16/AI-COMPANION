from sqlalchemy import Column, String, Float
from app.core.database import Base

class Insight(Base):
    __tablename__ = "user_insights"

    user_id = Column(String, primary_key=True)
    dominant_emotion = Column(String)
    emotion_trend = Column(String)
    engagement_score = Column(Float)
    recency_score = Column(Float)
from app.models.insight import Insight

class InsightRepository:

    @staticmethod
    def upsert_insight(db, data: dict):
        existing = db.query(Insight).filter(
            Insight.user_id == data["user_id"]
        ).first()

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
        else:
            existing = Insight(**data)
            db.add(existing)

        db.commit()
        db.refresh(existing)
        return existing
    @staticmethod
    def get_insight_by_user(db, user_id: str):
        return (
            db.query(Insight)
            .filter(Insight.user_id == user_id)
            .first()
        )
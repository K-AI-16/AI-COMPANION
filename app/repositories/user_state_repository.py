from datetime import datetime

from app.models.user_state import UserState


class UserStateRepository:

    @staticmethod
    def get_or_create(db, user_id: str):
        state = db.query(UserState).filter(UserState.user_id == user_id).first()

        if not state:
            state = UserState(user_id=user_id)
            db.add(state)
            db.commit()
            db.refresh(state)

        return state

    @staticmethod
    def update(db, state: UserState):
        state.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(state)
        return state

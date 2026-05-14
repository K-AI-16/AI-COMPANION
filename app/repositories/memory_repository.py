from app.models.memory import Memory


class MemoryRepository:

    @staticmethod
    def create_memory(db, user_id: str, key: str, value: str,type: str):
        memory = Memory(
            user_id=user_id,
            key=key,
            value=value,
            type=type
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory

    @staticmethod
    def get_user_memories(db, user_id: str, limit: int = 50):
        return (
            db.query(Memory)
            .filter(Memory.user_id == user_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def upsert_by_key(db, user_id: str, type: str, key: str, value: str):
        existing = (
            db.query(Memory)
            .filter(Memory.user_id == user_id, Memory.type == type, Memory.key == key)
            .first()
        )
        if existing:
            existing.value = value
            db.commit()
            db.refresh(existing)
            return existing
        return MemoryRepository.create_memory(db, user_id, key, value, type)

    @staticmethod
    def delete_memory(db, memory_id: str):
        memory = db.query(Memory).filter(Memory.id == memory_id).first()

        if not memory:
            return None

        db.delete(memory)
        db.commit()
        return memory

    @staticmethod
    def cleanup_low_quality_memories(db, user_id: str):
        allowed_types = {
            "identity",
            "preference",
            "routine",
            "relationship",
            "plan",
            "state",
            "open_thread",
            "emotional_context",
            "boundary",
        }

        non_actionable_state_keys = {
            "none",
            "day",
            "weather",
            "location",
            "state",
            "mood",
            "state_day",
            "state_weather",
            "state_mood",
            "state_activity",
            "current_feeling",
            "completed_activity",
        }

        empty_values = {"none", "null", "unknown", ""}
        deleted = []

        memories = db.query(Memory).filter(Memory.user_id == user_id).all()

        for memory in memories:
            mem_type = (memory.type or "").strip()
            key = (memory.key or "").strip()
            value = (memory.value or "").strip()

            should_delete = False

            if mem_type not in allowed_types:
                should_delete = True
            elif key.lower() in empty_values:
                should_delete = True
            elif value.lower() in empty_values:
                should_delete = True
            elif mem_type == "state" and key.lower() in non_actionable_state_keys:
                should_delete = True
            elif mem_type == "state" and "finished" in value.lower():
                should_delete = True

            if should_delete:
                deleted.append({
                    "id": memory.id,
                    "type": memory.type,
                    "key": memory.key,
                    "value": memory.value,
                })
                db.delete(memory)

        db.commit()
        return deleted

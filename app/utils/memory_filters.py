NULL_VALUES = {"none", "null", "unknown"}

HEAVY_PIVOT_TERMS = {
    "work",
    "office",
    "stress",
    "stressed",
    "bad day",
    "relationship",
    "partner",
    "ex",
}


def is_actionable_state(memory) -> bool:
    if memory.type != "state":
        return False
    key = (memory.key or "").lower().strip()
    value = (memory.value or "").lower().strip()
    if not key or not value or value in NULL_VALUES:
        return False
    return True


def is_low_stakes_pivot(memory, boundary_memories=None) -> bool:
    if memory.type not in {"preference", "routine", "plan"}:
        return False
    key = (memory.key or "").lower().strip()
    value = (memory.value or "").lower().strip()
    if not key or not value or value in NULL_VALUES:
        return False
    combined = key + " " + value
    if any(term in combined for term in HEAVY_PIVOT_TERMS):
        return False
    if boundary_memories:
        for b in boundary_memories:
            boundary_words = set((b.value or "").lower().split())
            if len(boundary_words) > 1:
                memory_words = set(combined.split())
                if boundary_words & memory_words:
                    return False
    return True

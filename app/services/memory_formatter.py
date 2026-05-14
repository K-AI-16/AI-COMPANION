class MemoryFormatter:

    @staticmethod
    def format(memories):

        summary = {
            "identity": [],
            "routine": [],
            "preferences": [],
            "relationship": []
        }

        for m in memories:
            key = m.key.lower()
            value = m.value

            if m.type == "identity":
                summary["identity"].append(f"{key}: {value}")

            elif m.type == "routine":
                summary["routine"].append(value)

            elif m.type == "preference":
                summary["preferences"].append(value)

            elif m.type == "relationship":
                summary["relationship"].append(value)

        # build readable text
        result = ""

        if summary["identity"]:
            result += "Identity:\n- " + "\n- ".join(summary["identity"]) + "\n\n"

        if summary["routine"]:
            result += "Routine:\n- " + ", ".join(set(summary["routine"])) + "\n\n"

        if summary["preferences"]:
            result += "Preferences:\n- " + ", ".join(set(summary["preferences"])) + "\n\n"

        if summary["relationship"]:
            result += "Relationships:\n- " + ", ".join(set(summary["relationship"])) + "\n\n"

        return result.strip()
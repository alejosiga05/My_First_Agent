"""Ranks courses; credits, ECTS and timetable clashes are computed in code, never by the model."""


def summarize_credits(matches: list[dict], credits_needed: float) -> dict:
    """Sum ECTS of suggested matches. Unsure matches are counted separately; missing ECTS is ignored."""
    confirmed = sum(m["ects"] for m in matches if m.get("sure") and m.get("ects") is not None)
    unsure = sum(m["ects"] for m in matches if not m.get("sure") and m.get("ects") is not None)
    return {
        "confirmed_ects": confirmed,
        "unsure_ects": unsure,
        "credits_needed": credits_needed,
        "remaining": max(credits_needed - confirmed, 0),
    }

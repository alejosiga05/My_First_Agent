"""Labels and credit totals; credits and ECTS are computed in code, never by the model."""

from backend.retrieval import Document

NOT_SURE_TEXT = "Not sure – ask your coordinator"
MATCH_TEXT = "Match"
NO_CLEAR_MATCH_TEXT = "No clear match"
CLOSEST_PREFIX = "Closest Bocconi course: "
MASTER_WARNING = "Master course – check with your coordinator"
GRADUATE_LEVELS = {"graduate", "master", "postgraduate"}


def _fmt(value: float) -> str:
    return f"{value:g}"


def _is_graduate(level: str | None) -> bool:
    return bool(level) and level.strip().lower() in GRADUATE_LEVELS


def build_card(
    judgment: dict, home: Document, exchange: Document | None, study_level: str | None = None
) -> dict:
    """Turn the model's content judgment into a card; label, ECTS and level warning come from the files."""
    if exchange is None or not judgment.get("content_match"):
        label, label_text = "not_sure", NOT_SURE_TEXT
    elif exchange.ects is None or home.ects is None:
        label, label_text = "not_sure", NOT_SURE_TEXT
    elif exchange.ects >= home.ects:
        label, label_text = "match", MATCH_TEXT
    else:
        label = "credit_gap"
        label_text = (
            f"Same content – credits short: covers {_fmt(exchange.ects)} of "
            f"{_fmt(home.ects)} ECTS, check with your coordinator"
        )

    # A not_sure card must not look like a recommendation: the Bocconi course is only "closest".
    if label == "not_sure":
        title = NO_CLEAR_MATCH_TEXT
        closest_text = CLOSEST_PREFIX + exchange.course if exchange else None
    else:
        title, closest_text = exchange.course, None

    # Only a suggested course gets the warning; a missing or unknown Level line gives none.
    level_warning = None
    if label != "not_sure" and study_level == "Bachelor" and _is_graduate(exchange.level):
        level_warning = MASTER_WARNING

    return {
        "label": label,
        "label_text": label_text,
        "title": title,
        "closest_text": closest_text,
        "home_course": home.course,
        "home_ects": home.ects,
        "exchange_course": exchange.course if exchange else None,
        "ects": exchange.ects if exchange else None,
        "reason": judgment.get("reason") or "",
        "model_error": bool(judgment.get("model_error")),
        "level_warning": level_warning,
        "source_file": exchange.file if exchange else None,
        "source_url": exchange.source_url if exchange else None,
    }


def summarize_credits(cards: list[dict], credits_needed: float) -> dict:
    """match and credit_gap count with their exchange ECTS; not_sure cards are only counted as courses."""
    confirmed = sum(c["ects"] for c in cards if c["label"] != "not_sure" and c.get("ects") is not None)
    not_sure_count = sum(1 for c in cards if c["label"] == "not_sure")
    return {
        "confirmed_ects": confirmed,
        "not_sure_count": not_sure_count,
        "credits_needed": credits_needed,
        "remaining": max(credits_needed - confirmed, 0),
    }

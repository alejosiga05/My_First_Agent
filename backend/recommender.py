"""Labels and credit totals; credits and ECTS are computed in code, never by the model."""

from backend.retrieval import Document

NOT_SURE_TEXT = "Not sure – ask your coordinator"
MATCH_TEXT = "Match"


def _fmt(value: float) -> str:
    return f"{value:g}"


def build_card(judgment: dict, home: Document, exchange: Document | None) -> dict:
    """Turn the model's content judgment into a card; label and ECTS come from the files."""
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

    return {
        "label": label,
        "label_text": label_text,
        "home_course": home.course,
        "home_ects": home.ects,
        "exchange_course": exchange.course if exchange else None,
        "ects": exchange.ects if exchange else None,
        "reason": judgment.get("reason") or "",
        "model_error": bool(judgment.get("model_error")),
        "source_file": exchange.file if exchange else None,
        "source_url": exchange.source_url if exchange else None,
    }


def summarize_credits(cards: list[dict], credits_needed: float) -> dict:
    """match and credit_gap count with their exchange ECTS; not_sure is shown separately."""
    confirmed = sum(c["ects"] for c in cards if c["label"] != "not_sure" and c.get("ects") is not None)
    unsure = sum(c["ects"] for c in cards if c["label"] == "not_sure" and c.get("ects") is not None)
    return {
        "confirmed_ects": confirmed,
        "unsure_ects": unsure,
        "credits_needed": credits_needed,
        "remaining": max(credits_needed - confirmed, 0),
    }

"""Labels and credit totals; credits and ECTS are computed in code, never by the model."""

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

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


# --- Exchange residences: prices, filters and the date check, all in Python ---

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NEAR_MINUTES = 5
NO_RESIDENCE_FITS = "No Bocconi exchange residence fits – try the private housing websites"
DATE_WARNING = "Exchange residences cover only {period} – look at the private housing websites below"


def months_between(start: date, end: date) -> int:
    """Whole calendar months from start to end (a partial last month is not counted)."""
    months = (end.year - start.year) * 12 + end.month - start.month
    return months - 1 if end.day < start.day else months


def monthly_price(semester_eur: float, months: int) -> int:
    """Semester price per month, rounded half-up to whole euros."""
    return int((Decimal(str(semester_eur)) / months).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def walk_minutes(text: str) -> int | None:
    """Largest number of minutes in a walking-time text ("within 10-15 minutes" -> 15), or None."""
    match = re.search(r"([\d\s\-–]+)\s*minute", text or "")
    numbers = [int(n) for n in re.findall(r"\d+", match.group(1))] if match else []
    return max(numbers) if numbers else None


def _day_month(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def period_text(start: date, end: date) -> str:
    if start.year == end.year:
        return f"{_day_month(start)} – {_day_month(end)} {end.year}"
    return f"{_day_month(start)} {start.year} – {_day_month(end)} {end.year}"


def _residence(row: dict) -> dict | None:
    """One CSV row with prices computed; None when price or dates are missing or invalid."""
    try:
        start = date.fromisoformat(row["period_start"].strip())
        end = date.fromisoformat(row["period_end"].strip())
        semester = float(row["price_semester_eur"])
    except (KeyError, AttributeError, ValueError):
        return None
    months = months_between(start, end)
    if months < 1:
        return None
    return {
        "residence": row.get("residence", ""),
        "room_type": row.get("room_type", ""),
        "monthly_price_eur": monthly_price(semester, months),
        "price_semester_eur": int(semester) if semester.is_integer() else semester,
        "walking_time": row.get("walking_time", ""),
        "period_text": period_text(start, end),
        "bills_included": row.get("bills_included", ""),
        "source": row.get("source", ""),
        "_start": start,
        "_end": end,
    }


def compare_residences(
    rows: list[dict], max_budget: float | None, within_5_min: bool, until: date | None
) -> dict:
    """Filter by budget and walking time; warn when the student needs housing after the residences end."""
    all_rows = [r for r in (_residence(row) for row in rows) if r]
    if not all_rows:
        return {"residences": [], "date_warning": None, "message": None}

    date_warning = None
    last_end = max(r["_end"] for r in all_rows)
    if until and until > last_end:
        first_start = min(r["_start"] for r in all_rows)
        date_warning = DATE_WARNING.format(period=period_text(first_start, last_end))

    def near(r: dict) -> bool:
        minutes = walk_minutes(r["walking_time"])
        return minutes is not None and minutes <= NEAR_MINUTES

    kept = [
        r
        for r in all_rows
        if (max_budget is None or r["monthly_price_eur"] <= max_budget) and (not within_5_min or near(r))
    ]
    residences = [{k: v for k, v in r.items() if not k.startswith("_")} for r in kept]
    return {
        "residences": residences,
        "date_warning": date_warning,
        "message": None if residences else NO_RESIDENCE_FITS,
    }

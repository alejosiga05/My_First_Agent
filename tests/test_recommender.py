from backend.recommender import build_card, summarize_credits
from backend.retrieval import Document


def doc(course, ects, file, side):
    return Document(
        file=file,
        source_url=f"https://example.org/{course}",
        course=course,
        ects=ects,
        side=side,
        text="",
    )


HOME = doc("Home Marketing", 7.5, "data/courses/cbs_m.md", "home")


def judgment(content_match, reason="Same topics.", model_error=False):
    return {
        "exchange_course": "ignored, name comes from the file",
        "home_course": "Home Marketing",
        "reason": reason,
        "source_file": "data/courses/bocconi_m.md",
        "content_match": content_match,
        "model_error": model_error,
    }


def test_match_when_content_matches_and_credits_are_enough():
    exchange = doc("Exchange Marketing", 7.5, "data/courses/bocconi_m.md", "exchange")

    card = build_card(judgment(True), HOME, exchange)

    assert card["label"] == "match"
    assert card["exchange_course"] == "Exchange Marketing"
    assert card["ects"] == 7.5
    assert card["home_ects"] == 7.5
    assert card["source_url"] == "https://example.org/Exchange Marketing"
    assert card["source_file"] == "data/courses/bocconi_m.md"


def test_credit_gap_when_content_matches_but_credits_short():
    exchange = doc("Exchange Marketing", 6, "data/courses/bocconi_m.md", "exchange")

    card = build_card(judgment(True), HOME, exchange)

    assert card["label"] == "credit_gap"
    assert card["label_text"] == (
        "Same content – credits short: covers 6 of 7.5 ECTS, check with your coordinator"
    )


def test_not_sure_when_content_does_not_match():
    exchange = doc("Exchange Marketing", 10, "data/courses/bocconi_m.md", "exchange")

    card = build_card(judgment(False), HOME, exchange)

    assert card["label"] == "not_sure"
    assert card["label_text"] == "Not sure – ask your coordinator"


def test_model_error_reason_is_kept_on_card():
    exchange = doc("Exchange Marketing", 6, "data/courses/bocconi_m.md", "exchange")

    card = build_card(judgment(False, reason="Model unavailable", model_error=True), HOME, exchange)

    assert card["label"] == "not_sure"
    assert card["reason"] == "Model unavailable"
    assert card["model_error"] is True


def test_not_sure_without_any_exchange_course():
    card = build_card(judgment(False, reason="Nothing found."), HOME, None)

    assert card["label"] == "not_sure"
    assert card["exchange_course"] is None
    assert card["ects"] is None
    assert card["source_url"] is None


def test_credit_gap_counts_and_not_sure_does_not():
    cards = [
        {"label": "match", "ects": 7.5},
        {"label": "credit_gap", "ects": 6},
        {"label": "not_sure", "ects": 6},
    ]

    summary = summarize_credits(cards, credits_needed=30)

    assert summary == {
        "confirmed_ects": 13.5,
        "unsure_ects": 6,
        "credits_needed": 30,
        "remaining": 16.5,
    }


def test_missing_ects_is_ignored_not_guessed():
    cards = [{"label": "not_sure", "ects": None}, {"label": "match", "ects": 6}]

    summary = summarize_credits(cards, credits_needed=6)

    assert summary["confirmed_ects"] == 6
    assert summary["unsure_ects"] == 0
    assert summary["remaining"] == 0


def test_remaining_never_goes_below_zero():
    summary = summarize_credits([{"label": "match", "ects": 10}], credits_needed=5)

    assert summary["remaining"] == 0


def test_no_matches_gives_zero_totals():
    summary = summarize_credits([], credits_needed=30)

    assert summary["confirmed_ects"] == 0
    assert summary["unsure_ects"] == 0
    assert summary["remaining"] == 30

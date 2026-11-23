from backend.recommender import summarize_credits


def test_unsure_matches_are_counted_separately():
    matches = [
        {"ects": 6, "sure": True},
        {"ects": 5, "sure": True},
        {"ects": 4, "sure": False},
    ]

    summary = summarize_credits(matches, credits_needed=30)

    assert summary == {
        "confirmed_ects": 11,
        "unsure_ects": 4,
        "credits_needed": 30,
        "remaining": 19,
    }


def test_missing_ects_is_ignored_not_guessed():
    matches = [{"ects": None, "sure": True}, {"ects": 6, "sure": True}]

    summary = summarize_credits(matches, credits_needed=6)

    assert summary["confirmed_ects"] == 6
    assert summary["remaining"] == 0


def test_remaining_never_goes_below_zero():
    summary = summarize_credits([{"ects": 10, "sure": True}], credits_needed=5)

    assert summary["remaining"] == 0


def test_no_matches_gives_zero_totals():
    summary = summarize_credits([], credits_needed=30)

    assert summary["confirmed_ects"] == 0
    assert summary["unsure_ects"] == 0
    assert summary["remaining"] == 30

"""Compare Bocconi exchange residences: prices, filters and date check in Python. Fixture CSV only; no model."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import llm, main, retrieval
from backend.main import app
from backend.recommender import months_between, monthly_price, walk_minutes

LISTS = Path(__file__).parent / "fixtures" / "lists"
RESIDENCES = LISTS / "test_exchange_residences.csv"
MISSING = LISTS / "does_not_exist.csv"
SOURCE = "https://example.org/housing/residences"
DATE_WARNING = (
    "Exchange residences cover only 24 Aug – 24 Dec 2026 – look at the private housing websites below"
)
NO_FIT = "No Bocconi exchange residence fits – try the private housing websites"

client = TestClient(app)


@pytest.fixture(autouse=True)
def fixture_file_and_no_model(monkeypatch):
    monkeypatch.setattr(main, "RESIDENCES_FILE", RESIDENCES)

    def no_model():
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(llm, "_client", no_model)


def get(**params):
    response = client.get("/api/housing/residences", params=params)
    assert response.status_code == 200
    return response.json()


# --- Parser and maths ---


def test_parser_returns_rows_with_source():
    rows = retrieval.exchange_residences(RESIDENCES)

    assert [r["residence"] for r in rows] == ["Test Near House", "Test Near House", "Test Far Hall"]
    assert rows[0]["price_semester_eur"] == "4770"
    assert rows[0]["source"] == SOURCE
    assert rows[0]["file"] == "tests/fixtures/lists/test_exchange_residences.csv"


def test_missing_file_gives_no_rows():
    assert retrieval.exchange_residences(MISSING) == []


def test_months_between_counts_whole_months():
    assert months_between(date(2026, 8, 24), date(2026, 12, 24)) == 4
    assert months_between(date(2026, 8, 24), date(2026, 12, 23)) == 3
    assert months_between(date(2026, 9, 1), date(2027, 2, 1)) == 5


def test_monthly_price_rounds_half_up_to_whole_euros():
    assert monthly_price(4770, 4) == 1193
    assert monthly_price(3025, 4) == 756
    assert monthly_price(4000, 4) == 1000


def test_walk_minutes_takes_the_largest_number():
    assert walk_minutes("about 5 minutes walk to campus") == 5
    assert walk_minutes("within 10-15 minutes walk") == 15
    assert walk_minutes("close to campus") is None


# --- Endpoint ---


def test_no_filters_returns_every_row_with_python_prices():
    body = get()

    assert [r["monthly_price_eur"] for r in body["residences"]] == [1193, 756, 1000]
    first = body["residences"][0]
    assert first == {
        "residence": "Test Near House",
        "room_type": "Single room (ensuite)",
        "monthly_price_eur": 1193,
        "price_semester_eur": 4770,
        "walking_time": "about 5 minutes walk to campus",
        "period_text": "24 Aug – 24 Dec 2026",
        "bills_included": "yes",
        "source": SOURCE,
    }
    assert body["date_warning"] is None
    assert body["message"] is None


def test_budget_hides_rows_over_budget_and_keeps_equal():
    body = get(max_budget=1000)

    assert [r["monthly_price_eur"] for r in body["residences"]] == [756, 1000]
    assert body["message"] is None


def test_only_within_five_minutes():
    body = get(within_5_min="true")

    assert {r["residence"] for r in body["residences"]} == {"Test Near House"}
    assert len(body["residences"]) == 2


def test_end_date_after_period_end_warns_and_keeps_rows():
    body = get(until="2027-01-31")

    assert body["date_warning"] == DATE_WARNING
    assert len(body["residences"]) == 3


def test_end_date_on_period_end_gives_no_warning():
    assert get(until="2026-12-24")["date_warning"] is None


def test_nothing_fits_gives_message():
    body = get(max_budget=100)

    assert body["residences"] == []
    assert body["message"] == NO_FIT


def test_filters_combined():
    body = get(max_budget=800, within_5_min="true", until="2027-01-31")

    assert [r["monthly_price_eur"] for r in body["residences"]] == [756]
    assert body["date_warning"] == DATE_WARNING


def test_bad_filters_give_422():
    assert client.get("/api/housing/residences", params={"until": "not-a-date"}).status_code == 422
    assert client.get("/api/housing/residences", params={"max_budget": -5}).status_code == 422


def test_missing_file_returns_empty_list(monkeypatch):
    monkeypatch.setattr(main, "RESIDENCES_FILE", MISSING)

    body = get(until="2027-01-31")

    assert body == {"residences": [], "date_warning": None, "message": None}

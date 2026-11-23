import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "sample_matches.json"

VALID_REQUEST = {
    "home_university": "Home University",
    "exchange_university": "Partner University",
    "home_courses": ["Introduction to Machine Learning", "Databases", "Academic Writing"],
    "credits_needed": 30,
    "question": "Which courses are taught in English?",
}

client = TestClient(app)


def test_match_returns_sample_matches():
    response = client.post("/api/match", json=VALID_REQUEST)

    assert response.status_code == 200
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["matches"]
    assert response.json()["matches"] == expected


def test_match_summary_is_computed_in_python():
    response = client.post("/api/match", json=VALID_REQUEST)

    assert response.json()["summary"] == {
        "confirmed_ects": 17,
        "unsure_ects": 6,
        "credits_needed": 30,
        "remaining": 13,
    }


def test_every_match_cites_a_file_in_data():
    matches = client.post("/api/match", json=VALID_REQUEST).json()["matches"]

    assert matches
    for match in matches:
        assert match["source"].startswith("data/")


def test_question_is_optional():
    body = {k: v for k, v in VALID_REQUEST.items() if k != "question"}

    assert client.post("/api/match", json=body).status_code == 200


def test_missing_credits_is_rejected():
    body = {k: v for k, v in VALID_REQUEST.items() if k != "credits_needed"}

    assert client.post("/api/match", json=body).status_code == 422


def test_non_positive_credits_is_rejected():
    body = {**VALID_REQUEST, "credits_needed": 0}

    assert client.post("/api/match", json=body).status_code == 422


def test_source_links_can_be_opened():
    matches = client.post("/api/match", json=VALID_REQUEST).json()["matches"]

    for source in {m["source"] for m in matches}:
        assert client.get("/" + source).status_code == 200

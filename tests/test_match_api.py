"""API tests. Courses come from tests/fixtures; llm.judge_match is mocked."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import llm, main
from backend.main import app

FIXTURES = Path(__file__).parent / "fixtures"
JUDGMENTS = json.loads((FIXTURES / "sample_matches.json").read_text(encoding="utf-8"))["judgments"]

VALID_REQUEST = {
    "home_university": "Test Home School",
    "exchange_university": "Test Exchange University",
    "home_courses": ["Test Marketing", "Test Corporate Finance"],
    "credits_needed": 30,
    "question": "Which courses are taught in English?",
}

client = TestClient(app)


@pytest.fixture(autouse=True)
def fixture_data_and_fake_model(monkeypatch):
    monkeypatch.setattr(main, "COURSES_DIR", FIXTURES / "courses")

    def fake_judge(home_doc, candidates):
        return {**JUDGMENTS[home_doc.course], "model_error": False}

    monkeypatch.setattr(llm, "judge_match", fake_judge)


def post(body=VALID_REQUEST):
    return client.post("/api/match", json=body)


def test_home_courses_lists_fixture_home_courses():
    response = client.get("/api/home-courses")

    assert response.status_code == 200
    assert sorted(response.json()["home_courses"]) == ["Test Corporate Finance", "Test Marketing"]


def test_one_card_per_home_course_with_python_labels():
    matches = post().json()["matches"]

    by_home = {m["home_course"]: m for m in matches}
    assert set(by_home) == {"Test Marketing", "Test Corporate Finance"}
    assert by_home["Test Marketing"]["label"] == "credit_gap"
    assert by_home["Test Marketing"]["label_text"] == (
        "Same content – credits short: covers 6 of 7.5 ECTS, check with your coordinator"
    )
    assert by_home["Test Corporate Finance"]["label"] == "match"


def test_summary_is_computed_in_python():
    assert post().json()["summary"] == {
        "confirmed_ects": 13.5,
        "unsure_ects": 0,
        "credits_needed": 30,
        "remaining": 16.5,
    }


def test_source_link_is_official_url_from_file():
    matches = post().json()["matches"]

    by_home = {m["home_course"]: m for m in matches}
    assert by_home["Test Marketing"]["source_url"] == "https://example.org/bocconi/marketing"
    assert by_home["Test Marketing"]["source_file"] == "tests/fixtures/courses/bocconi_test_marketing.md"


def test_not_sure_does_not_count(monkeypatch):
    def fake_judge(home_doc, candidates):
        return {**JUDGMENTS[home_doc.course], "content_match": False, "model_error": False}

    monkeypatch.setattr(llm, "judge_match", fake_judge)

    response = post().json()

    assert {m["label"] for m in response["matches"]} == {"not_sure"}
    assert response["summary"]["confirmed_ects"] == 0


def test_unknown_home_course_is_rejected():
    body = {**VALID_REQUEST, "home_courses": ["Invented Course"]}

    assert post(body).status_code == 422


def test_question_is_optional():
    body = {k: v for k, v in VALID_REQUEST.items() if k != "question"}

    assert post(body).status_code == 200


def test_missing_credits_is_rejected():
    body = {k: v for k, v in VALID_REQUEST.items() if k != "credits_needed"}

    assert post(body).status_code == 422


def test_non_positive_credits_is_rejected():
    body = {**VALID_REQUEST, "credits_needed": 0}

    assert post(body).status_code == 422

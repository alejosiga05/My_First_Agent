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
    "home_university": "Copenhagen Business School",
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


def test_home_courses_are_grouped_by_home_university():
    response = client.get("/api/home-courses")

    assert response.status_code == 200
    groups = response.json()["home_universities"]
    assert [g["name"] for g in groups] == ["Copenhagen Business School", "WU Vienna"]
    assert sorted(groups[0]["courses"]) == ["Test Corporate Finance", "Test Marketing"]
    assert groups[1]["courses"] == ["Test IFRS Accounting"]


def test_wu_request_is_accepted():
    body = {**VALID_REQUEST, "home_university": "WU Vienna", "home_courses": ["Test IFRS Accounting"]}

    response = post(body)

    assert response.status_code == 200
    assert [m["home_course"] for m in response.json()["matches"]] == ["Test IFRS Accounting"]


def test_course_from_other_home_university_is_rejected():
    body = {**VALID_REQUEST, "home_courses": ["Test Marketing", "Test IFRS Accounting"]}

    assert post(body).status_code == 422


def test_unknown_home_university_is_rejected():
    body = {**VALID_REQUEST, "home_university": "Invented University"}

    assert post(body).status_code == 422


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
        "not_sure_count": 0,
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
    assert response["summary"]["not_sure_count"] == 2


def test_not_sure_card_title_is_not_a_recommendation(monkeypatch):
    def fake_judge(home_doc, candidates):
        return {**JUDGMENTS[home_doc.course], "content_match": False, "model_error": False}

    monkeypatch.setattr(llm, "judge_match", fake_judge)

    by_home = {m["home_course"]: m for m in post().json()["matches"]}
    card = by_home["Test Marketing"]

    assert card["title"] == "No clear match"
    assert card["closest_text"] == "Closest Bocconi course: Exchange Marketing"
    assert card["source_url"] == "https://example.org/bocconi/marketing"


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


def test_profile_is_optional_and_gives_no_warnings():
    matches = post().json()["matches"]

    assert all(m["level_warning"] is None for m in matches)


def test_profile_values_are_accepted():
    for level in ("Bachelor", "Master"):
        for semester in ("Fall 2026", "Spring 2027"):
            body = {**VALID_REQUEST, "study_level": level, "semester": semester}
            assert post(body).status_code == 200


def test_unknown_study_level_is_rejected():
    assert post({**VALID_REQUEST, "study_level": "PhD"}).status_code == 422


def test_unknown_semester_is_rejected():
    assert post({**VALID_REQUEST, "semester": "Spring 2026"}).status_code == 422


def test_bachelor_sees_warning_on_graduate_course(monkeypatch):
    def fake_judge(home_doc, candidates):
        judgment = {**JUDGMENTS[home_doc.course], "model_error": False}
        if home_doc.course == "Test Corporate Finance":
            judgment["source_file"] = "tests/fixtures/courses/bocconi_test_graduate.md"
        return judgment

    monkeypatch.setattr(llm, "judge_match", fake_judge)

    by_home = {m["home_course"]: m for m in post({**VALID_REQUEST, "study_level": "Bachelor"}).json()["matches"]}

    assert by_home["Test Corporate Finance"]["level_warning"] == "Master course – check with your coordinator"
    assert by_home["Test Marketing"]["level_warning"] is None

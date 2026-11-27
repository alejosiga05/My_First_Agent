"""/api/ask tests. Files come from tests/fixtures; the model client is faked, so no network calls."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import llm, main
from backend.main import app

FIXTURES = Path(__file__).parent / "fixtures"
EXCHANGE_HOUSING_FILE = "tests/fixtures/housing/test_exchange_housing.md"

client = TestClient(app)


class FakeClient:
    """Mimics client.chat.completions.create and records the prompt."""

    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.messages = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.messages = kwargs["messages"]
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture(autouse=True)
def fixture_sections(monkeypatch):
    monkeypatch.setattr(main, "SECTION_DIRS", {"housing": FIXTURES / "housing", "clubs": FIXTURES / "clubs"})


def use_model(monkeypatch, content=None, error=None):
    fake = FakeClient(content=content, error=error)
    monkeypatch.setattr(llm, "_client", lambda: fake)
    return fake


def reply(**overrides):
    body = {
        "answer": "Residence Alpha costs EUR 4,000 for the semester.",
        "sources": [EXCHANGE_HOUSING_FILE],
        "found": True,
    }
    return json.dumps({**body, **overrides})


def post(section="housing", question="How much do the residences cost?"):
    return client.post("/api/ask", json={"section": section, "question": question})


def test_answer_has_sources_with_official_urls(monkeypatch):
    use_model(monkeypatch, content=reply())

    response = post()

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["model_error"] is False
    assert body["answer"] == "Residence Alpha costs EUR 4,000 for the semester."
    assert body["sources"] == [
        {
            "file": EXCHANGE_HOUSING_FILE,
            "title": "Test housing for exchange students",
            "url": "https://example.org/housing/exchange",
        }
    ]


def test_housing_question_only_sees_housing_files(monkeypatch):
    fake = use_model(monkeypatch, content=reply())

    post(question="Which clubs and residences are there?")

    prompt = " ".join(m["content"] for m in fake.messages)
    assert "tests/fixtures/housing/" in prompt
    assert "tests/fixtures/clubs/" not in prompt


def test_clubs_question_only_sees_clubs_files(monkeypatch):
    fake = use_model(monkeypatch, content=reply(sources=["tests/fixtures/clubs/test_associations.md"]))

    body = post(section="clubs", question="I like finance and football").json()

    prompt = " ".join(m["content"] for m in fake.messages)
    assert "tests/fixtures/housing/" not in prompt
    assert body["sources"][0]["url"] == "https://example.org/clubs/list"


def test_not_found_shows_dont_know_and_closest_sources(monkeypatch):
    use_model(monkeypatch, content=reply(answer="Probably cheap.", sources=[], found=False))

    body = post(question="How much does the residence cost?").json()

    assert body["found"] is False
    assert body["answer"] == (
        "I don't know – please ask the Bocconi International Student Desk or Housing Office"
    )
    assert body["sources"], "closest sources should be listed"
    assert body["sources"][0]["url"] == "https://example.org/housing/exchange"
    official = {"https://example.org/housing/exchange", "https://example.org/housing/private"}
    assert {s["url"] for s in body["sources"]} <= official


def test_invented_url_is_removed_from_answer(monkeypatch):
    use_model(monkeypatch, content=reply(answer="Pay the deposit at https://evil.example.com/pay today."))

    answer = post().json()["answer"]

    assert "evil.example.com" not in answer


def test_model_error_shows_model_unavailable(monkeypatch):
    use_model(monkeypatch, error=RuntimeError("boom"))

    body = post().json()

    assert body["model_error"] is True
    assert body["found"] is False
    assert body["answer"] == "Model unavailable – could not answer"
    assert body["sources"][0]["url"] == "https://example.org/housing/exchange"


def test_unknown_section_is_rejected(monkeypatch):
    use_model(monkeypatch, content=reply())

    assert post(section="sports").status_code == 422


def test_empty_question_is_rejected(monkeypatch):
    use_model(monkeypatch, content=reply())

    assert post(question="   ").status_code == 422

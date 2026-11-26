"""llm.py tests. The OpenAI client is always replaced; no network calls."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend import llm
from backend.retrieval import load_documents, search

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "courses"
MARKETING_FILE = "tests/fixtures/courses/bocconi_test_marketing.md"


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


@pytest.fixture
def home_and_candidates():
    docs = load_documents(FIXTURE_DIR)
    home = next(d for d in docs if d.course == "Test Marketing")
    return home, search(home, docs, k=3)


def use_client(monkeypatch, client):
    monkeypatch.setattr(llm, "_client", lambda: client)


def answer(**overrides):
    body = {
        "exchange_course": "Exchange Marketing",
        "home_course": "Test Marketing",
        "reason": "Same STP and branding topics.",
        "source_file": MARKETING_FILE,
        "content_match": True,
    }
    return json.dumps({**body, **overrides})


def test_returns_parsed_judgment(monkeypatch, home_and_candidates):
    use_client(monkeypatch, FakeClient(content=answer()))

    result = llm.judge_match(*home_and_candidates)

    assert result["content_match"] is True
    assert result["source_file"] == MARKETING_FILE
    assert result["reason"] == "Same STP and branding topics."
    assert result["model_error"] is False


def test_result_never_contains_credits(monkeypatch, home_and_candidates):
    use_client(monkeypatch, FakeClient(content=answer(ects=99, credits=99)))

    result = llm.judge_match(*home_and_candidates)

    assert "ects" not in result
    assert "credits" not in result


def test_unknown_source_file_is_not_a_match(monkeypatch, home_and_candidates):
    use_client(monkeypatch, FakeClient(content=answer(source_file="data/courses/invented.md")))

    result = llm.judge_match(*home_and_candidates)

    assert result["content_match"] is False


def test_non_boolean_content_match_is_not_a_match(monkeypatch, home_and_candidates):
    use_client(monkeypatch, FakeClient(content=answer(content_match="yes")))

    assert llm.judge_match(*home_and_candidates)["content_match"] is False


def test_bad_json_reports_model_unavailable(monkeypatch, home_and_candidates):
    use_client(monkeypatch, FakeClient(content="not json"))

    result = llm.judge_match(*home_and_candidates)

    assert result["content_match"] is False
    assert result["model_error"] is True
    assert result["reason"] == llm.MODEL_UNAVAILABLE


def test_api_error_reports_model_unavailable_and_logs_type_only(monkeypatch, caplog, home_and_candidates):
    use_client(monkeypatch, FakeClient(error=RuntimeError("secret-detail sk-123")))

    result = llm.judge_match(*home_and_candidates)

    assert result["content_match"] is False
    assert result["model_error"] is True
    assert result["reason"] == llm.MODEL_UNAVAILABLE
    assert "RuntimeError" in caplog.text
    assert "sk-123" not in caplog.text


def test_missing_api_key_reports_model_unavailable(monkeypatch, home_and_candidates):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = llm.judge_match(*home_and_candidates)

    assert result["model_error"] is True
    assert result["content_match"] is False


def test_no_candidates_skips_the_model(monkeypatch, home_and_candidates):
    client = FakeClient(content=answer())
    use_client(monkeypatch, client)

    result = llm.judge_match(home_and_candidates[0], [])

    assert result["content_match"] is False
    assert client.messages is None


def test_prompt_contains_home_and_candidate_texts(monkeypatch, home_and_candidates):
    client = FakeClient(content=answer())
    use_client(monkeypatch, client)

    llm.judge_match(*home_and_candidates)

    prompt = " ".join(m["content"] for m in client.messages)
    assert "Branding and consumer behaviour" in prompt
    assert MARKETING_FILE in prompt
    assert "Branding, pricing and consumer behaviour" in prompt

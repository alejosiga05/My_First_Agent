"""llm.py tests. The OpenAI client is always replaced; no network calls."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend import llm
from backend.retrieval import load_documents, load_info_documents, search, search_question

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "courses"
MARKETING_FILE = "tests/fixtures/courses/bocconi_test_marketing.md"
HOUSING_DIR = Path(__file__).parent / "fixtures" / "housing"
EXCHANGE_HOUSING_FILE = "tests/fixtures/housing/test_exchange_housing.md"
PRIVATE_HOUSING_FILE = "tests/fixtures/housing/test_private_housing.md"


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


# --- answer_question (Housing and Clubs sections) ---


@pytest.fixture
def housing_chunks():
    docs = load_info_documents(HOUSING_DIR)
    return search_question("How much do residences cost and where can I find a private flat?", docs)


def reply(**overrides):
    body = {
        "answer": "Residence Alpha costs EUR 4,000 for the semester.",
        "sources": [EXCHANGE_HOUSING_FILE],
        "found": True,
    }
    return json.dumps({**body, **overrides})


def ask(housing_chunks, question="How much does Residence Alpha cost?"):
    return llm.answer_question(question, housing_chunks)


def test_answer_is_parsed(monkeypatch, housing_chunks):
    use_client(monkeypatch, FakeClient(content=reply()))

    result = ask(housing_chunks)

    assert result == {
        "answer": "Residence Alpha costs EUR 4,000 for the semester.",
        "sources": [EXCHANGE_HOUSING_FILE],
        "found": True,
        "model_error": False,
    }


def test_url_not_in_retrieved_text_is_removed(monkeypatch, housing_chunks):
    text = "Pay a deposit at https://evil.example.com/pay or browse https://flats.example.com."
    use_client(monkeypatch, FakeClient(content=reply(answer=text, sources=[PRIVATE_HOUSING_FILE])))

    result = ask(housing_chunks)

    assert "evil.example.com" not in result["answer"]
    assert "https://flats.example.com" in result["answer"]


def test_remove_unknown_urls_keeps_only_allowed_links():
    allowed = "See https://example.org/housing/apply and www.allowed.example.org for details."
    answer = "Apply at https://example.org/housing/apply, not www.other.example.org or http://x.example/y)."

    cleaned = llm.remove_unknown_urls(answer, allowed)

    assert "https://example.org/housing/apply" in cleaned
    assert "other.example.org" not in cleaned
    assert "x.example" not in cleaned


def test_source_line_url_of_retrieved_file_is_allowed(monkeypatch, housing_chunks):
    text = "Check https://example.org/housing/exchange for details."
    use_client(monkeypatch, FakeClient(content=reply(answer=text)))

    assert "https://example.org/housing/exchange" in ask(housing_chunks)["answer"]


def test_found_false_gives_dont_know(monkeypatch, housing_chunks):
    use_client(monkeypatch, FakeClient(content=reply(answer="Maybe EUR 10.", sources=[], found=False)))

    result = ask(housing_chunks)

    assert result["found"] is False
    assert result["answer"] == llm.DONT_KNOW
    assert result["model_error"] is False


def test_non_boolean_found_is_not_found(monkeypatch, housing_chunks):
    use_client(monkeypatch, FakeClient(content=reply(found="yes")))

    assert ask(housing_chunks)["found"] is False


def test_unknown_source_is_dropped(monkeypatch, housing_chunks):
    sources = [EXCHANGE_HOUSING_FILE, "data/housing/invented.md"]
    use_client(monkeypatch, FakeClient(content=reply(sources=sources)))

    assert ask(housing_chunks)["sources"] == [EXCHANGE_HOUSING_FILE]


def test_found_without_valid_source_is_not_found(monkeypatch, housing_chunks):
    use_client(monkeypatch, FakeClient(content=reply(sources=["data/housing/invented.md"])))

    result = ask(housing_chunks)

    assert result["found"] is False
    assert result["answer"] == llm.DONT_KNOW


def test_bad_json_answer_reports_model_unavailable(monkeypatch, housing_chunks):
    use_client(monkeypatch, FakeClient(content="not json"))

    result = ask(housing_chunks)

    assert result["model_error"] is True
    assert result["found"] is False
    assert result["answer"] == llm.MODEL_UNAVAILABLE_ANSWER == "Model unavailable – could not answer"


def test_api_error_answer_logs_type_only(monkeypatch, caplog, housing_chunks):
    use_client(monkeypatch, FakeClient(error=RuntimeError("secret-detail sk-123")))

    result = ask(housing_chunks)

    assert result["model_error"] is True
    assert "RuntimeError" in caplog.text
    assert "sk-123" not in caplog.text


def test_no_chunks_skips_the_model_for_questions(monkeypatch):
    client = FakeClient(content=reply())
    use_client(monkeypatch, client)

    result = llm.answer_question("Anything?", [])

    assert result["found"] is False
    assert result["answer"] == llm.DONT_KNOW
    assert client.messages is None


def test_question_prompt_contains_question_chunks_and_rules(monkeypatch, housing_chunks):
    client = FakeClient(content=reply())
    use_client(monkeypatch, client)

    ask(housing_chunks, question="How much does Residence Alpha cost?")

    prompt = " ".join(m["content"] for m in client.messages)
    assert "How much does Residence Alpha cost?" in prompt
    assert EXCHANGE_HOUSING_FILE in prompt
    assert "EUR 4,000 for the semester" in prompt
    assert "exactly as written" in prompt

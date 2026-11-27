"""The ONLY file that calls the model. It judges course content and answers housing/clubs
questions from retrieved text. It never does arithmetic on credits, prices or dates."""

import json
import logging
import os
import re

from backend.retrieval import Chunk, Document

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
MODEL_UNAVAILABLE = "Model unavailable – content could not be checked"
NO_CANDIDATES = "No exchange course in our sources covers this course."

SYSTEM_PROMPT = """You compare a home university course with candidate exchange courses.
Use ONLY the documents given. Judge course CONTENT only (topics, learning outcomes).
Never mention credits, ECTS, workload or numbers of any kind.
Pick the single best candidate. If the documents do not clearly show that it covers
the same content as the home course, set content_match to false.
Answer with one JSON object with exactly these keys:
"exchange_course" (string), "home_course" (string), "reason" (one or two sentences),
"source_file" (the exact file path of the chosen candidate), "content_match" (true or false)."""


def _client():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    from openai import OpenAI

    return OpenAI()


def _user_prompt(home: Document, candidates: list[Chunk]) -> str:
    parts = [f"HOME COURSE: {home.course}\n{home.text}", "CANDIDATE EXCHANGE COURSES:"]
    for chunk in candidates:
        parts.append(f"--- file: {chunk.file}\n{chunk.text}")
    return "\n\n".join(parts)


def _not_a_match(home: Document, reason: str, model_error: bool, source_file: str | None = None) -> dict:
    return {
        "exchange_course": None,
        "home_course": home.course,
        "reason": reason,
        "source_file": source_file,
        "content_match": False,
        "model_error": model_error,
    }


def judge_match(home: Document, candidates: list[Chunk]) -> dict:
    """Ask the model whether one of the candidates covers the home course's content."""
    if not candidates:
        return _not_a_match(home, NO_CANDIDATES, model_error=False)

    try:
        response = _client().chat.completions.create(
            model=os.getenv("OPENAI_MODEL") or DEFAULT_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(home, candidates)},
            ],
        )
        data = json.loads(response.choices[0].message.content)
        if not isinstance(data, dict):
            raise ValueError("model answer is not a JSON object")
    except Exception as error:  # noqa: BLE001 - any failure means "could not check"
        logger.warning("LLM call failed: %s", type(error).__name__)
        return _not_a_match(home, MODEL_UNAVAILABLE, model_error=True)

    source_file = data.get("source_file")
    known_file = source_file in {c.file for c in candidates}
    return {
        "exchange_course": data.get("exchange_course"),
        "home_course": home.course,
        "reason": str(data.get("reason") or ""),
        "source_file": source_file if known_file else None,
        "content_match": data.get("content_match") is True and known_file,
        "model_error": False,
    }


# --- Housing and Clubs sections: answer a question from retrieved chunks only ---

MODEL_UNAVAILABLE_ANSWER = "Model unavailable – could not answer"
DONT_KNOW = "I don't know – please ask the Bocconi International Student Desk or Housing Office"

ANSWER_PROMPT = """You answer a student's question about their exchange semester.
Answer ONLY from the text given below. Do not use any other knowledge.
Copy prices, dates and links exactly as written in the text.
If you name a website that appears in the text, include its URL exactly as written.
Never calculate, add up, convert or count anything.
Keep the answer short (at most a few sentences), in plain text, no markdown.
If the text does not answer the question, set found to false.
Answer with one JSON object with exactly these keys:
"answer" (string), "sources" (list of the exact file paths you used), "found" (true or false)."""

_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'()\[\]]+")
_URL_TRAILING = ".,;:!?"


def _normalize_url(url: str) -> str:
    return url.rstrip(_URL_TRAILING).rstrip("/")


def remove_unknown_urls(answer: str, allowed_text: str) -> str:
    """Remove every URL from `answer` that does not appear in `allowed_text`."""
    allowed = {_normalize_url(u) for u in _URL_RE.findall(allowed_text)}

    def keep_or_drop(match: re.Match) -> str:
        url = match.group(0)
        core = url.rstrip(_URL_TRAILING)
        return url if _normalize_url(url) in allowed else url[len(core) :]

    cleaned = _URL_RE.sub(keep_or_drop, answer)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _question_prompt(question: str, chunks: list[Chunk]) -> str:
    parts = [f"QUESTION: {question}", "TEXT:"]
    for chunk in chunks:
        parts.append(f"--- file: {chunk.file}\n{chunk.text}")
    return "\n\n".join(parts)


def _not_answered(model_error: bool) -> dict:
    answer = MODEL_UNAVAILABLE_ANSWER if model_error else DONT_KNOW
    return {"answer": answer, "sources": [], "found": False, "model_error": model_error}


def answer_question(question: str, chunks: list[Chunk]) -> dict:
    """Answer from the retrieved chunks only. URLs and sources are checked here, in code."""
    if not chunks:
        return _not_answered(model_error=False)

    try:
        response = _client().chat.completions.create(
            model=os.getenv("OPENAI_MODEL") or DEFAULT_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": ANSWER_PROMPT},
                {"role": "user", "content": _question_prompt(question, chunks)},
            ],
        )
        data = json.loads(response.choices[0].message.content)
        if not isinstance(data, dict):
            raise ValueError("model answer is not a JSON object")
    except Exception as error:  # noqa: BLE001 - any failure means "could not answer"
        logger.warning("LLM call failed: %s", type(error).__name__)
        return _not_answered(model_error=True)

    retrieved = {c.file for c in chunks}
    cited = data.get("sources")
    cited = cited if isinstance(cited, list) else []
    sources = list(dict.fromkeys(s for s in cited if s in retrieved))
    if data.get("found") is not True or not sources:
        return _not_answered(model_error=False)

    allowed_text = "\n".join([c.text for c in chunks] + sorted({c.source_url for c in chunks}))
    answer = remove_unknown_urls(str(data.get("answer") or ""), allowed_text)
    return {"answer": answer, "sources": sources, "found": True, "model_error": False}

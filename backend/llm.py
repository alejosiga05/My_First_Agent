"""The ONLY file that calls the model. It judges course content; it never handles credits."""

import json
import logging
import os

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

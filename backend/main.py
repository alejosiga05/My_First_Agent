"""FastAPI app: serves frontend/, /health, and the API, on one port."""

import os
from pathlib import Path
from typing import Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from backend import llm, retrieval
from backend.recommender import build_card, summarize_credits

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_DIR = ROOT_DIR / "data"
COURSES_DIR = DATA_DIR / "courses"
SECTION_DIRS = {"housing": DATA_DIR / "housing", "clubs": DATA_DIR / "clubs"}

app = FastAPI(title="Course Exchange Assistant")


class MatchRequest(BaseModel):
    home_university: str
    exchange_university: str
    home_courses: list[str]
    credits_needed: float = Field(gt=0)
    question: str | None = None


class AskRequest(BaseModel):
    section: Literal["housing", "clubs"]
    question: str

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be empty")
        return value.strip()


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/home-courses")
def home_courses() -> dict[str, list[dict]]:
    grouped = retrieval.home_courses_by_university(retrieval.load_documents(COURSES_DIR))
    return {"home_universities": [{"name": name, "courses": courses} for name, courses in grouped.items()]}


@app.post("/api/match")
def match(request: MatchRequest) -> dict:
    if request.home_university not in retrieval.HOME_UNIVERSITIES.values():
        raise HTTPException(status_code=422, detail=f"Unknown home university: {request.home_university}")
    docs = retrieval.load_documents(COURSES_DIR)
    # Only the chosen university's courses: a course from another home university is rejected below.
    homes = {d.course: d for d in docs if d.home_university == request.home_university}
    unknown = [name for name in request.home_courses if name not in homes]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown home course(s): {', '.join(unknown)}")
    by_file = {d.file: d for d in docs}

    cards = []
    for name in request.home_courses:
        home = homes[name]
        candidates = retrieval.search(home, docs)
        judgment = llm.judge_match(home, candidates)
        # Show the course the model judged; if it named none, the top search result.
        chosen = judgment.get("source_file") or (candidates[0].file if candidates else None)
        cards.append(build_card(judgment, home, by_file.get(chosen)))
    return {"matches": cards, "summary": summarize_credits(cards, request.credits_needed)}


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    """Answer a Housing or Clubs question from that section's files only."""
    docs = retrieval.load_info_documents(SECTION_DIRS[request.section])
    chunks = retrieval.search_question(request.question, docs)
    result = llm.answer_question(request.question, chunks)

    by_file = {d.file: d for d in docs}
    # Not answered: show the closest retrieved files instead, in ranking order.
    files = result["sources"] if result["found"] else list(dict.fromkeys(c.file for c in chunks))
    sources = [
        {"file": f, "title": by_file[f].course, "url": by_file[f].source_url} for f in files if f in by_file
    ]
    return {
        "section": request.section,
        "found": result["found"],
        "answer": result["answer"],
        "sources": sources,
        "model_error": result["model_error"],
    }


app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
# Keep this last: a mount at "/" would otherwise catch the API routes.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT") or 8000))

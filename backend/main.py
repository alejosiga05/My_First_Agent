"""FastAPI app: serves frontend/, /health, and the API, on one port."""

import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import llm, retrieval
from backend.recommender import build_card, summarize_credits

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_DIR = ROOT_DIR / "data"
COURSES_DIR = DATA_DIR / "courses"

app = FastAPI(title="Course Exchange Assistant")


class MatchRequest(BaseModel):
    home_university: str
    exchange_university: str
    home_courses: list[str]
    credits_needed: float = Field(gt=0)
    question: str | None = None


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/home-courses")
def home_courses() -> dict[str, list[str]]:
    return {"home_courses": retrieval.home_courses(retrieval.load_documents(COURSES_DIR))}


@app.post("/api/match")
def match(request: MatchRequest) -> dict:
    docs = retrieval.load_documents(COURSES_DIR)
    homes = {d.course: d for d in docs if d.side == "home"}
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


app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
# Keep this last: a mount at "/" would otherwise catch the API routes.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT") or 8000))

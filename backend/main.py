"""FastAPI app: serves frontend/, /health, and the API, on one port."""

import json
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.recommender import summarize_credits

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_DIR = ROOT_DIR / "data"
# Temporary: sample results until llm.py is wired in.
SAMPLE_MATCHES = ROOT_DIR / "tests" / "fixtures" / "sample_matches.json"

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


@app.post("/api/match")
def match(request: MatchRequest) -> dict:
    matches = json.loads(SAMPLE_MATCHES.read_text(encoding="utf-8"))["matches"]
    return {"matches": matches, "summary": summarize_credits(matches, request.credits_needed)}


app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
# Keep this last: a mount at "/" would otherwise catch the API routes.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT") or 8000))

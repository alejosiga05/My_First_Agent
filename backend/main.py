"""FastAPI app: serves frontend/, /health, and the API, on one port."""

import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Course Exchange Assistant")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


# Keep this last: a mount at "/" would otherwise catch the API routes.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT") or 8000))

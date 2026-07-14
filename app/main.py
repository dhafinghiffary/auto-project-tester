from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_test import router as test_router
from app.core import config  # noqa: F401  (import triggers load_dotenv())

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="auto-project-tester")

app.include_router(test_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

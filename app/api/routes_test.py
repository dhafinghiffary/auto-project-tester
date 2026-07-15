from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.schemas import GithubTestRequest
from app.domain.models import TestReport
from app.ingestion.errors import IngestionError
from app.ingestion.github_ingest import clone_public_repo
from app.ingestion.workspace import new_workspace
from app.ingestion.zip_ingest import extract_zip
from app.services.errors import SandboxError
from app.services.pipeline import run_pipeline

router = APIRouter(prefix="/test", tags=["test"])


def _resolve_source_root(extracted_dir: Path) -> Path:
    """Many ZIP exports (e.g. GitHub's 'Download ZIP') wrap everything in a
    single top-level folder. Descend into it if that's the only entry."""
    entries = list(extracted_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extracted_dir


def _run_zip_pipeline(workspace: Path, zip_bytes: bytes, filename: str) -> TestReport:
    extract_zip(zip_bytes, workspace)
    source_root = _resolve_source_root(workspace)
    project_name = Path(filename).stem
    return run_pipeline(source_root, project_name, f"ZIP upload: {filename}")


def _run_github_pipeline(workspace: Path, repo_url: str) -> TestReport:
    clone_public_repo(repo_url, workspace)
    project_name = repo_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    return run_pipeline(workspace, project_name, f"GitHub: {repo_url}")


@router.post("/zip", response_model=TestReport)
async def test_zip(file: UploadFile = File(...)) -> TestReport:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "File harus berformat .zip")

    workspace = new_workspace()
    zip_bytes = await file.read()
    try:
        # The whole pipeline (git/zip I/O, the Gemini call, Docker exec) is blocking.
        # Running it inline in this `async def` would freeze FastAPI's single event
        # loop for every other request until it finishes -- offload it to a thread.
        return await run_in_threadpool(_run_zip_pipeline, workspace, zip_bytes, file.filename)
    except IngestionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post("/github", response_model=TestReport)
async def test_github(body: GithubTestRequest) -> TestReport:
    workspace = new_workspace()
    try:
        return await run_in_threadpool(_run_github_pipeline, workspace, body.repo_url)
    except IngestionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(500, str(exc)) from exc

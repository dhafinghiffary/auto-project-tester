from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

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


@router.post("/zip", response_model=TestReport)
async def test_zip(file: UploadFile = File(...)) -> TestReport:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "File harus berformat .zip")

    workspace = new_workspace()
    try:
        zip_bytes = await file.read()
        extract_zip(zip_bytes, workspace)
        source_root = _resolve_source_root(workspace)
        project_name = Path(file.filename).stem
        return run_pipeline(source_root, project_name, f"ZIP upload: {file.filename}")
    except IngestionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post("/github", response_model=TestReport)
async def test_github(body: GithubTestRequest) -> TestReport:
    workspace = new_workspace()
    try:
        clone_public_repo(body.repo_url, workspace)
        project_name = body.repo_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        return run_pipeline(workspace, project_name, f"GitHub: {body.repo_url}")
    except IngestionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(500, str(exc)) from exc

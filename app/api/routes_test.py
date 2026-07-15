from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.api.schemas import GithubTestRequest
from app.domain.models import TestJob
from app.ingestion.errors import IngestionError
from app.ingestion.github_ingest import clone_public_repo
from app.ingestion.workspace import new_workspace
from app.ingestion.zip_ingest import extract_zip
from app.services import job_store
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


def _run_job(job_id: str, ingest_fn) -> None:
    """Shared job runner: ingest_fn() does the source-specific ingestion (zip
    extract / git clone) and returns the resolved source dir + project_name.
    Runs on a BackgroundTasks worker thread, never inline in the event loop."""
    job_store.update_job(job_id, status="running", stage="Mengambil source code...")
    try:
        source_dir, project_name, source_summary = ingest_fn()
        report = run_pipeline(
            source_dir,
            project_name,
            source_summary,
            on_stage=lambda stage: job_store.update_job(job_id, stage=stage),
        )
        job_store.update_job(job_id, status="done", stage="Selesai", report=report)
    except IngestionError as exc:
        job_store.update_job(job_id, status="failed", stage="Gagal", error=str(exc))
    except SandboxError as exc:
        job_store.update_job(job_id, status="failed", stage="Gagal", error=str(exc))
    except Exception as exc:  # noqa: BLE001 - last resort so a job never hangs as "running" forever
        job_store.update_job(job_id, status="failed", stage="Gagal", error=f"Error tak terduga: {exc}")


@router.post("/zip", response_model=TestJob, status_code=202)
async def test_zip(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> TestJob:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "File harus berformat .zip")

    zip_bytes = await file.read()
    filename = file.filename
    job = job_store.create_job(project_name=Path(filename).stem, source_summary=f"ZIP upload: {filename}")

    def ingest():
        workspace = new_workspace()
        extract_zip(zip_bytes, workspace)
        source_root = _resolve_source_root(workspace)
        return source_root, Path(filename).stem, f"ZIP upload: {filename}"

    background_tasks.add_task(_run_job, job.job_id, ingest)
    return job


@router.post("/github", response_model=TestJob, status_code=202)
async def test_github(body: GithubTestRequest, background_tasks: BackgroundTasks) -> TestJob:
    repo_url = body.repo_url
    project_name = repo_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    job = job_store.create_job(project_name=project_name, source_summary=f"GitHub: {repo_url}")

    def ingest():
        workspace = new_workspace()
        clone_public_repo(repo_url, workspace)
        return workspace, project_name, f"GitHub: {repo_url}"

    background_tasks.add_task(_run_job, job.job_id, ingest)
    return job


@router.get("/jobs", response_model=list[TestJob])
async def list_jobs() -> list[TestJob]:
    return job_store.list_jobs()


@router.get("/jobs/{job_id}", response_model=TestJob)
async def get_job(job_id: str) -> TestJob:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job tidak ditemukan")
    return job

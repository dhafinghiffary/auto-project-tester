from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import JobStatus, TestJob, TestReport

JOB_HISTORY_DIR = Path(__file__).resolve().parent.parent.parent / "job_history"

_lock = threading.Lock()
_jobs: dict[str, TestJob] = {}


def _persist(job: TestJob) -> None:
    JOB_HISTORY_DIR.mkdir(exist_ok=True)
    path = JOB_HISTORY_DIR / f"{job.job_id}.json"
    path.write_text(job.model_dump_json(indent=2), encoding="utf-8")


def _load_all() -> None:
    if not JOB_HISTORY_DIR.exists():
        return
    for path in JOB_HISTORY_DIR.glob("*.json"):
        try:
            job = TestJob.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if job.status in ("queued", "running"):
            # No thread is actually processing this job anymore -- the process
            # that owned it is gone (server restarted/crashed mid-run).
            job.status = "failed"
            job.stage = "Terputus"
            job.error = "Server di-restart atau crash sebelum job ini selesai."
            job.updated_at = datetime.now(timezone.utc)
            _persist(job)
        _jobs[job.job_id] = job


_load_all()


def create_job(project_name: str, source_summary: str) -> TestJob:
    job = TestJob(job_id=uuid.uuid4().hex[:12], project_name=project_name, source_summary=source_summary)
    with _lock:
        _jobs[job.job_id] = job
        _persist(job)
    return job


def update_job(
    job_id: str,
    *,
    status: JobStatus | None = None,
    stage: str | None = None,
    report: TestReport | None = None,
    error: str | None = None,
) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        if status is not None:
            job.status = status
        if stage is not None:
            job.stage = stage
        if report is not None:
            job.report = report
        if error is not None:
            job.error = error
        job.updated_at = datetime.now(timezone.utc)
        _persist(job)


def get_job(job_id: str) -> TestJob | None:
    with _lock:
        return _jobs.get(job_id)


def list_jobs(limit: int = 50) -> list[TestJob]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

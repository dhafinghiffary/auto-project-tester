from __future__ import annotations

from pathlib import Path

import pytest

from app.services import job_store


@pytest.fixture(autouse=True)
def isolated_job_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every test gets its own empty job store so we never touch the real
    job_history/ directory or leak state between tests."""
    monkeypatch.setattr(job_store, "JOB_HISTORY_DIR", tmp_path / "job_history")
    monkeypatch.setattr(job_store, "_jobs", {})
    yield


def test_create_and_get_job():
    job = job_store.create_job("demo", "ZIP upload: demo.zip")

    fetched = job_store.get_job(job.job_id)

    assert fetched is not None
    assert fetched.project_name == "demo"
    assert fetched.status == "queued"


def test_update_job_persists_changes():
    job = job_store.create_job("demo", "ZIP upload: demo.zip")

    job_store.update_job(job.job_id, status="running", stage="Menganalisis kode...")

    fetched = job_store.get_job(job.job_id)
    assert fetched.status == "running"
    assert fetched.stage == "Menganalisis kode..."


def test_get_job_returns_none_for_unknown_id():
    assert job_store.get_job("does-not-exist") is None


def test_list_jobs_sorted_newest_first():
    from datetime import datetime

    older = job_store.TestJob(job_id="older", project_name="a", source_summary="a",
                               created_at=datetime(2020, 1, 1))
    newer = job_store.TestJob(job_id="newer", project_name="b", source_summary="b",
                               created_at=datetime(2021, 1, 1))
    job_store._jobs["older"] = older
    job_store._jobs["newer"] = newer

    jobs = job_store.list_jobs()

    assert jobs[0].job_id == "newer"


def test_load_all_reconciles_orphaned_running_job_as_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    history_dir = tmp_path / "job_history"
    history_dir.mkdir()
    orphan = job_store.TestJob(job_id="orphan123", status="running", stage="Menjalankan test...",
                                project_name="demo", source_summary="ZIP upload: demo.zip")
    (history_dir / "orphan123.json").write_text(orphan.model_dump_json(), encoding="utf-8")

    monkeypatch.setattr(job_store, "JOB_HISTORY_DIR", history_dir)
    monkeypatch.setattr(job_store, "_jobs", {})

    job_store._load_all()

    reconciled = job_store.get_job("orphan123")
    assert reconciled.status == "failed"
    assert "restart" in reconciled.error.lower() or "crash" in reconciled.error.lower()

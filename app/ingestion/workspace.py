from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

WORKSPACES_ROOT = Path(__file__).resolve().parent.parent.parent / "workspaces"
DEFAULT_RETENTION_HOURS = 24


def new_workspace() -> Path:
    WORKSPACES_ROOT.mkdir(exist_ok=True)
    workspace = WORKSPACES_ROOT / uuid.uuid4().hex
    workspace.mkdir(parents=True)
    return workspace


def cleanup_workspace(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)


def cleanup_stale_workspaces(retention_hours: float = DEFAULT_RETENTION_HOURS) -> int:
    """Removes workspace dirs older than retention_hours. Each request creates
    a new workspace and nothing ever swept them, so disk usage grew without
    bound. Returns the number of workspaces removed."""
    if not WORKSPACES_ROOT.exists():
        return 0

    cutoff = time.time() - (retention_hours * 3600)
    removed = 0
    for entry in WORKSPACES_ROOT.iterdir():
        if not entry.is_dir():
            continue
        if entry.stat().st_mtime < cutoff:
            cleanup_workspace(entry)
            removed += 1
    return removed

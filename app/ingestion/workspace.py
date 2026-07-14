from __future__ import annotations

import shutil
import uuid
from pathlib import Path

WORKSPACES_ROOT = Path(__file__).resolve().parent.parent.parent / "workspaces"


def new_workspace() -> Path:
    WORKSPACES_ROOT.mkdir(exist_ok=True)
    workspace = WORKSPACES_ROOT / uuid.uuid4().hex
    workspace.mkdir(parents=True)
    return workspace


def cleanup_workspace(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)

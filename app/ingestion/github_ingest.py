from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.ingestion.errors import IngestionError

# Only accept plain https://github.com/<owner>/<repo>[.git] URLs. This blocks
# ssh://, file://, and anything with option-like ("-...") prefixes that could
# otherwise be interpreted as a git command-line flag.
GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[\w.-]+/[\w.-]+?(\.git)?/?$"
)

CLONE_TIMEOUT_SECONDS = 60


def validate_github_url(url: str) -> str:
    url = url.strip()
    if not GITHUB_URL_RE.match(url):
        raise IngestionError(
            "URL repo tidak valid. Harus berbentuk https://github.com/<owner>/<repo>"
        )
    return url


def clone_public_repo(url: str, dest: Path) -> None:
    url = validate_github_url(url)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", "--", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise IngestionError("Clone repo timeout (repo terlalu besar atau tidak bisa diakses)") from exc

    if result.returncode != 0:
        raise IngestionError(f"Gagal clone repo: {result.stderr.strip()[:500]}")

    git_dir = dest / ".git"
    if git_dir.exists():
        import shutil

        shutil.rmtree(git_dir, ignore_errors=True)

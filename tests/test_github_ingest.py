from __future__ import annotations

import pytest

from app.ingestion.errors import IngestionError
from app.ingestion.github_ingest import validate_github_url


@pytest.mark.parametrize("url", [
    "https://github.com/owner/repo",
    "https://github.com/owner/repo.git",
    "https://github.com/owner/repo/",
    "https://github.com/owner-name/repo_name",
])
def test_validate_github_url_accepts_valid_urls(url: str):
    assert validate_github_url(url) == url


@pytest.mark.parametrize("url", [
    "http://github.com/owner/repo",  # not https
    "https://evil.com/owner/repo",  # wrong host
    "https://github.com/owner/repo/extra/path",
    "git@github.com:owner/repo.git",
    "not-a-url",
    "https://github.com/owner",  # missing repo segment
    "",
])
def test_validate_github_url_rejects_invalid_urls(url: str):
    with pytest.raises(IngestionError):
        validate_github_url(url)

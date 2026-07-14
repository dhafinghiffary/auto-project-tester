from __future__ import annotations

from pydantic import BaseModel


class GithubTestRequest(BaseModel):
    repo_url: str

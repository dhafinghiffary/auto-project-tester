from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# "gemini" (default) or "anthropic" -- switch providers without touching code,
# e.g. when the Gemini free-tier daily quota is exhausted.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

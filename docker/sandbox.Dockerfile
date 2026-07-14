FROM python:3.11-slim

RUN useradd -m -u 1000 runner

USER runner
WORKDIR /home/runner

RUN python -m venv /home/runner/venv
ENV PATH="/home/runner/venv/bin:$PATH"

RUN pip install --no-cache-dir --disable-pip-version-check pytest pytest-json-report

WORKDIR /workspace

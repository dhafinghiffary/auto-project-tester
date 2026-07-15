from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ParameterInfo(BaseModel):
    name: str
    annotation: str | None = None
    default: str | None = None


class FunctionInfo(BaseModel):
    name: str
    parameters: list[ParameterInfo] = Field(default_factory=list)
    return_annotation: str | None = None
    docstring: str | None = None
    is_async: bool = False
    lineno: int


class ClassInfo(BaseModel):
    name: str
    docstring: str | None = None
    methods: list[FunctionInfo] = Field(default_factory=list)
    lineno: int


class FileAnalysis(BaseModel):
    file_path: str
    module_name: str
    imports: list[str] = Field(default_factory=list)
    functions: list[FunctionInfo] = Field(default_factory=list)
    classes: list[ClassInfo] = Field(default_factory=list)
    parse_error: str | None = None


class ParsedProjectContext(BaseModel):
    project_name: str
    files: list[FileAnalysis] = Field(default_factory=list)
    has_requirements: bool = False
    requirements_content: str | None = None


class GeneratedTestFile(BaseModel):
    filename: str
    target_module: str
    content: str


class TestGenerationResult(BaseModel):
    files: list[GeneratedTestFile] = Field(default_factory=list)
    model_notes: str | None = None


TestOutcome = Literal["passed", "failed", "error", "skipped"]


class TestCaseResult(BaseModel):
    node_id: str
    outcome: TestOutcome
    duration: float = 0.0
    message: str | None = None


class ExecutionSummary(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0


class ExecutionResult(BaseModel):
    install_success: bool
    install_log: str = ""
    timed_out: bool = False
    summary: ExecutionSummary = Field(default_factory=ExecutionSummary)
    tests: list[TestCaseResult] = Field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""


class TestReport(BaseModel):
    project_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source_summary: str
    generated_tests: list[GeneratedTestFile] = Field(default_factory=list)
    execution: ExecutionResult
    markdown: str


JobStatus = Literal["queued", "running", "done", "failed"]


class TestJob(BaseModel):
    job_id: str
    status: JobStatus = "queued"
    stage: str = "Menunggu giliran..."
    project_name: str
    source_summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    report: TestReport | None = None
    error: str | None = None

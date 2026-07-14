from __future__ import annotations

from pathlib import Path

from app.domain.models import TestReport
from app.services.code_analyzer import analyze_project
from app.services.report_service import build_report
from app.services.sandbox_executor import run_in_sandbox
from app.services.test_generator_service import TestGeneratorService


def run_pipeline(source_dir: Path, project_name: str, source_summary: str) -> TestReport:
    context = analyze_project(source_dir, project_name)

    generator = TestGeneratorService()
    generated = generator.generate_tests(context)

    generated_dir = source_dir / "generated_tests"
    generated_dir.mkdir(exist_ok=True)
    for f in generated.files:
        (generated_dir / f.filename).write_text(f.content, encoding="utf-8")

    execution = run_in_sandbox(source_dir)

    return build_report(project_name, source_summary, generated, execution)

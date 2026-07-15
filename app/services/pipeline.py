from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.domain.models import TestReport
from app.services.code_analyzer import analyze_project
from app.services.report_service import build_report
from app.services.sandbox_executor import run_in_sandbox
from app.services.test_generator_service import TestGeneratorService

OnStage = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def run_pipeline(
    source_dir: Path,
    project_name: str,
    source_summary: str,
    on_stage: OnStage = _noop,
) -> TestReport:
    on_stage("Menganalisis struktur kode...")
    context = analyze_project(source_dir, project_name)

    on_stage("Generate test dengan AI (Gemini)...")
    generator = TestGeneratorService()
    generated = generator.generate_tests(context)

    generated_dir = source_dir / "generated_tests"
    generated_dir.mkdir(exist_ok=True)
    for f in generated.files:
        (generated_dir / f.filename).write_text(f.content, encoding="utf-8")

    on_stage("Menjalankan test di sandbox Docker...")
    execution = run_in_sandbox(source_dir)

    on_stage("Menyusun laporan...")
    return build_report(project_name, source_summary, generated, execution)

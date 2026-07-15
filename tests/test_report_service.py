from __future__ import annotations

from app.domain.models import (
    ExecutionResult,
    ExecutionSummary,
    GeneratedTestFile,
    TestCaseResult,
    TestGenerationResult,
)
from app.services.report_service import build_report


def test_build_report_summarizes_passing_and_failing_tests():
    generated = TestGenerationResult(
        files=[GeneratedTestFile(filename="test_calc.py", target_module="calc", content="def test_x(): pass")],
    )
    execution = ExecutionResult(
        install_success=True,
        summary=ExecutionSummary(total=2, passed=1, failed=1, errors=0, skipped=0, duration_seconds=0.5),
        tests=[
            TestCaseResult(node_id="test_calc.py::test_a", outcome="passed", duration=0.1),
            TestCaseResult(node_id="test_calc.py::test_b", outcome="failed", duration=0.2, message="assert 1 == 2"),
        ],
    )

    report = build_report("demo", "ZIP upload: demo.zip", generated, execution)

    assert report.project_name == "demo"
    assert "Total test: 2" in report.markdown
    assert "Passed: 1" in report.markdown
    assert "Failed: 1" in report.markdown
    assert "test_calc.py::test_b" in report.markdown
    assert "assert 1 == 2" in report.markdown
    assert "test_calc.py" in report.markdown  # listed under generated files


def test_build_report_handles_failed_install():
    generated = TestGenerationResult(files=[])
    execution = ExecutionResult(
        install_success=False,
        install_log="ERROR: could not find a version that satisfies the requirement foo",
        summary=ExecutionSummary(),
    )

    report = build_report("demo", "GitHub: https://github.com/x/y", generated, execution)

    assert "GAGAL" in report.markdown
    assert "could not find a version" in report.markdown


def test_build_report_handles_no_tests_collected():
    generated = TestGenerationResult(files=[], model_notes="Tidak ada fungsi yang bisa dites.")
    execution = ExecutionResult(install_success=True, summary=ExecutionSummary(), raw_stdout="no tests ran")

    report = build_report("empty-repo", "ZIP upload: empty.zip", generated, execution)

    assert "Tidak ada test yang berhasil dikumpulkan" in report.markdown
    assert "Tidak ada fungsi yang bisa dites." in report.markdown

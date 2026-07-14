from __future__ import annotations

from app.domain.models import ExecutionResult, TestGenerationResult, TestReport


def _outcome_label(outcome: str) -> str:
    return {
        "passed": "PASSED",
        "failed": "FAILED",
        "error": "ERROR",
        "skipped": "SKIPPED",
    }.get(outcome, outcome.upper())


def _build_markdown(project_name: str, source_summary: str, generated: TestGenerationResult, execution: ExecutionResult) -> str:
    s = execution.summary
    lines: list[str] = []
    lines.append(f"# Laporan Testing: {project_name}")
    lines.append("")
    lines.append(f"Sumber: {source_summary}")
    lines.append("")
    lines.append("## Ringkasan")
    lines.append(f"- Total test: {s.total}")
    lines.append(f"- Passed: {s.passed}")
    lines.append(f"- Failed: {s.failed}")
    lines.append(f"- Error: {s.errors}")
    lines.append(f"- Skipped: {s.skipped}")
    lines.append(f"- Durasi eksekusi: {s.duration_seconds:.2f}s")
    lines.append(f"- Install dependencies: {'sukses' if execution.install_success else 'GAGAL'}")
    if execution.timed_out:
        lines.append("- **Peringatan: eksekusi test timeout dan dihentikan paksa.**")
    lines.append("")

    if not execution.install_success:
        lines.append("## Log Install Dependencies (gagal)")
        lines.append("```")
        lines.append(execution.install_log)
        lines.append("```")
        lines.append("")

    lines.append("## Detail Test")
    if execution.tests:
        lines.append("| Test | Hasil | Durasi (s) |")
        lines.append("|---|---|---|")
        for t in execution.tests:
            lines.append(f"| `{t.node_id}` | {_outcome_label(t.outcome)} | {t.duration:.3f} |")
        lines.append("")

        failing = [t for t in execution.tests if t.outcome in ("failed", "error") and t.message]
        if failing:
            lines.append("### Detail Kegagalan")
            for t in failing:
                lines.append(f"**`{t.node_id}`**")
                lines.append("```")
                lines.append(t.message or "")
                lines.append("```")
    else:
        lines.append("_Tidak ada test yang berhasil dikumpulkan/dijalankan. Lihat raw output di bawah._")
        lines.append("")
        lines.append("```")
        lines.append(execution.raw_stdout)
        lines.append("```")

    lines.append("")
    lines.append("## File Test yang Digenerate AI")
    if generated.files:
        for f in generated.files:
            lines.append(f"- `{f.filename}` (menguji `{f.target_module}`)")
    else:
        lines.append("_Tidak ada file test yang digenerate._")

    if generated.model_notes:
        lines.append("")
        lines.append("## Catatan dari Model")
        lines.append(generated.model_notes)

    return "\n".join(lines)


def build_report(
    project_name: str,
    source_summary: str,
    generated: TestGenerationResult,
    execution: ExecutionResult,
) -> TestReport:
    markdown = _build_markdown(project_name, source_summary, generated, execution)
    return TestReport(
        project_name=project_name,
        source_summary=source_summary,
        generated_tests=generated.files,
        execution=execution,
        markdown=markdown,
    )

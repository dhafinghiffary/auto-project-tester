from __future__ import annotations

from pathlib import Path

from app.services.code_analyzer import MAX_FILES_ANALYZED, analyze_file, analyze_project


def test_analyze_file_extracts_functions_and_classes(tmp_path: Path):
    src = tmp_path / "calculator.py"
    src.write_text(
        '''
def add(a: int, b: int = 1) -> int:
    """Add two numbers."""
    return a + b


class Rectangle:
    """A shape."""

    def area(self, w: float, h: float) -> float:
        return w * h
''',
        encoding="utf-8",
    )

    result = analyze_file(src, "calculator.py")

    assert result.parse_error is None
    assert result.module_name == "calculator"
    assert [f.name for f in result.functions] == ["add"]
    assert result.functions[0].parameters[0].name == "a"
    assert result.functions[0].parameters[1].default == "1"
    assert result.functions[0].return_annotation == "int"
    assert result.functions[0].docstring == "Add two numbers."
    assert [c.name for c in result.classes] == ["Rectangle"]
    assert result.classes[0].methods[0].name == "area"


def test_analyze_file_reports_syntax_error_instead_of_raising(tmp_path: Path):
    src = tmp_path / "broken.py"
    src.write_text("def foo(:\n    pass", encoding="utf-8")

    result = analyze_file(src, "broken.py")

    assert result.parse_error is not None
    assert result.functions == []


def test_analyze_project_skips_vendored_and_test_dirs(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("def real_function():\n    pass\n", encoding="utf-8")

    # A vendored dependency dir with a .py file that must never be analyzed.
    venv_site_packages = tmp_path / "venv" / "lib" / "site-packages"
    venv_site_packages.mkdir(parents=True)
    (venv_site_packages / "vendored.py").write_text("def should_be_ignored():\n    pass\n", encoding="utf-8")

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_ignored():\n    pass\n", encoding="utf-8")

    context = analyze_project(tmp_path, "demo")

    analyzed_paths = {f.file_path for f in context.files}
    assert analyzed_paths == {"app/main.py"}


def test_analyze_project_respects_file_cap(tmp_path: Path):
    for i in range(MAX_FILES_ANALYZED + 10):
        (tmp_path / f"mod_{i}.py").write_text(f"def f_{i}():\n    pass\n", encoding="utf-8")

    context = analyze_project(tmp_path, "demo")

    assert len(context.files) <= MAX_FILES_ANALYZED


def test_analyze_project_detects_requirements(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")

    context = analyze_project(tmp_path, "demo")

    assert context.has_requirements is True
    assert "flask" in context.requirements_content

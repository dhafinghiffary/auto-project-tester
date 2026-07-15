from __future__ import annotations

from app.services.test_generator_service import _python_syntax_error, _safe_test_filename, _strip_fences


def test_strip_fences_removes_markdown_code_block():
    content = "```python\ndef test_x():\n    assert True\n```"

    result = _strip_fences(content)

    assert result == "def test_x():\n    assert True\n"


def test_strip_fences_is_noop_for_plain_content():
    content = "def test_x():\n    assert True\n"

    assert _strip_fences(content) == content


def test_safe_test_filename_accepts_valid_pattern():
    assert _safe_test_filename("test_calculator.py", 0) == "test_calculator.py"


def test_safe_test_filename_neutralizes_path_traversal():
    # ".." and "/" get stripped before the filename is ever used in a path join,
    # so the result must contain neither -- whatever the exact sanitized string is.
    name = _safe_test_filename("../../evil_test.py", 3)

    assert "/" not in name
    assert "\\" not in name
    assert ".." not in name


def test_safe_test_filename_rejects_wrong_pattern():
    name = _safe_test_filename("calculator.py", 1)  # doesn't start with test_ or end with _test.py

    assert name == "test_generated_1.py"


def test_python_syntax_error_returns_none_for_valid_code():
    assert _python_syntax_error("def test_x():\n    assert True\n", "test_x.py") is None


def test_python_syntax_error_catches_invalid_code():
    error = _python_syntax_error("def test_x(:\n    pass", "test_x.py")

    assert error is not None
    assert "test_x.py" in error

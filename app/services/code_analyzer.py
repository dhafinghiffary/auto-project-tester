from __future__ import annotations

import ast
from pathlib import Path

from app.domain.models import ClassInfo, FileAnalysis, FunctionInfo, ParameterInfo, ParsedProjectContext

SKIP_DIR_NAMES = {
    "venv", ".venv", "env", "__pycache__", ".git", "node_modules",
    "site-packages", "tests", "test", ".pytest_cache", "build", "dist",
    "generated_tests",
}
MAX_FILES_ANALYZED = 40


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py")


def _unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _extract_parameters(args: ast.arguments) -> list[ParameterInfo]:
    params: list[ParameterInfo] = []
    positional = args.posonlyargs + args.args
    defaults = list(args.defaults)
    # Right-align defaults against the tail of positional args.
    pad = len(positional) - len(defaults)
    default_map = {i + pad: d for i, d in enumerate(defaults)}
    for i, arg in enumerate(positional):
        params.append(ParameterInfo(
            name=arg.arg,
            annotation=_unparse(arg.annotation),
            default=_unparse(default_map.get(i)),
        ))
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append(ParameterInfo(
            name=arg.arg,
            annotation=_unparse(arg.annotation),
            default=_unparse(default),
        ))
    return params


def _function_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
    return FunctionInfo(
        name=node.name,
        parameters=_extract_parameters(node.args),
        return_annotation=_unparse(node.returns),
        docstring=ast.get_docstring(node),
        is_async=isinstance(node, ast.AsyncFunctionDef),
        lineno=node.lineno,
    )


def analyze_file(path: Path, relative_path: str) -> FileAnalysis:
    module_name = relative_path[:-3].replace("/", ".").replace("\\", ".")
    if module_name.endswith(".__init__"):
        module_name = module_name[: -len(".__init__")]

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=relative_path)
    except (SyntaxError, UnicodeDecodeError) as exc:
        return FileAnalysis(file_path=relative_path, module_name=module_name, parse_error=str(exc))

    imports: list[str] = []
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_function_info(node))
        elif isinstance(node, ast.ClassDef):
            methods = [
                _function_info(item)
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            classes.append(ClassInfo(
                name=node.name,
                docstring=ast.get_docstring(node),
                methods=methods,
                lineno=node.lineno,
            ))

    return FileAnalysis(
        file_path=relative_path,
        module_name=module_name,
        imports=imports,
        functions=functions,
        classes=classes,
    )


def analyze_project(root: Path, project_name: str) -> ParsedProjectContext:
    files: list[FileAnalysis] = []
    for py_file in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in py_file.relative_to(root).parts[:-1]):
            continue
        if _is_test_file(py_file):
            continue
        if len(files) >= MAX_FILES_ANALYZED:
            break
        relative = py_file.relative_to(root).as_posix()
        files.append(analyze_file(py_file, relative))

    requirements_path = root / "requirements.txt"
    has_requirements = requirements_path.exists()
    requirements_content = requirements_path.read_text(encoding="utf-8", errors="replace") if has_requirements else None

    return ParsedProjectContext(
        project_name=project_name,
        files=files,
        has_requirements=has_requirements,
        requirements_content=requirements_content,
    )

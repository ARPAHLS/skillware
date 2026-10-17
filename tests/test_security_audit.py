"""Security and AST integrity audits for skills and framework."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import List, Tuple

import pytest

from skillware.core.base_skill import BaseSkill

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
SKILLWARE_ROOT = REPO_ROOT / "skillware"

FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__"})


def _discover_python_files(root_dir: Path, exclude_tests: bool = True) -> List[Path]:
    py_files: List[Path] = []
    if not root_dir.is_dir():
        return py_files
    for p in root_dir.rglob("*.py"):
        if exclude_tests and p.name.startswith("test_"):
            continue
        py_files.append(p)
    return sorted(py_files)


def test_no_dynamic_code_execution_primitives_in_skills():
    """Verify that no skill contains eval(), exec(), compile(), or __import__()."""
    files = _discover_python_files(SKILLS_ROOT, exclude_tests=False)
    assert files, "expected at least one Python file under skills/"

    violations: List[Tuple[str, str, int]] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as exc:
            pytest.fail(f"Syntax error in {file_path}: {exc}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    rel_path = file_path.relative_to(REPO_ROOT).as_posix()
                    violations.append((rel_path, node.func.id, node.lineno))

    assert (
        not violations
    ), "Forbidden dynamic execution calls found in skills:\n" + "\n".join(
        f"  {path}:{line} calls {fn}()" for path, fn, line in violations
    )


def test_no_direct_credential_reads_from_os_environ():
    """
    Ensure skills do not bypass BaseSkill.credential() by reading API keys directly
    from os.environ.
    """
    files = _discover_python_files(SKILLS_ROOT, exclude_tests=True)
    violations: List[Tuple[str, str, int]] = []

    # Whitelisted non-credential environment variables (e.g. scratch directory paths)
    allowed_env_vars = frozenset({"SKILLWARE_SCRATCH_DIR"})

    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as exc:
            pytest.fail(f"Syntax error in {file_path}: {exc}")

        for node in ast.walk(tree):
            # Check os.environ.get("...") calls
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "environ"
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "os"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    var_name = str(node.args[0].value)
                    if var_name not in allowed_env_vars:
                        rel_path = file_path.relative_to(REPO_ROOT).as_posix()
                        violations.append((rel_path, var_name, node.lineno))

            # Check os.environ["..."] subscript reads
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "environ"
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
            ):
                if isinstance(node.slice, ast.Constant):
                    var_name = str(node.slice.value)
                    if var_name not in allowed_env_vars:
                        rel_path = file_path.relative_to(REPO_ROOT).as_posix()
                        violations.append((rel_path, var_name, node.lineno))

    assert not violations, (
        "Direct os.environ credential reads found in skill code. Use self.credential() instead:\n"
        + "\n".join(
            f"  {path}:{line} reads os.environ['{var}']"
            for path, var, line in violations
        )
    )


def test_credential_fn_sandboxing_isolation(monkeypatch):
    """Verify that BaseSkill credential_fn provides complete sandboxed resolution."""
    monkeypatch.delenv("PRIVATE_SECRET", raising=False)

    resolved_keys: List[str] = []

    def mock_key_vault(key: str) -> str | None:
        resolved_keys.append(key)
        if key == "PRIVATE_SECRET":
            return "super-secret-vault-token"
        return None

    class _MockSkill(BaseSkill):
        @property
        def manifest(self):
            return {"name": "test/mock_skill"}

        def execute(self, params):
            return {"token": self.credential("PRIVATE_SECRET")}

    skill = _MockSkill(credential_fn=mock_key_vault)
    result = skill.execute({})

    assert result["token"] == "super-secret-vault-token"
    assert resolved_keys == ["PRIVATE_SECRET"]
    # Ensure os.environ was never populated or accessed
    assert "PRIVATE_SECRET" not in os.environ

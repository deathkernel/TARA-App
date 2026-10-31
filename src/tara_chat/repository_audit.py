"""Static repository audit for the conversation-first TARA runtime."""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class AuditIssue:
    code: str
    path: str
    detail: str
    severity: str = "error"


@dataclass(frozen=True)
class AuditReport:
    files_scanned: int
    python_files: int
    workflow_files: int
    issues: tuple[AuditIssue, ...]
    fingerprint: str

    @property
    def healthy(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


class RepositoryAuditor:
    # Paths required by the current TARA-App monorepo.
    REQUIRED_FILES = (
        "pyproject.toml",
        "src/tara_app/__init__.py",
        "src/tara_app/cli.py",
        "src/tara_chat/__init__.py",
        "src/tara_chat/brain.py",
        "src/tara_chat/ollama_provider.py",
        "src/tara_chat/memory.py",
        "tests/test_app_core.py",
        ".github/workflows/ci.yml",
    )

    IGNORED_DIRECTORIES = frozenset({
        ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", "node_modules", "build", "dist",
        "coverage", ".tox",
    })

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(str(self.root))

    def audit(self) -> AuditReport:
        issues: list[AuditIssue] = []
        python_files = sorted(self._python_files())
        workflow_directory = self.root / ".github" / "workflows"
        workflow_files = (
            sorted(
                path for path in workflow_directory.iterdir()
                if self._is_repository_file(path)
            )
            if workflow_directory.is_dir() and not workflow_directory.is_symlink()
            else []
        )

        for path in python_files:
            self._audit_python(path, issues)

        for relative in self.REQUIRED_FILES:
            if not self._is_repository_file(self.root / relative):
                issues.append(AuditIssue("MISSING_REQUIRED_FILE", relative, "required conversation runtime file is missing"))

        pytest_workflows = []
        for path in workflow_files:
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "python -m pytest" in content:
                pytest_workflows.append(path)
        if len(pytest_workflows) > 1:
            names = ", ".join(str(path.relative_to(self.root)) for path in pytest_workflows)
            issues.append(AuditIssue(
                "DUPLICATE_PYTEST_WORKFLOWS",
                ".github/workflows",
                f"multiple workflows run the full pytest suite: {names}",
            ))

        parts = [f"{issue.code}|{issue.path}|{issue.detail}" for issue in issues]
        fingerprint = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
        return AuditReport(
            files_scanned=len(python_files) + len(workflow_files),
            python_files=len(python_files),
            workflow_files=len(workflow_files),
            issues=tuple(sorted(issues, key=lambda item: (item.code, item.path, item.detail))),
            fingerprint=fingerprint,
        )

    def _is_repository_file(self, path: Path) -> bool:
        """Accept regular files whose resolved targets remain inside the audit root."""
        try:
            if path.is_symlink() or not path.is_file():
                return False
            path.resolve(strict=True).relative_to(self.root)
        except (OSError, RuntimeError, ValueError):
            return False
        return True

    def _python_files(self):
        """Walk the repository while pruning generated trees and external file links."""
        for current, directories, filenames in os.walk(self.root, topdown=True, followlinks=False):
            directories[:] = sorted(
                name for name in directories
                if name not in self.IGNORED_DIRECTORIES
            )
            for filename in sorted(filenames):
                path = Path(current) / filename
                if filename.endswith(".py") and self._is_repository_file(path):
                    yield path

    def _audit_python(self, path: Path, issues: list[AuditIssue]) -> None:
        relative = str(path.relative_to(self.root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            issues.append(AuditIssue("PYTHON_SYNTAX", relative, str(exc)))
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hash":
                issues.append(AuditIssue(
                    "NONDETERMINISTIC_HASH",
                    relative,
                    "built-in hash() is process-randomized; use stable hashing for persisted/fingerprint logic",
                    severity="warning",
                ))

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Audit the TARA conversation runtime")
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    report = RepositoryAuditor(args.root).audit()
    print(
        f"TARA audit: healthy={report.healthy} "
        f"python_files={report.python_files} workflow_files={report.workflow_files} "
        f"issues={len(report.issues)} fingerprint={report.fingerprint}"
    )
    for issue in report.issues:
        print(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.detail}")
    return 0 if report.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())

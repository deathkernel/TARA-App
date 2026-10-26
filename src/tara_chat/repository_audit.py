"""Static repository audit for the conversation-first TARA runtime."""
from __future__ import annotations

import ast
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
    REQUIRED_FILES = (
        "requirements.txt",
        "src/__main__.py",
        "src/brain.py",
        "src/ollama_provider.py",
        "src/memory.py",
        "tests/test_tara_cli.py",
    )

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(str(self.root))

    def audit(self) -> AuditReport:
        issues: list[AuditIssue] = []
        python_files = sorted(
            path for path in self.root.rglob("*.py")
            if not self._ignored(path)
        )
        workflow_files = sorted(
            path for path in (self.root / ".github" / "workflows").glob("*")
            if path.is_file()
        )

        for path in python_files:
            self._audit_python(path, issues)

        for relative in self.REQUIRED_FILES:
            if not (self.root / relative).is_file():
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

    @staticmethod
    def _ignored(path: Path) -> bool:
        return any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts)


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

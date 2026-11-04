"""Static repository audit for the conversation-first TARA runtime."""
from __future__ import annotations

import ast
import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterator


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


def _display_text(value: object, *, limit: int = 240) -> str:
    text = "".join(char for char in str(value or "") if char.isprintable())
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


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
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise FileNotFoundError(str(self.root))

    def audit(self) -> AuditReport:
        issues: list[AuditIssue] = []
        python_files = sorted(self._python_files(issues))
        workflow_directory = self.root / ".github" / "workflows"
        workflow_files: list[Path] = []
        if workflow_directory.is_dir() and not workflow_directory.is_symlink():
            try:
                workflow_files = sorted(
                    path for path in workflow_directory.iterdir()
                    if self._is_repository_file(path)
                )
            except OSError:
                issues.append(AuditIssue(
                    "SCAN_ERROR", ".github/workflows",
                    "workflow directory could not be enumerated",
                ))

        for path in python_files:
            self._audit_python(path, issues)

        for relative in self.REQUIRED_FILES:
            if not self._is_repository_file(self.root / relative):
                issues.append(AuditIssue(
                    "MISSING_REQUIRED_FILE", relative,
                    "required conversation runtime file is missing",
                ))

        pytest_workflows = []
        for path in workflow_files:
            relative = str(path.relative_to(self.root))
            try:
                content = self._read_repository_text(path)
            except (OSError, UnicodeDecodeError, ValueError):
                issues.append(AuditIssue(
                    "WORKFLOW_READ_ERROR", relative,
                    "workflow file could not be read safely",
                ))
                continue
            if "python -m pytest" in content:
                pytest_workflows.append(path)
        if len(pytest_workflows) > 1:
            names = ", ".join(str(path.relative_to(self.root)) for path in pytest_workflows)
            issues.append(AuditIssue(
                "DUPLICATE_PYTEST_WORKFLOWS",
                ".github/workflows",
                "multiple workflows contain a python -m pytest invocation "
                f"(including targeted test commands): {names}",
            ))

        ordered_issues = tuple(sorted(issues, key=lambda item: (item.code, item.path, item.detail)))
        parts = [f"{issue.code}|{issue.path}|{issue.detail}" for issue in ordered_issues]
        fingerprint = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
        return AuditReport(
            files_scanned=len(python_files) + len(workflow_files),
            python_files=len(python_files),
            workflow_files=len(workflow_files),
            issues=ordered_issues,
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

    def _read_repository_text(self, path: Path) -> str:
        """Read a file without following symlinks or escaping the audit root."""
        relative = path.relative_to(self.root)
        if not relative.parts:
            raise OSError("repository file path is empty")

        supports_openat = (
            os.open in getattr(os, "supports_dir_fd", set())
            and hasattr(os, "O_NOFOLLOW")
            and hasattr(os, "O_DIRECTORY")
        )
        if supports_openat:
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            root_fd = os.open(self.root, flags | os.O_DIRECTORY | os.O_NOFOLLOW)
            current_fd = root_fd
            try:
                for part in relative.parts[:-1]:
                    next_fd = os.open(
                        part, flags | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                    if current_fd != root_fd:
                        os.close(current_fd)
                    current_fd = next_fd
                file_fd = os.open(
                    relative.parts[-1], flags | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=current_fd,
                )
                with os.fdopen(file_fd, "r", encoding="utf-8") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise OSError("repository entry is not a regular file")
                    return stream.read()
            finally:
                if current_fd != root_fd:
                    os.close(current_fd)
                os.close(root_fd)

        # Windows does not expose openat/dir_fd for os.open. Check every parent
        # before opening, then compare the opened file identity and resolved
        # path afterwards so a replaced symlink or file is rejected.
        current = self.root
        for part in relative.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise OSError("repository path contains a symlink")
            current.resolve(strict=True).relative_to(self.root)
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise OSError("repository entry is not a regular file")
        with path.open("r", encoding="utf-8") as stream:
            opened = os.fstat(stream.fileno())
            after = path.lstat()
            resolved = path.resolve(strict=True)
            resolved.relative_to(self.root)
            identity = (opened.st_dev, opened.st_ino)
            if (
                stat.S_ISLNK(after.st_mode)
                or not stat.S_ISREG(opened.st_mode)
                or identity != (before.st_dev, before.st_ino)
                or identity != (after.st_dev, after.st_ino)
            ):
                raise OSError("repository file changed while it was being opened")
            return stream.read()

    def _python_files(self, issues: list[AuditIssue] | None = None) -> Iterator[Path]:
        """Walk the repository while pruning generated trees and reporting scan errors."""
        def onerror(error: OSError) -> None:
            if issues is None:
                return
            filename = getattr(error, "filename", None)
            relative = "."
            if filename:
                try:
                    relative = str(Path(filename).resolve(strict=False).relative_to(self.root))
                except (OSError, RuntimeError, ValueError):
                    relative = "."
            issues.append(AuditIssue(
                "SCAN_ERROR", relative,
                "directory traversal was incomplete",
            ))

        for current, directories, filenames in os.walk(
            self.root, topdown=True, followlinks=False, onerror=onerror
        ):
            directories[:] = sorted(
                name for name in directories
                if name not in self.IGNORED_DIRECTORIES
                and not (Path(current) / name).is_symlink()
            )
            for filename in sorted(filenames):
                path = Path(current) / filename
                if filename.endswith(".py") and self._is_repository_file(path):
                    yield path

    def _audit_python(self, path: Path, issues: list[AuditIssue]) -> None:
        relative = str(path.relative_to(self.root))
        try:
            source = self._read_repository_text(path)
        except (OSError, UnicodeDecodeError, ValueError):
            issues.append(AuditIssue(
                "PYTHON_READ_ERROR", relative,
                "Python source could not be read safely",
            ))
            return
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            issues.append(AuditIssue("PYTHON_SYNTAX", relative, _display_text(exc)))
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
        print(
            f"{issue.severity.upper()} {issue.code} "
            f"{_display_text(issue.path, limit=240)}: {_display_text(issue.detail, limit=240)}"
        )
    return 0 if report.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())

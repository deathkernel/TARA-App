"""Read-only git helpers for the built-in MCP git server.

Operations are limited to inspected metadata and file content inside an
allowlisted repository root. No fetch, push, commit, checkout, or other
mutating commands. Invocations use fixed argv lists with ``shell=False``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_MAX_OUTPUT_BYTES = 256_000
_MAX_LOG_ENTRIES = 50
_TIMEOUT_SECONDS = 15.0


class GitReadError(ValueError):
    """Raised when a git read operation is rejected or fails safely."""


def _normalize_roots(roots: list[str] | tuple[str, ...]) -> tuple[Path, ...]:
    if not roots:
        raise GitReadError("at least one allowlisted git root is required")
    resolved: list[Path] = []
    for raw in roots:
        if not isinstance(raw, str) or not raw.strip():
            raise GitReadError("root paths must be non-empty strings")
        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            raise GitReadError(f"root is not a directory: {path}")
        resolved.append(path)
    return tuple(resolved)


def resolve_repo(path: str, roots: list[str] | tuple[str, ...]) -> Path:
    """Resolve a path that must be a git work tree under an allowlisted root."""
    if not isinstance(path, str) or not path.strip():
        raise GitReadError("repo path must be a non-empty string")
    if len(path) > 1024:
        raise GitReadError("repo path is too long")
    allowed = _normalize_roots(roots)
    candidate = Path(path).expanduser().resolve()
    under: Path | None = None
    for root in allowed:
        try:
            candidate.relative_to(root)
            under = candidate
            break
        except ValueError:
            continue
    if under is None:
        raise GitReadError("repo path is outside the allowlisted roots")
    git_dir = under / ".git"
    if not git_dir.exists():
        raise GitReadError("path is not a git repository (missing .git)")
    return under


def _run_git(repo: Path, args: list[str]) -> str:
    argv = ["git", "-C", str(repo), *args]
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv, no shell
            argv,
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise GitReadError("git executable is not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitReadError("git command timed out") from exc
    if completed.returncode != 0:
        err = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
        raise GitReadError(err or f"git exited with status {completed.returncode}")
    out = completed.stdout or b""
    if len(out) > _MAX_OUTPUT_BYTES:
        raise GitReadError(f"git output exceeds {_MAX_OUTPUT_BYTES} byte limit")
    return out.decode("utf-8", errors="replace")


def git_status(repo_path: str, roots: list[str] | tuple[str, ...]) -> dict[str, str]:
    repo = resolve_repo(repo_path, roots)
    porcelain = _run_git(repo, ["status", "--porcelain=v1", "-b"])
    return {"repo": str(repo), "status": porcelain}


def git_log(
    repo_path: str,
    roots: list[str] | tuple[str, ...],
    *,
    max_count: int = 10,
) -> dict[str, object]:
    if type(max_count) is not int or not 1 <= max_count <= _MAX_LOG_ENTRIES:
        raise GitReadError(f"max_count must be an integer between 1 and {_MAX_LOG_ENTRIES}")
    repo = resolve_repo(repo_path, roots)
    fmt = "%H%x09%an%x09%ad%x09%s"
    text = _run_git(
        repo,
        ["log", f"-n{max_count}", f"--format={fmt}", "--date=iso-strict"],
    )
    entries: list[dict[str, str]] = []
    for line in text.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        entries.append(
            {
                "commit": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
            }
        )
    return {"repo": str(repo), "entries": entries}


def git_show_file(
    repo_path: str,
    roots: list[str] | tuple[str, ...],
    *,
    path: str,
    revision: str = "HEAD",
) -> dict[str, str]:
    if not isinstance(path, str) or not path.strip() or len(path) > 512:
        raise GitReadError("path must be a non-empty relative path")
    if path.startswith("/") or ".." in Path(path).parts:
        raise GitReadError("path must be relative without parent traversal")
    if not isinstance(revision, str) or not revision.strip() or len(revision) > 128:
        raise GitReadError("revision must be a non-empty identifier")
    rev = revision.strip()
    if rev.startswith("-"):
        raise GitReadError("revision must not start with '-'")
    rel = path.strip().replace("\\", "/")
    if rel.startswith("-"):
        raise GitReadError("path must not start with '-'")
    repo = resolve_repo(repo_path, roots)
    content = _run_git(repo, ["show", f"{rev}:{rel}"])
    return {"repo": str(repo), "revision": rev, "path": rel, "content": content}

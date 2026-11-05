"""Read-only scoped filesystem helpers for the built-in MCP server."""
from __future__ import annotations

import os
from pathlib import Path

_MAX_READ_BYTES = 256_000
_MAX_LIST_ENTRIES = 500


class ScopedFsError(ValueError):
    """Raised when a path is outside the allowlist or otherwise unsafe."""


def _normalize_roots(roots: list[str] | tuple[str, ...]) -> tuple[Path, ...]:
    if not roots:
        raise ScopedFsError("at least one allowlisted root is required")
    resolved: list[Path] = []
    for raw in roots:
        if not isinstance(raw, str) or not raw.strip():
            raise ScopedFsError("root paths must be non-empty strings")
        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            raise ScopedFsError(f"root is not a directory: {path}")
        resolved.append(path)
    return tuple(resolved)


def resolve_under_roots(path: str, roots: list[str] | tuple[str, ...]) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ScopedFsError("path must be a non-empty string")
    if len(path) > 1024:
        raise ScopedFsError("path is too long")
    allowed = _normalize_roots(roots)
    candidate = Path(path).expanduser().resolve()
    for root in allowed:
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    raise ScopedFsError("path is outside the allowlisted roots")


def list_directory(path: str, roots: list[str] | tuple[str, ...]) -> list[dict[str, str]]:
    target = resolve_under_roots(path, roots)
    if not target.is_dir():
        raise ScopedFsError("path is not a directory")
    entries: list[dict[str, str]] = []
    with os.scandir(target) as iterator:
        for entry in iterator:
            if len(entries) >= _MAX_LIST_ENTRIES:
                break
            kind = "dir" if entry.is_dir(follow_symlinks=False) else "file"
            if entry.is_symlink():
                kind = "symlink"
            entries.append({"name": entry.name, "kind": kind})
    entries.sort(key=lambda item: item["name"].lower())
    return entries


def read_text_file(path: str, roots: list[str] | tuple[str, ...]) -> str:
    target = resolve_under_roots(path, roots)
    if not target.is_file():
        raise ScopedFsError("path is not a regular file")
    if target.is_symlink():
        raise ScopedFsError("refusing to read symlink target directly")
    data = target.read_bytes()
    if len(data) > _MAX_READ_BYTES:
        raise ScopedFsError(f"file exceeds {_MAX_READ_BYTES} byte read limit")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ScopedFsError("file is not valid UTF-8 text") from exc

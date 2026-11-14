"""Format SITA Code proposed_changes as a read-only unified-diff style preview.

This module never writes files, never applies patches, and never executes code.
It only turns structured proposal data into bounded text for UI review.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

_MAX_CHANGES = 64
_MAX_PATH_LEN = 512
_MAX_LINE_LEN = 4_000
_MAX_LINES_PER_SIDE = 2_000
_MAX_OUTPUT_CHARS = 200_000
_CONTENT_OLD_KEYS = ("old_content", "original", "before")
_CONTENT_NEW_KEYS = ("new_content", "content", "after")


class DiffPreviewError(ValueError):
    """Raised when proposed_changes cannot be formatted safely."""


def format_proposed_changes_diff(proposed_changes: Sequence[Mapping[str, Any]]) -> str:
    """Return a unified-diff style preview string for structured proposals.

    Accepted change objects:

    - path: relative path string
    - action: "create" | "modify" | "delete" | "rename" (default "modify")
    - old_content / original / before: previous file text
    - new_content / content / after: proposed file text
    - diff: preformatted unified diff (used only when no content sides are supplied)
    - from_path / to_path: for rename (from_path required when action is rename)

    Empty input returns an empty string. Oversized or invalid input raises
    DiffPreviewError. Output is capped so a hostile proposal cannot blow the UI.
    """
    if not isinstance(proposed_changes, Sequence) or isinstance(proposed_changes, (str, bytes)):
        raise DiffPreviewError("proposed_changes must be a list of objects")
    if len(proposed_changes) > _MAX_CHANGES:
        raise DiffPreviewError(f"proposed_changes exceeds {_MAX_CHANGES} entries")

    blocks: list[str] = []
    total = 0
    for index, raw in enumerate(proposed_changes):
        if not isinstance(raw, Mapping):
            raise DiffPreviewError(f"proposed_changes[{index}] must be an object")
        block = _format_one(dict(raw), index)
        if not block:
            continue
        if total + len(block) + 1 > _MAX_OUTPUT_CHARS:
            raise DiffPreviewError("diff preview exceeds the output size limit")
        blocks.append(block)
        total += len(block) + 1
    return "\n".join(blocks)


def _has_content_side(change: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(key in change and change[key] is not None for key in keys)


def _format_one(change: dict[str, Any], index: int) -> str:
    action = change.get("action", "modify")
    if action is None:
        action = "modify"
    if not isinstance(action, str) or action not in {"create", "modify", "delete", "rename"}:
        raise DiffPreviewError(f"proposed_changes[{index}].action is invalid")

    if "diff" in change and change["diff"] is not None and not isinstance(change["diff"], str):
        raise DiffPreviewError(f"proposed_changes[{index}].diff must be a string")

    has_old = _has_content_side(change, _CONTENT_OLD_KEYS)
    has_new = _has_content_side(change, _CONTENT_NEW_KEYS)
    preformatted = change.get("diff") if isinstance(change.get("diff"), str) else None

    # Prefer structured content when either side is supplied (avoids stale diffs).
    if preformatted is not None and preformatted.strip() and not has_old and not has_new:
        if len(preformatted) > _MAX_OUTPUT_CHARS:
            raise DiffPreviewError(f"proposed_changes[{index}].diff is too large")
        if preformatted.lstrip().startswith("---"):
            return preformatted
        old_hdr, new_hdr = _headers_for_action(change, action, index)
        return f"{old_hdr}\n{new_hdr}\n{preformatted}"

    path = _path(change.get("path") or change.get("to_path") or f"change-{index}")
    if action == "rename":
        from_path = change.get("from_path")
        if not isinstance(from_path, str):
            raise DiffPreviewError(f"proposed_changes[{index}].from_path is required for rename")
        old_label = _path(from_path)
        new_label = path
    elif action == "create":
        old_label = None  # /dev/null marker
        new_label = path
    elif action == "delete":
        old_label = path
        new_label = None
    else:
        old_label = path
        new_label = path

    old_text = _side_text(change, _CONTENT_OLD_KEYS, index, "old")
    new_text = _side_text(change, _CONTENT_NEW_KEYS, index, "new")

    if action == "delete":
        new_text = ""
    if action == "create":
        old_text = ""

    old_lines = _lines(old_text)
    new_lines = _lines(new_text)
    body = _simple_unified(old_lines, new_lines)
    old_hdr = "--- /dev/null" if old_label is None else f"--- a/{old_label}"
    new_hdr = "+++ /dev/null" if new_label is None else f"+++ b/{new_label}"
    return f"{old_hdr}\n{new_hdr}\n{body}"


def _headers_for_action(change: dict[str, Any], action: str, index: int) -> tuple[str, str]:
    path = _path(change.get("path") or change.get("to_path") or f"change-{index}")
    if action == "create":
        return "--- /dev/null", f"+++ b/{path}"
    if action == "delete":
        return f"--- a/{path}", "+++ /dev/null"
    if action == "rename":
        from_path = change.get("from_path")
        if not isinstance(from_path, str):
            raise DiffPreviewError(f"proposed_changes[{index}].from_path is required for rename")
        return f"--- a/{_path(from_path)}", f"+++ b/{path}"
    return f"--- a/{path}", f"+++ b/{path}"


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_PATH_LEN:
        raise DiffPreviewError("change path must be a non-empty bounded string")
    if value != value.strip():
        raise DiffPreviewError("change path must not have leading or trailing whitespace")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise DiffPreviewError("change path must not contain control characters")
    cleaned = value.replace("\\", "/")
    if cleaned.startswith("/") or cleaned.startswith("../") or "/../" in f"/{cleaned}/":
        raise DiffPreviewError("change path must be a relative path without parent traversal")
    if not cleaned.strip("."):
        raise DiffPreviewError("change path is invalid")
    return cleaned


def _side_text(change: Mapping[str, Any], keys: tuple[str, ...], index: int, side: str) -> str:
    for key in keys:
        if key in change and change[key] is not None:
            value = change[key]
            if not isinstance(value, str):
                raise DiffPreviewError(f"proposed_changes[{index}].{key} must be a string")
            if len(value) > _MAX_LINE_LEN * _MAX_LINES_PER_SIDE:
                raise DiffPreviewError(f"proposed_changes[{index}] {side} content is too large")
            return value
    return ""


def _lines(text: str) -> list[str]:
    if not text:
        return []
    parts = text.splitlines()
    if len(parts) > _MAX_LINES_PER_SIDE:
        raise DiffPreviewError("a proposed file side exceeds the line limit")
    for line in parts:
        if len(line) > _MAX_LINE_LEN:
            raise DiffPreviewError("a proposed line exceeds the character limit")
    return parts


def _simple_unified(old_lines: list[str], new_lines: list[str]) -> str:
    """Minimal line-oriented unified hunk (not a full Myers diff)."""
    if old_lines == new_lines:
        return "@@ no changes @@\n"
    old_start = 0 if not old_lines else 1
    new_start = 0 if not new_lines else 1
    out: list[str] = [f"@@ -{old_start},{len(old_lines)} +{new_start},{len(new_lines)} @@"]
    for line in old_lines:
        out.append(f"-{line}")
    for line in new_lines:
        out.append(f"+{line}")
    return "\n".join(out) + "\n"

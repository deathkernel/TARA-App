"""Format TARA-Code proposed_changes as a read-only unified-diff style preview.

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


class DiffPreviewError(ValueError):
    """Raised when proposed_changes cannot be formatted safely."""


def format_proposed_changes_diff(proposed_changes: Sequence[Mapping[str, Any]]) -> str:
    """Return a unified-diff style preview string for structured proposals.

    Accepted change objects (all fields optional except path when content is present):

    - path: relative path string
    - action: "create" | "modify" | "delete" | "rename" (default "modify")
    - old_content / original / before: previous file text
    - new_content / content / after: proposed file text
    - diff: preformatted unified diff (used when present and no content sides)
    - from_path / to_path: for rename

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


def _format_one(change: dict[str, Any], index: int) -> str:
    action = change.get("action", "modify")
    if action is None:
        action = "modify"
    if not isinstance(action, str) or action not in {"create", "modify", "delete", "rename"}:
        raise DiffPreviewError(f"proposed_changes[{index}].action is invalid")

    if isinstance(change.get("diff"), str) and change["diff"].strip():
        diff_text = change["diff"]
        if len(diff_text) > _MAX_OUTPUT_CHARS:
            raise DiffPreviewError(f"proposed_changes[{index}].diff is too large")
        path = _path(change.get("path") or change.get("to_path") or f"change-{index}")
        header = f"--- a/{path}\n+++ b/{path}\n"
        return header + diff_text if not diff_text.lstrip().startswith("---") else diff_text

    path = _path(change.get("path") or change.get("to_path") or f"change-{index}")
    from_path = change.get("from_path")
    if action == "rename":
        old_label = _path(from_path if isinstance(from_path, str) else path)
        new_label = path
    elif action == "create":
        old_label = "/dev/null"
        new_label = path
    elif action == "delete":
        old_label = path
        new_label = "/dev/null"
    else:
        old_label = path
        new_label = path

    old_text = _side_text(change, ("old_content", "original", "before"), index, "old")
    new_text = _side_text(change, ("new_content", "content", "after"), index, "new")

    if action == "delete":
        new_text = ""
    if action == "create":
        old_text = ""

    old_lines = _lines(old_text)
    new_lines = _lines(new_text)
    body = _simple_unified(old_lines, new_lines)
    return f"--- a/{old_label}\n+++ b/{new_label}\n{body}"


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_PATH_LEN:
        raise DiffPreviewError("change path must be a non-empty bounded string")
    # Reject absolute and parent-traversal paths in preview labels only.
    cleaned = value.replace("\\", "/").strip()
    if cleaned.startswith("/") or cleaned.startswith("../") or "/../" in f"/{cleaned}/":
        raise DiffPreviewError("change path must be a relative path without parent traversal")
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
    """Minimal line-oriented unified hunk (not a full Myers diff).

    Sufficient for review UI when proposals carry full file sides. Prefer a
    preformatted `diff` field when the engine already computed one.
    """
    if old_lines == new_lines:
        return "@@ no changes @@\n"
    out: list[str] = [f"@@ -1,{len(old_lines)} +1,{len(new_lines)} @@"]
    # Emit a single hunk: context-free old removals then new additions.
    # This stays deterministic and avoids pulling in difflib for the first slice.
    for line in old_lines:
        out.append(f"-{line}")
    for line in new_lines:
        out.append(f"+{line}")
    return "\n".join(out) + "\n"

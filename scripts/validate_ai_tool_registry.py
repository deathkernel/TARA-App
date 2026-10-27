#!/usr/bin/env python3
"""Validate TARA-App's machine-readable AI tool registry without installing tools."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "ai_tool_registry.json"
REQUIRED_TOOL_FIELDS = {"id", "name", "repository", "placement", "kind", "priority", "status", "enabled", "adapter"}
ALLOWED_STATUSES = {"candidate", "reference_only", "blocked_pending_sandbox", "approved", "disabled"}
BLOCKED_EXECUTION_AGENTS = {"openhands", "open-interpreter"}


def validate_registry(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must equal 1")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
        policy = {}
    for key in ("default_enabled", "default_network_access", "default_shell_access", "auto_install", "auto_merge"):
        if policy.get(key) is not False:
            errors.append(f"policy.{key} must be false")

    tools = data.get("tools")
    if not isinstance(tools, list):
        return errors + ["tools must be an array"]

    if len(tools) != 30:
        errors.append(f"expected exactly 30 tool records, found {len(tools)}")

    seen: set[str] = set()
    for index, tool in enumerate(tools):
        prefix = f"tools[{index}]"
        if not isinstance(tool, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_TOOL_FIELDS - tool.keys()
        if missing:
            errors.append(f"{prefix} missing required fields: {', '.join(sorted(missing))}")
            continue
        tool_id = tool["id"]
        if not isinstance(tool_id, str) or not tool_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
            continue
        if tool_id in seen:
            errors.append(f"duplicate tool id: {tool_id}")
        seen.add(tool_id)
        if tool["enabled"] is not False:
            errors.append(f"{tool_id}: tools must remain disabled until individually reviewed")
        if tool["status"] not in ALLOWED_STATUSES:
            errors.append(f"{tool_id}: invalid status {tool['status']!r}")
        if not isinstance(tool["repository"], str) or not tool["repository"].startswith("https://github.com/"):
            errors.append(f"{tool_id}: repository must be an HTTPS GitHub URL")
        if tool_id in BLOCKED_EXECUTION_AGENTS:
            if tool.get("requires_hardened_sandbox") is not True:
                errors.append(f"{tool_id}: hardened sandbox requirement must be explicit")
            if tool["status"] != "blocked_pending_sandbox":
                errors.append(f"{tool_id}: must remain blocked_pending_sandbox")
            if tool.get("shell_access") is not False:
                errors.append(f"{tool_id}: shell access must remain false")
    return errors


def main() -> int:
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Registry load failed: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("Registry root must be a JSON object", file=sys.stderr)
        return 2

    errors = validate_registry(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Registry valid: {len(data['tools'])} unique tool records; all disabled by default.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

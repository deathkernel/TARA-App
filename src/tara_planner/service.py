"""Bounded planning and dependency validation without task execution."""
from __future__ import annotations
import re
from typing import Any

MODULE_ID = "planner"
CAPABILITIES = ("plan",)
_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_MAX_STEPS = 64

def _goal_steps(goal: str) -> list[dict[str, Any]]:
    fragments = [part.strip(" .;") for part in re.split(r"\s+(?:then|after that|and then)\s+|[;\n]+", goal, flags=re.I) if part.strip(" .;")]
    if len(fragments) > 1:
        return [{"id": f"step-{i+1}", "description": text, "depends_on": [f"step-{i}"] if i else []} for i, text in enumerate(fragments)]
    return [
        {"id": "define", "description": f"Confirm the goal and completion criteria for: {goal}", "depends_on": []},
        {"id": "prepare", "description": "Identify prerequisites, required inputs, and constraints", "depends_on": ["define"]},
        {"id": "work", "description": "Complete the requested work in reviewable steps", "depends_on": ["prepare"]},
        {"id": "verify", "description": "Check the result against the completion criteria", "depends_on": ["work"]},
    ]

def _order(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 1 <= len(steps) <= _MAX_STEPS:
        raise ValueError("steps must contain 1 to 64 items")
    by_id: dict[str, dict[str, Any]] = {}
    dependencies: dict[str, set[str]] = {}
    for raw in steps:
        if not isinstance(raw, dict):
            raise ValueError("each step must be an object")
        step_id, description, deps = raw.get("id"), raw.get("description"), raw.get("depends_on", [])
        if not isinstance(step_id, str) or not _ID.fullmatch(step_id) or step_id in by_id:
            raise ValueError("step IDs must be unique simple identifiers")
        if not isinstance(description, str) or not description.strip() or len(description) > 1000:
            raise ValueError("step descriptions must contain 1 to 1000 characters")
        if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
            raise ValueError("depends_on must be a list of step IDs")
        unique_deps = list(dict.fromkeys(deps))
        by_id[step_id] = {"id": step_id, "description": description.strip(), "depends_on": unique_deps}
        dependencies[step_id] = set(unique_deps)
    for step_id, deps in dependencies.items():
        if step_id in deps or any(dep not in by_id for dep in deps):
            raise ValueError("steps contain a self or unknown dependency")
    ready = sorted(step_id for step_id, deps in dependencies.items() if not deps)
    order = []
    while ready:
        step_id = ready.pop(0)
        order.append(step_id)
        for other_id in sorted(dependencies):
            dependencies[other_id].discard(step_id)
            if not dependencies[other_id] and other_id not in order and other_id not in ready:
                ready.append(other_id)
        ready.sort()
    if len(order) != len(by_id):
        raise ValueError("steps contain a dependency cycle")
    return [by_id[step_id] for step_id in order]

def execute(action: str, inputs: dict[str, Any], *, approval_token: str | None = None) -> tuple[str, dict[str, Any], str | None]:
    if action != "plan":
        return "permission_denied", {}, "unsupported planner capability"
    goal = inputs.get("question", inputs.get("goal", ""))
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 20_000:
        raise ValueError("goal must be non-empty bounded text")
    raw_steps = inputs.get("steps")
    steps = _goal_steps(goal.strip()) if raw_steps is None else raw_steps
    if not isinstance(steps, list):
        raise ValueError("steps must be a list")
    return "success", {"goal": goal.strip(), "steps": _order(steps), "executable": False, "requires_user_review": True}, None


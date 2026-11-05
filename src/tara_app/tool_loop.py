"""Bounded multi-step tool-loop plans for TARA specialists.

Plans are **data**. This module validates structure and can run steps only through
an injected executor. It never interprets model text as a shell command and never
grants itself approval. Mutating steps must carry an explicit approval token
supplied by the application layer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol

_MAX_STEPS = 16
_MAX_ARG_BYTES = 64_000
_MAX_RESULT_CHARS = 100_000


class ToolStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"


class ToolLoopError(ValueError):
    """Raised when a plan or step is invalid."""


@dataclass(frozen=True, slots=True)
class ToolStep:
    step_id: str
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    read_only: bool = True
    requires_approval: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or not self.step_id.strip() or len(self.step_id) > 64:
            raise ToolLoopError("step_id must be a non-empty identifier ≤64 chars")
        if not isinstance(self.tool_name, str) or not self.tool_name.strip() or len(self.tool_name) > 128:
            raise ToolLoopError("tool_name must be a non-empty identifier ≤128 chars")
        if not isinstance(self.arguments, Mapping):
            raise ToolLoopError("arguments must be a mapping")
        try:
            encoded = json.dumps(dict(self.arguments), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ToolLoopError("arguments must be JSON-compatible") from exc
        if len(encoded) > _MAX_ARG_BYTES:
            raise ToolLoopError("arguments exceed size limit")
        if self.requires_approval and self.read_only:
            raise ToolLoopError("approval-gated steps must not be marked read_only")


@dataclass(frozen=True, slots=True)
class ToolPlan:
    plan_id: str
    steps: tuple[ToolStep, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or not self.plan_id.strip() or len(self.plan_id) > 64:
            raise ToolLoopError("plan_id must be a non-empty identifier ≤64 chars")
        if self.schema_version != "1.0":
            raise ToolLoopError("unsupported tool plan schema version")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ToolLoopError("plan must include at least one step")
        if len(self.steps) > _MAX_STEPS:
            raise ToolLoopError(f"plan exceeds {_MAX_STEPS} step limit")
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ToolLoopError("plan cannot contain duplicate step_ids")


@dataclass(frozen=True, slots=True)
class ToolStepResult:
    step_id: str
    status: ToolStepStatus
    output: str = ""
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or not self.step_id.strip():
            raise ToolLoopError("step_id is required")
        if not isinstance(self.status, ToolStepStatus):
            raise ToolLoopError("status must be a ToolStepStatus")
        if len(self.output) > _MAX_RESULT_CHARS:
            object.__setattr__(self, "output", self.output[:_MAX_RESULT_CHARS] + "\n…[truncated]")


@dataclass(frozen=True, slots=True)
class ToolLoopResult:
    plan_id: str
    status: str
    steps: tuple[ToolStepResult, ...]
    error_message: str | None = None


class ToolExecutor(Protocol):
    def __call__(
        self,
        step: ToolStep,
        *,
        approval_token: str | None,
    ) -> ToolStepResult:
        ...


def run_tool_plan(
    plan: ToolPlan,
    executor: ToolExecutor,
    *,
    approval_tokens: Mapping[str, str] | None = None,
    stop_on_failure: bool = True,
) -> ToolLoopResult:
    """Execute a validated plan sequentially through ``executor``.

    Approval-gated steps pause as ``WAITING_APPROVAL`` unless ``approval_tokens``
    contains a token keyed by ``step_id``. Remaining steps are skipped when a
    hard failure occurs and ``stop_on_failure`` is true.
    """
    if not isinstance(plan, ToolPlan):
        raise ToolLoopError("plan must be a ToolPlan")
    tokens = dict(approval_tokens or {})
    results: list[ToolStepResult] = []

    for step in plan.steps:
        if step.requires_approval and step.step_id not in tokens:
            results.append(
                ToolStepResult(
                    step.step_id,
                    ToolStepStatus.WAITING_APPROVAL,
                    error_code="approval_required",
                    error_message="Step requires an explicit approval token",
                )
            )
            for remaining in plan.steps[len(results) :]:
                results.append(
                    ToolStepResult(
                        remaining.step_id,
                        ToolStepStatus.SKIPPED,
                        error_code="blocked",
                        error_message="Blocked by upstream approval wait",
                    )
                )
            return ToolLoopResult(plan.plan_id, "waiting_approval", tuple(results))

        token = tokens.get(step.step_id)
        try:
            result = executor(step, approval_token=token)
        except Exception as exc:  # noqa: BLE001 — boundary
            result = ToolStepResult(
                step.step_id,
                ToolStepStatus.FAILED,
                error_code="executor_error",
                error_message=str(exc)[:500] or "executor failed",
            )
        if not isinstance(result, ToolStepResult) or result.step_id != step.step_id:
            result = ToolStepResult(
                step.step_id,
                ToolStepStatus.FAILED,
                error_code="invalid_result",
                error_message="Executor returned an invalid step result",
            )
        results.append(result)
        if stop_on_failure and result.status in {
            ToolStepStatus.FAILED,
            ToolStepStatus.DENIED,
        }:
            for remaining in plan.steps[len(results) :]:
                results.append(
                    ToolStepResult(
                        remaining.step_id,
                        ToolStepStatus.SKIPPED,
                        error_code="upstream_failed",
                        error_message="Upstream step failed",
                    )
                )
            return ToolLoopResult(
                plan.plan_id,
                "failed" if result.status == ToolStepStatus.FAILED else "denied",
                tuple(results),
                error_message=result.error_message,
            )

    if all(item.status == ToolStepStatus.SUCCEEDED for item in results):
        status = "succeeded"
    elif any(item.status == ToolStepStatus.WAITING_APPROVAL for item in results):
        status = "waiting_approval"
    else:
        status = "partial"
    return ToolLoopResult(plan.plan_id, status, tuple(results))


def plan_from_mapping(raw: Mapping[str, Any]) -> ToolPlan:
    """Build a ToolPlan from a JSON-compatible mapping (e.g. model proposal)."""
    if not isinstance(raw, Mapping):
        raise ToolLoopError("plan must be a mapping")
    plan_id = raw.get("plan_id")
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list):
        raise ToolLoopError("steps must be a list")
    steps: list[ToolStep] = []
    for item in steps_raw:
        if not isinstance(item, Mapping):
            raise ToolLoopError("each step must be a mapping")
        steps.append(
            ToolStep(
                step_id=str(item.get("step_id", "")),
                tool_name=str(item.get("tool_name", "")),
                arguments=dict(item.get("arguments") or {}),
                read_only=bool(item.get("read_only", True)),
                requires_approval=bool(item.get("requires_approval", False)),
            )
        )
    return ToolPlan(plan_id=str(plan_id or ""), steps=tuple(steps))

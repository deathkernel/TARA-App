"""Versioned, transport-neutral contracts for coordinated TARA workflows.

These contracts define the data shape for a future coordinator. They do not
change the current Orchestrator dispatch path by themselves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


WORKFLOW_SCHEMA_VERSION = "1.0"


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    DENIED = "denied"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    DENIED = "denied"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class WorkflowRequest:
    request_id: str
    session_id: str
    input: Mapping[str, Any]
    schema_version: str = WORKFLOW_SCHEMA_VERSION
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.request_id, "request_id")
        _require_identifier(self.session_id, "session_id")
        if self.schema_version != WORKFLOW_SCHEMA_VERSION:
            raise ValueError("unsupported workflow request schema version")
        if not isinstance(self.input, Mapping):
            raise ValueError("workflow input must be a mapping")


@dataclass(frozen=True, slots=True)
class WorkflowStepSpec:
    step_id: str
    operation_id: str
    input: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    timeout_seconds: int = 30
    requires_approval: bool = False
    read_only: bool = True

    def __post_init__(self) -> None:
        _require_identifier(self.step_id, "step_id")
        _require_identifier(self.operation_id, "operation_id")
        if not isinstance(self.input, Mapping):
            raise ValueError("step input must be a mapping")
        if not isinstance(self.depends_on, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.depends_on
        ):
            raise ValueError("step dependencies must be a tuple of non-empty identifiers")
        if self.step_id in self.depends_on or len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("step dependencies must be unique and cannot include the step itself")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, int):
            raise ValueError("step timeout must be an integer")
        if not 1 <= self.timeout_seconds <= 600:
            raise ValueError("step timeout must be between 1 and 600 seconds")
        if self.requires_approval and self.read_only:
            raise ValueError("approval-gated steps must be explicitly marked as side-effecting")


@dataclass(frozen=True, slots=True)
class WorkflowStepResult:
    step_id: str
    status: StepStatus
    data: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    artifact_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.step_id, "step_id")
        if not isinstance(self.status, StepStatus):
            raise ValueError("step status must be a StepStatus")
        if not isinstance(self.data, Mapping):
            raise ValueError("step result data must be a mapping")
        if not isinstance(self.artifact_refs, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.artifact_refs
        ):
            raise ValueError("artifact references must be a tuple of non-empty strings")


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    request_id: str
    workflow_id: str
    status: WorkflowStatus
    steps: tuple[WorkflowStepResult, ...] = ()
    schema_version: str = WORKFLOW_SCHEMA_VERSION
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.request_id, "request_id")
        _require_identifier(self.workflow_id, "workflow_id")
        if self.schema_version != WORKFLOW_SCHEMA_VERSION:
            raise ValueError("unsupported workflow result schema version")
        if not isinstance(self.status, WorkflowStatus):
            raise ValueError("workflow status must be a WorkflowStatus")
        if not isinstance(self.steps, tuple) or any(
            not isinstance(step, WorkflowStepResult) for step in self.steps
        ):
            raise ValueError("workflow steps must be a tuple of WorkflowStepResult values")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("workflow result cannot contain duplicate step IDs")


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError(f"{name} must be a non-empty identifier of at most 128 characters")

"""In-process workflow execution engine for SITA.

Runs a validated WorkflowPlan against an injected step executor. This engine
owns step status, approval pauses, cancellation, and result aggregation. It does
not authorize side effects; the executor and existing Security/Orchestrator
gates remain responsible for permission checks.

The engine is intentionally not connected to live Orchestrator dispatch yet.
Wire-up requires parity tests against the current approval lifecycle.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from tara_app.workflow_contracts import (
    StepStatus,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStepResult,
    WorkflowStepSpec,
)


_TERMINAL_WORKFLOW_STATUSES = frozenset(
    {
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
        WorkflowStatus.DENIED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.TIMED_OUT,
    }
)


class StepExecutor(Protocol):
    """Callable that performs one workflow step and returns a result."""

    def __call__(self, step: WorkflowStepSpec, *, context: Mapping[str, Any]) -> WorkflowStepResult:
        """Execute one validated step using the supplied request context."""
        ...


@dataclass
class WorkflowRunState:
    """Mutable execution state for one workflow instance."""

    plan: WorkflowPlan
    status: WorkflowStatus = WorkflowStatus.PENDING
    step_results: dict[str, WorkflowStepResult] = field(default_factory=dict)
    cancelled: bool = False
    started_at: float | None = None
    finished_at: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    _active: bool = field(default=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def snapshot(self) -> WorkflowResult:
        """Return an immutable view of the current workflow state."""
        with self._lock:
            steps = tuple(
                self.step_results.get(
                    step.step_id,
                    WorkflowStepResult(step.step_id, StepStatus.PENDING),
                )
                for step in self.plan.steps
            )
            return WorkflowResult(
                request_id=self.plan.request_id,
                workflow_id=self.plan.workflow_id,
                status=self.status,
                steps=steps,
                error_code=self.error_code,
                error_message=self.error_message,
            )


class WorkflowEngine:
    """Execute DAG workflow plans with approval pauses and cancellation."""

    def __init__(self) -> None:
        """Initialize an engine with an empty run registry."""
        self._runs: dict[str, WorkflowRunState] = {}
        self._lock = threading.RLock()

    def create_run(self, plan: WorkflowPlan) -> WorkflowRunState:
        """Register a new workflow plan and return its mutable run state."""
        if not isinstance(plan, WorkflowPlan):
            raise TypeError("plan must be a WorkflowPlan")
        state = WorkflowRunState(plan=plan)
        with self._lock:
            if plan.workflow_id in self._runs:
                raise ValueError(f"workflow already exists: {plan.workflow_id}")
            self._runs[plan.workflow_id] = state
        return state

    def get_run(self, workflow_id: str) -> WorkflowRunState | None:
        """Look up a workflow run by its unique identifier."""
        with self._lock:
            return self._runs.get(workflow_id)

    def cancel(self, workflow_id: str) -> WorkflowResult:
        """Cancel a nonterminal run and mark unfinished steps cancelled."""
        state = self.get_run(workflow_id)
        if state is None:
            raise KeyError(f"unknown workflow: {workflow_id}")
        with state._lock:
            if state.status in _TERMINAL_WORKFLOW_STATUSES:
                return state.snapshot()
            state.cancelled = True
            state.status = WorkflowStatus.CANCELLED
            state.finished_at = time.monotonic()
            state.error_code = "cancelled"
            state.error_message = "Workflow was cancelled"
            for step in state.plan.steps:
                existing = state.step_results.get(step.step_id)
                if existing is None or existing.status in {
                    StepStatus.PENDING,
                    StepStatus.RUNNING,
                    StepStatus.WAITING_APPROVAL,
                }:
                    state.step_results[step.step_id] = WorkflowStepResult(
                        step.step_id,
                        StepStatus.CANCELLED,
                        error_code="cancelled",
                        error_message="Workflow was cancelled",
                    )
            return state.snapshot()

    def run(
        self,
        plan: WorkflowPlan,
        executor: StepExecutor,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> WorkflowResult:
        """Execute all runnable steps until terminal status or approval pause."""
        self.create_run(plan)
        return self.continue_run(plan.workflow_id, executor, context=context)

    def continue_run(
        self,
        workflow_id: str,
        executor: StepExecutor,
        *,
        context: Mapping[str, Any] | None = None,
        approved_step_ids: frozenset[str] | None = None,
    ) -> WorkflowResult:
        """Continue a paused or pending workflow.

        approved_step_ids marks approval-gated steps that may now execute.
        A per-run claim prevents concurrent callers from executing the same step.
        """
        state = self.get_run(workflow_id)
        if state is None:
            raise KeyError(f"unknown workflow: {workflow_id}")
        ctx = dict(context or {})
        approved = approved_step_ids or frozenset()

        with state._lock:
            if state.cancelled or state.status in _TERMINAL_WORKFLOW_STATUSES:
                return state.snapshot()
            if state._active:
                return state.snapshot()
            state._active = True
            if state.started_at is None:
                state.started_at = time.monotonic()
            state.status = WorkflowStatus.RUNNING

        try:
            while True:
                with state._lock:
                    if state.cancelled:
                        return state.snapshot()

                ready = self._ready_steps(state, approved)
                if not ready:
                    return self._finalize(state)

                for step in ready:
                    with state._lock:
                        if state.cancelled:
                            return state.snapshot()
                        if step.requires_approval and step.step_id not in approved:
                            state.step_results[step.step_id] = WorkflowStepResult(
                                step.step_id,
                                StepStatus.WAITING_APPROVAL,
                                error_code="approval_required",
                                error_message="Step requires explicit human approval",
                            )
                            state.status = WorkflowStatus.WAITING_APPROVAL
                            return state.snapshot()
                        state.step_results[step.step_id] = WorkflowStepResult(
                            step.step_id, StepStatus.RUNNING
                        )

                    try:
                        result = executor(step, context=ctx)
                    except Exception as exc:  # noqa: BLE001 — executor boundary
                        result = WorkflowStepResult(
                            step.step_id,
                            StepStatus.FAILED,
                            error_code="step_execution_failed",
                            error_message=str(exc)[:500] or "step execution failed",
                        )
                    if not isinstance(result, WorkflowStepResult):
                        result = WorkflowStepResult(
                            step.step_id,
                            StepStatus.FAILED,
                            error_code="invalid_step_result",
                            error_message="Executor returned an invalid step result",
                        )
                    if result.step_id != step.step_id:
                        result = WorkflowStepResult(
                            step.step_id,
                            StepStatus.FAILED,
                            error_code="invalid_step_result",
                            error_message="Executor returned a mismatched step_id",
                        )

                    with state._lock:
                        if state.cancelled:
                            return state.snapshot()
                        state.step_results[step.step_id] = result
                        if result.status in {
                            StepStatus.FAILED,
                            StepStatus.DENIED,
                            StepStatus.TIMED_OUT,
                        }:
                            state.status = (
                                WorkflowStatus.DENIED
                                if result.status == StepStatus.DENIED
                                else WorkflowStatus.FAILED
                                if result.status == StepStatus.FAILED
                                else WorkflowStatus.TIMED_OUT
                            )
                            state.error_code = result.error_code
                            state.error_message = result.error_message
                            state.finished_at = time.monotonic()
                            for remaining in state.plan.steps:
                                if remaining.step_id not in state.step_results:
                                    state.step_results[remaining.step_id] = WorkflowStepResult(
                                        remaining.step_id,
                                        StepStatus.CANCELLED,
                                        error_code="upstream_failed",
                                        error_message="Upstream step failed",
                                    )
                            return state.snapshot()
        except Exception as exc:  # noqa: BLE001 — engine boundary
            with state._lock:
                if state.cancelled:
                    return state.snapshot()
                error_message = str(exc)[:500] or "workflow execution failed"
                for step_id, existing in state.step_results.items():
                    if existing.status == StepStatus.RUNNING:
                        state.step_results[step_id] = WorkflowStepResult(
                            step_id,
                            StepStatus.FAILED,
                            error_code="workflow_engine_error",
                            error_message=error_message,
                        )
                state.status = WorkflowStatus.FAILED
                state.error_code = "workflow_engine_error"
                state.error_message = error_message
                state.finished_at = time.monotonic()
                return state.snapshot()
        except BaseException:
            with state._lock:
                if not state.cancelled and state.status not in _TERMINAL_WORKFLOW_STATUSES:
                    for step_id, existing in state.step_results.items():
                        if existing.status == StepStatus.RUNNING:
                            state.step_results[step_id] = WorkflowStepResult(
                                step_id,
                                StepStatus.FAILED,
                                error_code="workflow_interrupted",
                                error_message="Workflow execution was interrupted",
                            )
                    state.status = WorkflowStatus.FAILED
                    state.error_code = "workflow_interrupted"
                    state.error_message = "Workflow execution was interrupted"
                    state.finished_at = time.monotonic()
            raise
        finally:
            with state._lock:
                state._active = False

    def _ready_steps(
        self, state: WorkflowRunState, approved: frozenset[str]
    ) -> list[WorkflowStepSpec]:
        """Return steps whose dependencies and approval requirements are met."""
        with state._lock:
            done_ok = {
                step_id
                for step_id, result in state.step_results.items()
                if result.status in {StepStatus.SUCCEEDED, StepStatus.PARTIAL}
            }
            ready: list[WorkflowStepSpec] = []
            for step in state.plan.steps:
                existing = state.step_results.get(step.step_id)
                if existing is not None:
                    if existing.status != StepStatus.WAITING_APPROVAL:
                        continue
                    if step.step_id not in approved:
                        continue
                if all(dep in done_ok for dep in step.depends_on):
                    ready.append(step)
            return ready

    def _finalize(self, state: WorkflowRunState) -> WorkflowResult:
        """Derive and store the terminal status from completed step results."""
        with state._lock:
            if state.status in _TERMINAL_WORKFLOW_STATUSES:
                return state.snapshot()
            if state.status == WorkflowStatus.WAITING_APPROVAL:
                return state.snapshot()
            if state.cancelled:
                state.status = WorkflowStatus.CANCELLED
            else:
                statuses = [r.status for r in state.step_results.values()]
                if any(s == StepStatus.WAITING_APPROVAL for s in statuses):
                    state.status = WorkflowStatus.WAITING_APPROVAL
                elif len(state.step_results) < len(state.plan.steps):
                    state.status = WorkflowStatus.FAILED
                    state.error_code = "incomplete"
                    state.error_message = "Workflow ended with unreachable steps"
                elif all(s == StepStatus.SUCCEEDED for s in statuses):
                    state.status = WorkflowStatus.SUCCEEDED
                elif any(s == StepStatus.PARTIAL for s in statuses) and all(
                    s in {StepStatus.SUCCEEDED, StepStatus.PARTIAL} for s in statuses
                ):
                    state.status = WorkflowStatus.PARTIAL
                else:
                    state.status = WorkflowStatus.FAILED
            state.finished_at = time.monotonic()
            return state.snapshot()

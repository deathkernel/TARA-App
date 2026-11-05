"""Tests for the in-process workflow execution engine."""
from __future__ import annotations

import unittest

from tara_app.workflow_contracts import (
    StepStatus,
    WorkflowPlan,
    WorkflowStatus,
    WorkflowStepResult,
    WorkflowStepSpec,
)
from tara_app.workflow_engine import WorkflowEngine


def _ok(step, *, context):
    return WorkflowStepResult(step.step_id, StepStatus.SUCCEEDED, data={"op": step.operation_id})


def _fail(step, *, context):
    return WorkflowStepResult(
        step.step_id, StepStatus.FAILED, error_code="boom", error_message="failed"
    )


class WorkflowEngineTests(unittest.TestCase):
    def test_sequential_success(self) -> None:
        plan = WorkflowPlan(
            workflow_id="wf-1",
            request_id="req-1",
            steps=(
                WorkflowStepSpec("a", "op.a"),
                WorkflowStepSpec("b", "op.b", depends_on=("a",)),
            ),
        )
        engine = WorkflowEngine()
        result = engine.run(plan, _ok)
        self.assertEqual(result.status, WorkflowStatus.SUCCEEDED)
        self.assertEqual([s.step_id for s in result.steps], ["a", "b"])
        self.assertTrue(all(s.status == StepStatus.SUCCEEDED for s in result.steps))

    def test_parallel_ready_steps_both_succeed(self) -> None:
        plan = WorkflowPlan(
            workflow_id="wf-2",
            request_id="req-2",
            steps=(
                WorkflowStepSpec("a", "op.a"),
                WorkflowStepSpec("b", "op.b"),
                WorkflowStepSpec("c", "op.c", depends_on=("a", "b")),
            ),
        )
        engine = WorkflowEngine()
        result = engine.run(plan, _ok)
        self.assertEqual(result.status, WorkflowStatus.SUCCEEDED)
        self.assertEqual(len(result.steps), 3)

    def test_hard_failure_stops_workflow(self) -> None:
        def executor(step, *, context):
            if step.step_id == "a":
                return _fail(step, context=context)
            return _ok(step, context=context)

        plan = WorkflowPlan(
            workflow_id="wf-3",
            request_id="req-3",
            steps=(
                WorkflowStepSpec("a", "op.a"),
                WorkflowStepSpec("b", "op.b", depends_on=("a",)),
            ),
        )
        engine = WorkflowEngine()
        result = engine.run(plan, executor)
        self.assertEqual(result.status, WorkflowStatus.FAILED)
        self.assertEqual(result.steps[0].status, StepStatus.FAILED)
        self.assertEqual(result.steps[1].status, StepStatus.CANCELLED)

    def test_approval_pause_and_continue(self) -> None:
        plan = WorkflowPlan(
            workflow_id="wf-4",
            request_id="req-4",
            steps=(
                WorkflowStepSpec("read", "op.read", read_only=True),
                WorkflowStepSpec(
                    "write",
                    "op.write",
                    depends_on=("read",),
                    requires_approval=True,
                    read_only=False,
                ),
            ),
        )
        engine = WorkflowEngine()
        paused = engine.run(plan, _ok)
        self.assertEqual(paused.status, WorkflowStatus.WAITING_APPROVAL)
        write = next(s for s in paused.steps if s.step_id == "write")
        self.assertEqual(write.status, StepStatus.WAITING_APPROVAL)

        continued = engine.continue_run("wf-4", _ok, approved_step_ids=frozenset({"write"}))
        self.assertEqual(continued.status, WorkflowStatus.SUCCEEDED)

    def test_cancel_marks_remaining_cancelled(self) -> None:
        plan = WorkflowPlan(
            workflow_id="wf-5",
            request_id="req-5",
            steps=(
                WorkflowStepSpec(
                    "write",
                    "op.write",
                    requires_approval=True,
                    read_only=False,
                ),
            ),
        )
        engine = WorkflowEngine()
        engine.run(plan, _ok)
        cancelled = engine.cancel("wf-5")
        self.assertEqual(cancelled.status, WorkflowStatus.CANCELLED)
        self.assertEqual(cancelled.steps[0].status, StepStatus.CANCELLED)

    def test_duplicate_workflow_id_rejected(self) -> None:
        plan = WorkflowPlan(
            workflow_id="wf-dup",
            request_id="req-d",
            steps=(WorkflowStepSpec("a", "op.a"),),
        )
        engine = WorkflowEngine()
        engine.create_run(plan)
        with self.assertRaises(ValueError):
            engine.create_run(plan)


if __name__ == "__main__":
    unittest.main()

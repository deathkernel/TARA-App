"""Tests for the in-process workflow execution engine."""
from __future__ import annotations

import threading
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
    """Build a successful result for a workflow step."""
    return WorkflowStepResult(step.step_id, StepStatus.SUCCEEDED, data={"op": step.operation_id})


def _fail(step, *, context):
    """Build a failed result for a workflow step."""
    return WorkflowStepResult(
        step.step_id, StepStatus.FAILED, error_code="boom", error_message="failed"
    )


class WorkflowEngineTests(unittest.TestCase):
    def test_sequential_success(self) -> None:
        """Verify test sequential success behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-1", request_id="req-1",
            steps=(WorkflowStepSpec("a", "op.a"), WorkflowStepSpec("b", "op.b", depends_on=("a",))),
        )
        result = WorkflowEngine().run(plan, _ok)
        self.assertEqual(result.status, WorkflowStatus.SUCCEEDED)
        self.assertEqual([s.step_id for s in result.steps], ["a", "b"])
        self.assertTrue(all(s.status == StepStatus.SUCCEEDED for s in result.steps))

    def test_parallel_ready_steps_both_succeed(self) -> None:
        """Verify test parallel ready steps both succeed behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-2", request_id="req-2",
            steps=(
                WorkflowStepSpec("a", "op.a"),
                WorkflowStepSpec("b", "op.b"),
                WorkflowStepSpec("c", "op.c", depends_on=("a", "b")),
            ),
        )
        result = WorkflowEngine().run(plan, _ok)
        self.assertEqual(result.status, WorkflowStatus.SUCCEEDED)
        self.assertEqual(len(result.steps), 3)

    def test_hard_failure_stops_workflow(self) -> None:
        """Verify test hard failure stops workflow behavior."""
        def executor(step, *, context):
            """Fail the first step and succeed any later step."""
            return _fail(step, context=context) if step.step_id == "a" else _ok(step, context=context)

        plan = WorkflowPlan(
            workflow_id="wf-3", request_id="req-3",
            steps=(WorkflowStepSpec("a", "op.a"), WorkflowStepSpec("b", "op.b", depends_on=("a",))),
        )
        result = WorkflowEngine().run(plan, executor)
        self.assertEqual(result.status, WorkflowStatus.FAILED)
        self.assertEqual(result.steps[0].status, StepStatus.FAILED)
        self.assertEqual(result.steps[1].status, StepStatus.CANCELLED)

    def test_approval_pause_and_continue(self) -> None:
        """Verify test approval pause and continue behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-4", request_id="req-4",
            steps=(
                WorkflowStepSpec("read", "op.read", read_only=True),
                WorkflowStepSpec(
                    "write", "op.write", depends_on=("read",),
                    requires_approval=True, read_only=False,
                ),
            ),
        )
        engine = WorkflowEngine()
        paused = engine.run(plan, _ok)
        self.assertEqual(paused.status, WorkflowStatus.WAITING_APPROVAL)
        self.assertEqual(next(s for s in paused.steps if s.step_id == "write").status, StepStatus.WAITING_APPROVAL)
        continued = engine.continue_run("wf-4", _ok, approved_step_ids=frozenset({"write"}))
        self.assertEqual(continued.status, WorkflowStatus.SUCCEEDED)

    def test_cancel_marks_remaining_cancelled(self) -> None:
        """Verify test cancel marks remaining cancelled behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-5", request_id="req-5",
            steps=(WorkflowStepSpec("write", "op.write", requires_approval=True, read_only=False),),
        )
        engine = WorkflowEngine()
        engine.run(plan, _ok)
        cancelled = engine.cancel("wf-5")
        self.assertEqual(cancelled.status, WorkflowStatus.CANCELLED)
        self.assertEqual(cancelled.steps[0].status, StepStatus.CANCELLED)

    def test_duplicate_workflow_id_rejected(self) -> None:
        """Verify test duplicate workflow id rejected behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-dup", request_id="req-d",
            steps=(WorkflowStepSpec("a", "op.a"),),
        )
        engine = WorkflowEngine()
        engine.create_run(plan)
        with self.assertRaises(ValueError):
            engine.create_run(plan)

    def test_concurrent_continue_does_not_execute_step_twice(self) -> None:
        """Verify test concurrent continue does not execute step twice behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-concurrent", request_id="req-concurrent",
            steps=(WorkflowStepSpec("a", "op.a"),),
        )
        engine = WorkflowEngine()
        engine.create_run(plan)
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def executor(step, *, context):
            """Block the first step so a concurrent continuation can be tested."""
            calls.append(step.step_id)
            entered.set()
            self.assertTrue(release.wait(2))
            return _ok(step, context=context)

        first = threading.Thread(target=lambda: engine.continue_run("wf-concurrent", executor))
        first.start()
        self.assertTrue(entered.wait(2))
        second = engine.continue_run("wf-concurrent", executor)
        self.assertEqual(second.status, WorkflowStatus.RUNNING)
        release.set()
        first.join(2)
        self.assertFalse(first.is_alive())
        self.assertEqual(calls, ["a"])
        self.assertEqual(engine.get_run("wf-concurrent").snapshot().status, WorkflowStatus.SUCCEEDED)

    def test_cancel_during_executor_preserves_cancellation(self) -> None:
        """Verify test cancel during executor preserves cancellation behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-cancel-race", request_id="req-cancel-race",
            steps=(WorkflowStepSpec("a", "op.a"), WorkflowStepSpec("b", "op.b")),
        )
        engine = WorkflowEngine()
        engine.create_run(plan)
        entered = threading.Event()
        release = threading.Event()

        def executor(step, *, context):
            """Block the active step until cancellation has been recorded."""
            entered.set()
            self.assertTrue(release.wait(2))
            return _ok(step, context=context)

        thread = threading.Thread(target=lambda: engine.continue_run("wf-cancel-race", executor))
        thread.start()
        self.assertTrue(entered.wait(2))
        cancelled = engine.cancel("wf-cancel-race")
        self.assertEqual(cancelled.status, WorkflowStatus.CANCELLED)
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        final = engine.get_run("wf-cancel-race").snapshot()
        self.assertEqual(final.status, WorkflowStatus.CANCELLED)
        self.assertTrue(all(step.status == StepStatus.CANCELLED for step in final.steps))

    def test_partial_workflow_is_terminal(self) -> None:
        """Verify test partial workflow is terminal behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-partial", request_id="req-partial",
            steps=(WorkflowStepSpec("a", "op.a"),),
        )
        engine = WorkflowEngine()
        engine.create_run(plan)

        def partial(step, *, context):
            """Return a partial result to exercise terminal-state handling."""
            return WorkflowStepResult(step.step_id, StepStatus.PARTIAL)

        result = engine.continue_run("wf-partial", partial)
        self.assertEqual(result.status, WorkflowStatus.PARTIAL)
        self.assertEqual(engine.cancel("wf-partial").status, WorkflowStatus.PARTIAL)
        self.assertEqual(engine.continue_run("wf-partial", _ok).status, WorkflowStatus.PARTIAL)

    def test_executor_interrupt_does_not_strand_running_state(self) -> None:
        """Verify test executor interrupt does not strand running state behavior."""
        plan = WorkflowPlan(
            workflow_id="wf-interrupted", request_id="req-interrupted",
            steps=(WorkflowStepSpec("a", "op.a"),),
        )
        engine = WorkflowEngine()

        def interrupt(step, *, context):
            """Raise an interruption while a step is marked as running."""
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            engine.run(plan, interrupt)
        state = engine.get_run("wf-interrupted")
        self.assertEqual(state.snapshot().status, WorkflowStatus.FAILED)
        self.assertEqual(state.error_code, "workflow_interrupted")
        self.assertEqual(state.snapshot().steps[0].status, StepStatus.FAILED)
        self.assertFalse(any(step.status == StepStatus.RUNNING for step in state.snapshot().steps))
        self.assertEqual(state.snapshot().steps[0].error_code, "workflow_interrupted")


if __name__ == "__main__":
    unittest.main()

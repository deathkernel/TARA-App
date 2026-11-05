"""Tests for bounded tool-loop plan validation and execution."""
from __future__ import annotations

import unittest

from tara_app.tool_loop import (
    ToolLoopError,
    ToolPlan,
    ToolStep,
    ToolStepResult,
    ToolStepStatus,
    plan_from_mapping,
    run_tool_plan,
)


def _ok(step, *, approval_token):
    return ToolStepResult(step.step_id, ToolStepStatus.SUCCEEDED, output=f"ran:{step.tool_name}")


class ToolLoopTests(unittest.TestCase):
    def test_plan_rejects_duplicate_steps(self) -> None:
        with self.assertRaises(ToolLoopError):
            ToolPlan(
                "p1",
                (
                    ToolStep("a", "t.a"),
                    ToolStep("a", "t.b"),
                ),
            )

    def test_approval_gated_cannot_be_read_only(self) -> None:
        with self.assertRaises(ToolLoopError):
            ToolStep("a", "t.write", requires_approval=True, read_only=True)

    def test_sequential_success(self) -> None:
        plan = ToolPlan(
            "p2",
            (ToolStep("a", "t.a"), ToolStep("b", "t.b")),
        )
        result = run_tool_plan(plan, _ok)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual([s.status for s in result.steps], [ToolStepStatus.SUCCEEDED, ToolStepStatus.SUCCEEDED])

    def test_waits_for_approval(self) -> None:
        plan = ToolPlan(
            "p3",
            (
                ToolStep("read", "t.read", read_only=True),
                ToolStep("write", "t.write", read_only=False, requires_approval=True),
            ),
        )
        paused = run_tool_plan(plan, _ok)
        self.assertEqual(paused.status, "waiting_approval")
        self.assertEqual(paused.steps[1].status, ToolStepStatus.WAITING_APPROVAL)

        continued = run_tool_plan(plan, _ok, approval_tokens={"write": "tok-1"})
        self.assertEqual(continued.status, "succeeded")

    def test_failure_stops_and_skips(self) -> None:
        def executor(step, *, approval_token):
            if step.step_id == "a":
                return ToolStepResult("a", ToolStepStatus.FAILED, error_code="x", error_message="nope")
            return _ok(step, approval_token=approval_token)

        plan = ToolPlan("p4", (ToolStep("a", "t.a"), ToolStep("b", "t.b")))
        result = run_tool_plan(plan, executor)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.steps[1].status, ToolStepStatus.SKIPPED)

    def test_plan_from_mapping(self) -> None:
        plan = plan_from_mapping(
            {
                "plan_id": "p5",
                "steps": [
                    {"step_id": "a", "tool_name": "time.get_current_time", "arguments": {}},
                ],
            }
        )
        self.assertEqual(plan.plan_id, "p5")
        self.assertEqual(plan.steps[0].tool_name, "time.get_current_time")


if __name__ == "__main__":
    unittest.main()

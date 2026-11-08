"""Tests for bounded tool-loop plan validation and execution."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

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


class ToolLoopBridgeTests(unittest.TestCase):
    def test_bridge_validate(self) -> None:
        from tara_app.tool_loop_bridge import validate_tool_plan

        plan = validate_tool_plan(
            {
                "plan_id": "b1",
                "steps": [{"step_id": "a", "tool_name": "time.get_current_time", "arguments": {}}],
            }
        )
        self.assertEqual(plan.plan_id, "b1")

    def test_bridge_never_mints_approval_for_read_only_steps(self) -> None:
        from tara_app.tool_loop_bridge import run_validated_tool_plan

        class Coordinator:
            mcp_gateway = SimpleNamespace(_config=SimpleNamespace(enabled_servers=[]))

            def __init__(self):
                self.issued = []
                self.calls = []

            def issue_mcp_approval_token(self, *args, **kwargs):
                self.issued.append((args, kwargs))
                return "implicit-token"

            def call_mcp_tool(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return "unexpected"

        coordinator = Coordinator()
        plan = ToolPlan("b2", (ToolStep("read", "time.get_current_time", read_only=True),))

        result = run_validated_tool_plan(coordinator, plan)

        self.assertEqual(result.status, "waiting_approval")
        self.assertEqual(result.steps[0].status, ToolStepStatus.WAITING_APPROVAL)
        self.assertEqual(coordinator.issued, [])
        self.assertEqual(coordinator.calls, [])


    def test_bridge_logs_only_sanitized_failure_details(self) -> None:
        from tara_app.tool_loop_bridge import run_validated_tool_plan

        class Coordinator:
            mcp_gateway = SimpleNamespace(_config=SimpleNamespace(enabled_servers=[]))

            def call_mcp_tool(self, *args, **kwargs):
                raise RuntimeError("secret-token-and-arguments")

        plan = ToolPlan(
            "b4",
            (ToolStep("read", "time.get_current_time", read_only=True),),
        )
        with self.assertLogs("tara_app.tool_loop_bridge", level="WARNING") as captured:
            result = run_validated_tool_plan(
                Coordinator(),
                plan,
                approval_tokens={"read": "explicit-token"},
            )

        self.assertEqual(result.steps[0].status, ToolStepStatus.FAILED)
        self.assertEqual(result.steps[0].error_message, "MCP tool call failed")
        self.assertIn("RuntimeError", captured.output[0])
        self.assertNotIn("secret-token-and-arguments", captured.output[0])
        self.assertNotIn("explicit-token", captured.output[0])

    def test_bridge_uses_only_the_explicitly_supplied_token(self) -> None:
        from tara_app.tool_loop_bridge import run_validated_tool_plan

        class Coordinator:
            mcp_gateway = SimpleNamespace(_config=SimpleNamespace(enabled_servers=[]))

            def __init__(self):
                self.calls = []

            def call_mcp_tool(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return "approved-result"

        coordinator = Coordinator()
        plan = ToolPlan("b3", (ToolStep("read", "time.get_current_time", read_only=True),))

        result = run_validated_tool_plan(
            coordinator,
            plan,
            session_id="session-1",
            approval_tokens={"read": "explicit-token"},
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(coordinator.calls[0][1]["approval_token"], "explicit-token")
        self.assertEqual(coordinator.calls[0][1]["session_id"], "session-1")


if __name__ == "__main__":
    unittest.main()

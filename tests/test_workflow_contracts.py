from __future__ import annotations

import unittest

from tara_app.workflow_contracts import (
    StepStatus,
    WorkflowPlan,
    WorkflowRequest,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStepResult,
    WorkflowStepSpec,
)


class WorkflowContractTests(unittest.TestCase):
    def test_request_requires_bounded_identifiers_and_mapping_input(self):
        request = WorkflowRequest("request-1", "session-1", {"question": "hello"})

        self.assertEqual(request.schema_version, "1.0")
        self.assertEqual(request.input["question"], "hello")
        with self.assertRaises(ValueError):
            WorkflowRequest("", "session-1", {})
        with self.assertRaises(ValueError):
            WorkflowRequest("request-1", "session-1", [], schema_version="2.0")

    def test_step_spec_validates_timeout_dependencies_and_approval_semantics(self):
        step = WorkflowStepSpec(
            step_id="review",
            operation_id="repository.review",
            depends_on=("load",),
            timeout_seconds=45,
            read_only=False,
            requires_approval=True,
        )

        self.assertEqual(step.depends_on, ("load",))
        with self.assertRaises(ValueError):
            WorkflowStepSpec("step", "repo.scan", timeout_seconds=0)
        with self.assertRaises(ValueError):
            WorkflowStepSpec("step", "repo.scan", depends_on=("step",))
        with self.assertRaises(ValueError):
            WorkflowStepSpec("step", "repo.scan", read_only=True, requires_approval=True)

    def test_workflow_plan_rejects_missing_dependencies_and_cycles(self):
        load = WorkflowStepSpec("load", "repo.load")
        review = WorkflowStepSpec("review", "repo.review", depends_on=("load",))
        plan = WorkflowPlan("workflow-1", "request-1", (review, load))

        self.assertEqual(len(plan.steps), 2)
        with self.assertRaises(ValueError):
            WorkflowPlan("workflow-1", "request-1", (review,))
        cycle_a = WorkflowStepSpec("a", "repo.a", depends_on=("b",))
        cycle_b = WorkflowStepSpec("b", "repo.b", depends_on=("a",))
        with self.assertRaises(ValueError):
            WorkflowPlan("workflow-1", "request-1", (cycle_a, cycle_b))

    def test_workflow_data_must_be_json_compatible_and_bounded(self):
        with self.assertRaises(ValueError):
            WorkflowRequest("request-1", "session-1", {"callback": object()})
        with self.assertRaises(ValueError):
            WorkflowRequest("request-1", "session-1", {"payload": "x" * 1_000_001})

    def test_result_contract_rejects_duplicate_steps_and_invalid_status(self):
        step = WorkflowStepResult("review", StepStatus.SUCCEEDED, {"findings": []})
        result = WorkflowResult("request-1", "workflow-1", WorkflowStatus.SUCCEEDED, (step,))

        self.assertEqual(result.steps[0].status, StepStatus.SUCCEEDED)
        with self.assertRaises(ValueError):
            WorkflowResult("request-1", "workflow-1", WorkflowStatus.SUCCEEDED, (step, step))
        with self.assertRaises(ValueError):
            WorkflowStepResult("review", "succeeded")


if __name__ == "__main__":
    unittest.main()

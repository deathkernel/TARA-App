"""Central capability validation and fail-closed module dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import uuid4

from tara_app.adapters import RouterClient
from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.registry import CapabilityRegistry


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    status: str
    route: RouteDecision | None
    result: ModuleResult
    request_id: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "request_id": self.request_id,
            "status": self.status,
            "route": None if self.route is None else {
                "schema_version": self.route.schema_version,
                "request_id": self.route.request_id,
                "status": self.route.status,
                "module": self.route.module,
                "action": self.route.action,
                "reason_code": self.route.reason_code,
                "reason": self.route.reason,
                "intended_module": self.route.intended_module,
                "intended_action": self.route.intended_action,
                "requires_approval": self.route.requires_approval,
                "policy_tags": list(self.route.policy_tags),
            },
            "result": self.result.to_payload(),
        }


class Orchestrator:
    """Uses Router proposals and registered module adapters; it never auto-approves."""

    def __init__(self, registry: CapabilityRegistry, router: RouterClient) -> None:
        self.registry = registry
        self.router = router

    def handle_question(
        self,
        question: str,
        *,
        session_id: str = "default",
        attachments: Sequence[Mapping[str, str]] = (),
        workspace_root: str | None = None,
        request_id: str | None = None,
    ) -> DispatchOutcome:
        operation_id = request_id or str(uuid4())
        if not isinstance(operation_id, str) or not operation_id.strip() or len(operation_id) > 128:
            return self._outcome("unknown", "invalid_request", None, "invalid_request", "request_id is invalid")
        if not isinstance(question, str) or not question.strip() or len(question) > 20_000:
            return self._outcome(operation_id, "invalid_request", None, "invalid_request", "question is empty or too long")
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            return self._outcome(operation_id, "invalid_request", None, "invalid_request", "session_id is invalid")
        try:
            safe_attachments = self._validate_attachments(attachments)
        except ValueError:
            return self._outcome(operation_id, "invalid_request", None, "invalid_request", "attachment metadata is invalid")

        route_input = {
            "schema_version": "1.0",
            "request_id": operation_id,
            "question": question,
            "available_capabilities": list(self.registry.capability_ids()),
            "attachments": safe_attachments,
        }
        try:
            decision = self.router.route(route_input)
        except Exception:
            return self._outcome(operation_id, "unavailable", None, "router_unavailable", "TARA-Router is unavailable")

        if not isinstance(decision, RouteDecision):
            return self._outcome(operation_id, "failed", None, "invalid_router_response", "Router returned an invalid decision")
        if decision.request_id != operation_id:
            return self._outcome(operation_id, "failed", decision, "invalid_router_response", "Router request ID did not match")
        if decision.status != "routed":
            return self._outcome(operation_id, decision.status, decision, decision.reason_code, decision.reason)
        if decision.module is None or decision.action is None:
            return self._outcome(operation_id, "failed", decision, "invalid_router_response", "Router did not select a capability")

        capability = self.registry.capability(decision.module, decision.action)
        adapter = self.registry.adapter(decision.module)
        if capability is None or adapter is None:
            return self._outcome(operation_id, "unavailable", decision, "capability_unavailable", "Selected capability is not registered")
        if (not capability.read_only or capability.requires_approval) and not decision.requires_approval:
            return self._outcome(operation_id, "permission_denied", decision, "approval_route_required", "Side-effecting capabilities must be assessed by TARA-Security first")
        if decision.requires_approval and decision.module != "security":
            return self._outcome(operation_id, "permission_denied", decision, "policy_route_invalid", "Approval-gated route bypassed TARA-Security")

        try:
            health = adapter.health()
        except Exception:
            return self._outcome(operation_id, "unavailable", decision, "adapter_health_failed", "Specialist health check failed")
        if not isinstance(health, AdapterHealth) or health.status != "healthy":
            return self._outcome(operation_id, "unavailable", decision, "adapter_unavailable", "Selected specialist is unavailable")

        inputs: dict[str, Any] = {"question": question, "attachments": safe_attachments}
        if decision.intended_module:
            inputs["intended_module"] = decision.intended_module
        if decision.intended_action:
            inputs["intended_action"] = decision.intended_action
        if decision.policy_tags:
            inputs["policy_tags"] = list(decision.policy_tags)
        module_request = ModuleRequest(
            request_id=operation_id,
            session_id=session_id,
            module=decision.module,
            action=decision.action,
            inputs=inputs,
            workspace_root=workspace_root,
        )
        try:
            result = adapter.execute(module_request)
        except Exception:
            return self._outcome(operation_id, "failed", decision, "adapter_execution_failed", "Specialist execution failed")
        if not isinstance(result, ModuleResult):
            return self._outcome(operation_id, "failed", decision, "invalid_adapter_response", "Specialist returned an invalid result")

        if decision.requires_approval:
            verdict = result.data.get("decision") if isinstance(result.data, Mapping) else None
            if result.status == "permission_denied" or verdict == "deny":
                return DispatchOutcome("permission_denied", decision, result, operation_id)
            if result.status != "success":
                return DispatchOutcome(result.status, decision, result, operation_id)
            pending = ModuleResult(
                status="approval_required",
                data={
                    "security_assessed": isinstance(verdict, str) and verdict in {"allow", "approval_required"},
                    "intended_module": decision.intended_module,
                    "intended_action": decision.intended_action,
                },
                error="human approval is required; the requested side effect was not executed",
            )
            return DispatchOutcome("approval_required", decision, pending, operation_id)

        return DispatchOutcome(result.status, decision, result, operation_id)

    @staticmethod
    def _validate_attachments(attachments: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        if not isinstance(attachments, Sequence) or isinstance(attachments, (str, bytes)) or len(attachments) > 20:
            raise ValueError("attachments are invalid")
        safe: list[dict[str, str]] = []
        for item in attachments:
            if not isinstance(item, Mapping) or set(item) - {"media_type", "name"}:
                raise ValueError("attachment metadata is invalid")
            media_type = item.get("media_type", "")
            name = item.get("name", "")
            if not isinstance(media_type, str) or not media_type or len(media_type) > 128:
                raise ValueError("attachment media_type is invalid")
            if not isinstance(name, str) or len(name) > 255:
                raise ValueError("attachment name is invalid")
            safe.append({"media_type": media_type, "name": name})
        return safe

    @staticmethod
    def _outcome(
        request_id: str,
        status: str,
        route: RouteDecision | None,
        reason_code: str,
        reason: str,
    ) -> DispatchOutcome:
        result = ModuleResult(status=status if status in ModuleResult._STATUSES else "failed", data={"reason_code": reason_code}, error=reason)
        return DispatchOutcome(status, route, result, request_id)

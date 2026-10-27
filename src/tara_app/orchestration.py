"""Versioned request/response contracts and policy-gated capability dispatch."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from tara_app.audit import AuditLogError, JsonlAuditLog
from tara_app.permissions import PermissionAction, PermissionPolicy


ORCHESTRATION_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class CapabilityRequest:
    capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid4()))
    approved: bool = False
    contract_version: int = ORCHESTRATION_CONTRACT_VERSION


@dataclass(frozen=True)
class CapabilityResponse:
    request_id: str
    status: str
    capability: str
    result: Any = None
    message: str = ""


class CapabilityUnavailable(RuntimeError):
    """Raised for missing, unsafe, or incompatible capability dispatch."""


class CapabilityOrchestrator:
    """Dispatch only registered capabilities allowed by an explicit policy."""

    def __init__(
        self,
        *,
        policy: PermissionPolicy,
        audit_log: JsonlAuditLog,
        handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
    ) -> None:
        self._policy = policy
        self._audit = audit_log
        self._handlers = dict(handlers or {})

    def register(self, capability: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        if not isinstance(capability, str) or not capability.strip():
            raise ValueError("capability must be a non-empty string")
        if not callable(handler):
            raise ValueError("handler must be callable")
        if capability in self._handlers:
            raise ValueError(f"capability {capability!r} is already registered")
        self._handlers[capability] = handler

    def dispatch(self, request: CapabilityRequest) -> CapabilityResponse:
        if request.contract_version != ORCHESTRATION_CONTRACT_VERSION:
            raise CapabilityUnavailable("unsupported orchestration contract version")
        if not isinstance(request.payload, dict):
            raise CapabilityUnavailable("request payload must be an object")

        decision = self._policy.evaluate(request.capability, approved=request.approved)
        audit_fields = {
            "request_id": request.request_id,
            "session_id": request.session_id,
            "capability": request.capability,
            "decision": decision.action.value,
            "reason": decision.reason,
        }
        try:
            self._audit.record("capability_policy_decision", audit_fields)
        except AuditLogError:
            # Fail closed: do not run a capability if its decision cannot be audited.
            return CapabilityResponse(request.request_id, "audit_unavailable", request.capability,
                                      message="Audit log unavailable; capability was not invoked")

        if decision.action is PermissionAction.DENY:
            return CapabilityResponse(request.request_id, "permission_denied", request.capability,
                                      message=decision.reason)
        if decision.action is PermissionAction.REQUIRE_APPROVAL:
            return CapabilityResponse(request.request_id, "approval_required", request.capability,
                                      message=decision.reason)
        handler = self._handlers.get(request.capability)
        if handler is None:
            self._safe_audit("capability_unavailable", audit_fields)
            return CapabilityResponse(request.request_id, "unavailable", request.capability,
                                      message="Capability has no registered handler")
        try:
            result = handler(dict(request.payload))
        except Exception:
            self._safe_audit("capability_failed", audit_fields)
            return CapabilityResponse(request.request_id, "failed", request.capability,
                                      message="Capability execution failed")
        self._safe_audit("capability_completed", audit_fields)
        return CapabilityResponse(request.request_id, "ok", request.capability, result=result)

    def _safe_audit(self, event_type: str, fields: dict[str, Any]) -> None:
        try:
            self._audit.record(event_type, fields)
        except AuditLogError:
            # The initial policy decision is already durable; completion audit is best effort.
            pass

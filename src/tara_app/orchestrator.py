"""Central capability validation and fail-closed module dispatch."""

from __future__ import annotations

import base64
import binascii
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
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
        self._conversation_history: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        self._history_lock = RLock()

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

        route_attachments = [{key: value for key, value in item.items() if key in {"media_type", "name"}} for item in safe_attachments]
        route_input = {
            "schema_version": "1.0",
            "request_id": operation_id,
            "question": question,
            "available_capabilities": list(self.registry.capability_ids()),
            "attachments": route_attachments,
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
        try:
            self._add_specialist_attachment_inputs(inputs, decision.module, decision.action, safe_attachments)
        except ValueError:
            return self._outcome(operation_id, "invalid_request", decision, "invalid_attachment_content", "attachment content is invalid for the selected specialist")
        if decision.module == "chat" and decision.action == "respond":
            with self._history_lock:
                inputs["history"] = [dict(turn) for turn in self._conversation_history.get(session_id, [])]
        if decision.intended_module:
            inputs["intended_module"] = decision.intended_module
        if decision.intended_action:
            inputs["intended_action"] = decision.intended_action
        if decision.module == "voice" and decision.action == "speak":
            inputs["text"] = question
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

        if decision.module == "chat" and decision.action == "respond" and result.status == "success":
            response_text = result.data.get("text") if isinstance(result.data, Mapping) else None
            if isinstance(response_text, str) and response_text.strip():
                with self._history_lock:
                    history = self._conversation_history.setdefault(session_id, [])
                    history.extend((
                        {"role": "user", "content": question.strip()},
                        {"role": "assistant", "content": response_text.strip()},
                    ))
                    del history[:-24]
                    self._conversation_history.move_to_end(session_id)
                    while len(self._conversation_history) > 512:
                        self._conversation_history.popitem(last=False)

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
        total_content_bytes = 0
        for item in attachments:
            if not isinstance(item, Mapping) or set(item) - {"media_type", "name", "content_base64"}:
                raise ValueError("attachment metadata is invalid")
            media_type = item.get("media_type", "")
            name = item.get("name", "")
            if not isinstance(media_type, str) or not media_type or len(media_type) > 128:
                raise ValueError("attachment media_type is invalid")
            if not isinstance(name, str) or len(name) > 255:
                raise ValueError("attachment name is invalid")
            normalized = {"media_type": media_type, "name": name}
            content = item.get("content_base64")
            if content is not None:
                if not isinstance(content, str) or not content or len(content) > 700_000:
                    raise ValueError("attachment content is invalid")
                try:
                    decoded = base64.b64decode(content, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise ValueError("attachment content is invalid") from exc
                if not decoded or len(decoded) > 512_000:
                    raise ValueError("attachment content is outside the size limit")
                total_content_bytes += len(decoded)
                if total_content_bytes > 512_000:
                    raise ValueError("combined attachment content exceeds the size limit")
                normalized["content_base64"] = base64.b64encode(decoded).decode("ascii")
            safe.append(normalized)
        return safe

    @staticmethod
    def _add_specialist_attachment_inputs(
        inputs: dict[str, Any],
        module: str,
        action: str,
        attachments: Sequence[Mapping[str, str]],
    ) -> None:
        if module == "vision" and action == "analyze":
            images = [item["content_base64"] for item in attachments if item.get("media_type", "").casefold().startswith("image/") and item.get("content_base64")]
            if images:
                inputs["images"] = images[:4]
        elif module == "voice" and action == "transcribe":
            audio = next((item for item in attachments if item.get("media_type", "").casefold().startswith("audio/") and item.get("content_base64")), None)
            if audio is not None:
                inputs["audio_base64"] = audio["content_base64"]
                inputs["media_type"] = audio["media_type"]
        elif module == "data" and action == "analyze":
            csv_file = next((item for item in attachments if item.get("media_type", "").casefold() == "text/csv" or item.get("name", "").casefold().endswith(".csv")), None)
            if csv_file is not None and csv_file.get("content_base64"):
                try:
                    text = base64.b64decode(csv_file["content_base64"], validate=True).decode("utf-8-sig")
                except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
                    raise ValueError("CSV attachment is invalid") from exc
                inputs["csv_text"] = text

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


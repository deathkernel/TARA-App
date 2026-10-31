"""Central capability validation and fail-closed module dispatch."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from uuid import uuid4

from tara_app.adapters import RouterClient
from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.ollama_models import OllamaModelCatalog
from tara_app.registry import CapabilityRegistry
from tara_app.sessions import SessionError, SessionStore

_AUDIO_MEDIA_TYPES = frozenset({
    "audio/mpeg", "audio/wav", "audio/mp4", "audio/webm", "audio/ogg", "audio/flac", "audio/aac",
})
_AUDIO_SUFFIX_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
}


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


@dataclass(frozen=True, slots=True)
class PendingApproval:
    approval_id: str
    request_id: str
    session_id: str
    question: str
    target_module: str
    target_action: str
    target_inputs: Mapping[str, Any]
    workspace_root: str | None
    route: RouteDecision
    expires_at: float
    description: str


class Orchestrator:
    """Uses Router proposals and registered module adapters; it never auto-approves."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        router: RouterClient,
        *,
        model_catalog: OllamaModelCatalog | None = None,
        session_store: SessionStore | None = None,
    ) -> None:
        self.registry = registry
        self.router = router
        self.model_catalog = model_catalog
        self.session_store = session_store
        self._history_limit = min(24, session_store.max_messages_per_session) if session_store is not None else 24
        self._conversation_history: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        if self.session_store is not None:
            for item in self.session_store.list_sessions():
                session_id = item["session_id"]
                messages = self.session_store.history(session_id, limit=self._history_limit)
                self._conversation_history[session_id] = [
                    {"role": message.role, "content": message.content}
                    for message in messages if message.role in {"user", "assistant"}
                ]
        self._history_lock = RLock()
        self._pending_approvals: OrderedDict[str, PendingApproval] = OrderedDict()
        self._approval_lock = RLock()
        self._active_question_lock = RLock()
        self._active_questions: dict[tuple[str, str], str] = {}
        self._active_execution_lock = RLock()
        self._active_executions: dict[str, tuple[str, Any]] = {}
        self._shutting_down = False

    def replace_conversation_history(self, session_id: str, history: Sequence[Mapping[str, str]]) -> None:
        """Replace one session's bounded conversation context from the local UI."""
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            raise ValueError("session_id is invalid")
        if not isinstance(history, Sequence) or isinstance(history, (str, bytes)) or len(history) > 24:
            raise ValueError("history is invalid")
        safe_history: list[dict[str, str]] = []
        total_chars = 0
        for turn in history:
            if not isinstance(turn, Mapping) or set(turn) != {"role", "content"}:
                raise ValueError("history turn is invalid")
            role = turn.get("role")
            content = turn.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip() or len(content) > 20_000:
                raise ValueError("history turn is invalid")
            total_chars += len(content)
            if total_chars > 120_000:
                raise ValueError("history is too large")
            safe_history.append({"role": role, "content": content})
        del safe_history[:-self._history_limit]
        with self._history_lock:
            if self.session_store is not None:
                try:
                    if safe_history:
                        self.session_store.replace_history(session_id, safe_history)
                    else:
                        self.session_store.close(session_id)
                except SessionError as exc:
                    raise ValueError("persistent conversation history could not be updated") from exc
            if safe_history:
                self._conversation_history[session_id] = safe_history
                self._conversation_history.move_to_end(session_id)
            else:
                self._conversation_history.pop(session_id, None)
            while len(self._conversation_history) > 512:
                self._conversation_history.popitem(last=False)

    def handle_question(
        self,
        question: str,
        *,
        session_id: str = "default",
        attachments: Sequence[Mapping[str, str]] = (),
        workspace_root: str | None = None,
        request_id: str | None = None,
    ) -> DispatchOutcome:
        """Reject an identical in-flight question in the same session.

        This protects against duplicate submissions from multiple tabs or
        clients. It does not suppress a later retry after the first request
        has completed.
        """
        operation_id = request_id or str(uuid4())
        with self._active_execution_lock:
            if self._shutting_down:
                return self._outcome(operation_id, "unavailable", None, "app_shutting_down", "TARA-App is shutting down and cannot accept new requests")
        if isinstance(question, str) and isinstance(session_id, str):
            fingerprint = hashlib.sha256(question.strip().casefold().encode("utf-8", errors="replace")).hexdigest()
            key = (session_id, fingerprint)
            with self._active_question_lock:
                if key in self._active_questions:
                    return self._outcome(
                        operation_id,
                        "unavailable",
                        None,
                        "duplicate_request",
                        "An identical request is already running in this session.",
                    )
                self._active_questions[key] = operation_id
            try:
                return self._handle_question(
                    question,
                    session_id=session_id,
                    attachments=attachments,
                    workspace_root=workspace_root,
                    request_id=operation_id,
                )
            finally:
                with self._active_question_lock:
                    if self._active_questions.get(key) == operation_id:
                        self._active_questions.pop(key, None)
        return self._handle_question(
            question,
            session_id=session_id,
            attachments=attachments,
            workspace_root=workspace_root,
            request_id=operation_id,
        )

    def _handle_question(
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
            # Showing a local catalog is safe even when the optional remote
            # model adapter is disabled. Cloud generation still requires an
            # explicitly enabled adapter and explicit model selection.
            if decision.intended_module == "models" and decision.intended_action == "catalog":
                local_models = []
                if self.model_catalog is not None:
                    try:
                        status = self.model_catalog.status()
                        local_models = [item.get("id", "unknown") for item in status.get("models", []) if isinstance(item, Mapping)]
                    except Exception:
                        local_models = []
                local_section = "\\n".join(f"- {model}" for model in local_models) or "- No local Ollama models detected."
                catalog_text = (
                    "# Free Model Hub\\n\\n"
                    "## Gemini free-tier candidates (cloud; explicit selection required)\\n"
                    "- gemini-3.5-flash-lite\\n- gemini-2.5-flash-lite\\n- gemini-3.1-flash-lite\\n\\n"
                    "Actual free quota and model availability depend on your Google AI project. "
                    "TARA does not send a prompt to Google merely to display this catalog.\\n\\n"
                    "## Open-weight models for local Ollama\\n"
                    "- gpt-oss:20b — verify memory requirements before installing.\\n"
                    "- gpt-oss:120b — a large model; verify hardware requirements first.\\n\\n"
                    "## Models installed on this device\\n" + local_section + "\\n\\n"
                    "Cloud generation stays disabled unless the model adapter is explicitly enabled."
                )
                catalog_route = RouteDecision(
                    operation_id, "routed", "models", "catalog", "local_model_catalog",
                    "Displayed the local, non-network model catalog.",
                )
                return DispatchOutcome(
                    "success", catalog_route,
                    ModuleResult("success", {"text": catalog_text, "provider": "TARA local catalog", "remote_data_transfer": False}),
                    operation_id,
                )
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

        if self.model_catalog is not None and decision.module in self.model_catalog.profiles:
            try:
                self.model_catalog.ensure_model_installed(decision.module)
            except RuntimeError:
                return self._outcome(
                    operation_id,
                    "unavailable",
                    decision,
                    "local_model_unavailable",
                    "TARA-App could not prepare the selected local model. Check the Models panel for download status.",
                )

        try:
            health = adapter.health()
        except Exception:
            return self._outcome(operation_id, "unavailable", decision, "adapter_health_failed", "Specialist health check failed")
        if not isinstance(health, AdapterHealth) or health.status != "healthy":
            return self._outcome(operation_id, "unavailable", decision, "adapter_unavailable", "Selected specialist is unavailable")

        try:
            module_attachments = self._specialist_attachments(
                decision.module, decision.action, safe_attachments
            )
        except (ValueError, binascii.Error):
            return self._outcome(operation_id, "invalid_request", decision, "invalid_attachment_content", "attachments exceed the selected specialist's supported limits")
        inputs: dict[str, Any] = {"question": question, "attachments": module_attachments}
        try:
            self._add_specialist_attachment_inputs(
                inputs, decision.module, decision.action, module_attachments
            )
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
        if decision.module == "memory" and decision.action == "search":
            query = re.sub(
                r"^\s*(?:what do you remember(?: about)?|do you remember|search (?:my )?memory(?: for)?|memory(?: search)?(?: for)?|meri memory(?: me)?|yaad hai)\s*",
                "",
                question,
                flags=re.IGNORECASE,
            ).strip(" ?.,")
            inputs["query"] = query or question.strip()
        if decision.policy_tags:
            inputs["policy_tags"] = list(decision.policy_tags)
        module_request = ModuleRequest(
            request_id=operation_id,
            session_id=session_id,
            module=decision.module,
            action=decision.action,
            inputs=inputs,
            timeout_seconds=getattr(adapter, "timeout_seconds", 30),
            workspace_root=workspace_root,
        )
        with self._active_execution_lock:
            if self._shutting_down:
                return self._outcome(operation_id, "unavailable", decision, "app_shutting_down", "TARA-App is shutting down and cannot start specialist execution")
            if operation_id in self._active_executions:
                return self._outcome(operation_id, "unavailable", decision, "duplicate_request_id", "This request ID is already active")
            self._active_executions[operation_id] = (session_id, adapter)
        try:
            result = adapter.execute(module_request)
        except Exception:
            return self._outcome(operation_id, "failed", decision, "adapter_execution_failed", "Specialist execution failed")
        finally:
            with self._active_execution_lock:
                self._active_executions.pop(operation_id, None)
        if not isinstance(result, ModuleResult):
            return self._outcome(operation_id, "failed", decision, "invalid_adapter_response", "Specialist returned an invalid result")

        if decision.module == "chat" and decision.action == "respond" and result.status == "success":
            response_text = result.data.get("text") if isinstance(result.data, Mapping) else None
            if isinstance(response_text, str) and response_text.strip():
                with self._history_lock:
                    history = [dict(turn) for turn in self._conversation_history.get(session_id, [])]
                    history.extend((
                        {"role": "user", "content": question.strip()},
                        {"role": "assistant", "content": response_text.strip()},
                    ))
                    del history[:-self._history_limit]
                    if self.session_store is not None:
                        try:
                            self.session_store.replace_history(session_id, history)
                        except SessionError:
                            return self._outcome(operation_id, "failed", decision, "session_persistence_failed", "Conversation history could not be saved")
                    self._conversation_history[session_id] = history
                    self._conversation_history.move_to_end(session_id)
                    while len(self._conversation_history) > 512:
                        self._conversation_history.popitem(last=False)

        if decision.requires_approval:
            verdict = result.data.get("decision") if isinstance(result.data, Mapping) else None
            if result.status == "permission_denied" or verdict == "deny":
                return DispatchOutcome("permission_denied", decision, result, operation_id)
            if result.status != "success":
                return DispatchOutcome(result.status, decision, result, operation_id)
            if verdict not in {"allow", "approval_required"} or not decision.intended_module or not decision.intended_action:
                return self._outcome(operation_id, "failed", decision, "invalid_security_response", "TARA-Security did not return a valid assessment")
            target_capability = self.registry.capability(decision.intended_module, decision.intended_action)
            target_adapter = self.registry.adapter(decision.intended_module)
            if target_capability is None or target_adapter is None or (target_capability.read_only and not target_capability.requires_approval):
                return self._outcome(operation_id, "unavailable", decision, "approved_target_unavailable", "The assessed capability is not registered")
            try:
                target_health = target_adapter.health()
            except Exception:
                return self._outcome(operation_id, "unavailable", decision, "approved_target_health_failed", "The assessed specialist is unavailable")
            if not isinstance(target_health, AdapterHealth) or target_health.status != "healthy":
                return self._outcome(operation_id, "unavailable", decision, "approved_target_unavailable", "The assessed specialist is unavailable")
            target_attachments = self._specialist_attachments(
                decision.intended_module, decision.intended_action, safe_attachments
            )
            target_inputs = {"question": question, "attachments": target_attachments}
            try:
                self._add_specialist_attachment_inputs(
                    target_inputs, decision.intended_module, decision.intended_action, target_attachments
                )
                self._add_approval_inputs(target_inputs, decision.intended_module, decision.intended_action, question, operation_id)
            except ValueError:
                return self._outcome(operation_id, "invalid_request", decision, "approval_input_invalid", "The requested operation needs valid structured input")
            if decision.intended_module == "voice" and decision.intended_action == "speak":
                target_inputs["text"] = question
            if decision.policy_tags:
                target_inputs["policy_tags"] = list(decision.policy_tags)
            approval_id = self._store_approval(
                request_id=operation_id,
                session_id=session_id,
                question=question,
                target_module=decision.intended_module,
                target_action=decision.intended_action,
                target_inputs=target_inputs,
                workspace_root=workspace_root,
                route=decision,
            )
            pending = ModuleResult(
                status="approval_required",
                data={
                    "security_assessed": True,
                    "intended_module": decision.intended_module,
                    "intended_action": decision.intended_action,
                    "approval_id": approval_id,
                    "approval_description": self._approval_description(decision.intended_module, decision.intended_action, target_inputs),
                    "expires_in_seconds": 120,
                },
                error="TARA-Security assessed the request; approve it explicitly to continue",
            )
            return DispatchOutcome("approval_required", decision, pending, operation_id)

        return DispatchOutcome(result.status, decision, result, operation_id)

    def shutdown(self) -> None:
        """Stop accepting work and request termination of active specialist processes."""
        with self._active_execution_lock:
            self._shutting_down = True
            active = list(self._active_executions.items())
        for request_id, (_session_id, adapter) in active:
            cancel = getattr(adapter, "cancel_request", None)
            if callable(cancel):
                try:
                    cancel(request_id)
                except Exception:
                    # Shutdown continues; non-cooperating adapters remain bounded by their own timeout.
                    continue

    def cancel_request(self, request_id: str, *, session_id: str) -> str:
        """Cancel one active specialist process belonging to the given session."""
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
            return "invalid_request"
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            return "invalid_request"
        with self._active_execution_lock:
            active = self._active_executions.get(request_id)
        if active is None:
            return "not_running"
        active_session, adapter = active
        if active_session != session_id:
            return "permission_denied"
        cancel = getattr(adapter, "cancel_request", None)
        if not callable(cancel):
            return "unsupported"
        try:
            return "cancelled" if cancel(request_id) else "not_running"
        except Exception:
            return "failed"

    def approve(self, approval_id: str, *, session_id: str) -> DispatchOutcome:
        """Execute one exact, session-bound operation after explicit user approval."""
        with self._active_execution_lock:
            if self._shutting_down:
                return self._outcome("unknown", "unavailable", None, "app_shutting_down", "TARA-App is shutting down and cannot process approvals")
        if not isinstance(approval_id, str) or not approval_id or len(approval_id) > 128:
            return self._outcome("unknown", "invalid_request", None, "invalid_approval", "approval ID is invalid")
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            return self._outcome("unknown", "invalid_request", None, "invalid_session", "session ID is invalid")
        with self._approval_lock:
            pending = self._pending_approvals.get(approval_id)
            if pending is None:
                return self._outcome("unknown", "unavailable", None, "approval_expired", "Approval is missing, expired, or already used")
            if pending.session_id != session_id:
                return self._outcome(pending.request_id, "permission_denied", pending.route, "approval_session_mismatch", "Approval belongs to another session")
            self._pending_approvals.pop(approval_id, None)
        if pending.expires_at <= time.monotonic():
            return self._outcome(pending.request_id, "timeout", pending.route, "approval_expired", "Approval expired; submit the request again")
        capability = self.registry.capability(pending.target_module, pending.target_action)
        adapter = self.registry.adapter(pending.target_module)
        if capability is None or adapter is None:
            return self._outcome(pending.request_id, "unavailable", pending.route, "approved_target_unavailable", "The approved capability is no longer registered")
        try:
            health = adapter.health()
        except Exception:
            return self._outcome(pending.request_id, "unavailable", pending.route, "approved_target_health_failed", "The approved specialist is unavailable")
        if not isinstance(health, AdapterHealth) or health.status != "healthy":
            return self._outcome(pending.request_id, "unavailable", pending.route, "approved_target_unavailable", "The approved specialist is unavailable")
        request = ModuleRequest(
            request_id=pending.request_id,
            session_id=pending.session_id,
            module=pending.target_module,
            action=pending.target_action,
            inputs=pending.target_inputs,
            workspace_root=pending.workspace_root,
            approval_token=approval_id,
        )
        with self._active_execution_lock:
            if self._shutting_down:
                return self._outcome(pending.request_id, "unavailable", pending.route, "app_shutting_down", "TARA-App is shutting down and cannot start the approved operation")
            if pending.request_id in self._active_executions:
                return self._outcome(pending.request_id, "unavailable", pending.route, "duplicate_request_id", "This request ID is already active")
            self._active_executions[pending.request_id] = (pending.session_id, adapter)
        try:
            result = adapter.execute(request)
        except Exception:
            return self._outcome(pending.request_id, "failed", pending.route, "approved_action_failed", "Approved specialist execution failed")
        finally:
            with self._active_execution_lock:
                self._active_executions.pop(pending.request_id, None)
        if not isinstance(result, ModuleResult):
            return self._outcome(pending.request_id, "failed", pending.route, "invalid_adapter_response", "Specialist returned an invalid result")
        approved_route = RouteDecision(
            request_id=pending.request_id,
            status="routed",
            module=pending.target_module,
            action=pending.target_action,
            reason_code="human_approved",
            reason="The user approved this one operation after TARA-Security assessment.",
            policy_tags=pending.route.policy_tags,
        )
        return DispatchOutcome(result.status, approved_route, result, pending.request_id)

    def cancel_approval(self, approval_id: str, *, session_id: str) -> DispatchOutcome:
        if not isinstance(approval_id, str) or not approval_id or len(approval_id) > 128:
            return self._outcome("unknown", "invalid_request", None, "invalid_approval", "approval ID is invalid")
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            return self._outcome("unknown", "invalid_request", None, "invalid_session", "session ID is invalid")
        with self._approval_lock:
            pending = self._pending_approvals.get(approval_id)
            if pending is None:
                return self._outcome("unknown", "unavailable", None, "approval_expired", "Approval is missing, expired, or already used")
            if not isinstance(session_id, str) or pending.session_id != session_id:
                return self._outcome(pending.request_id, "permission_denied", pending.route, "approval_session_mismatch", "Approval belongs to another session")
            self._pending_approvals.pop(approval_id, None)
        result = ModuleResult("success", {"cancelled": True})
        return DispatchOutcome("cancelled", pending.route, result, pending.request_id)

    def _store_approval(
        self,
        *,
        request_id: str,
        session_id: str,
        question: str,
        target_module: str,
        target_action: str,
        target_inputs: Mapping[str, Any],
        workspace_root: str | None,
        route: RouteDecision,
    ) -> str:
        approval_id = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._approval_lock:
            for key, item in list(self._pending_approvals.items()):
                if item.expires_at <= now:
                    self._pending_approvals.pop(key, None)
            self._pending_approvals[approval_id] = PendingApproval(
                approval_id=approval_id,
                request_id=request_id,
                session_id=session_id,
                question=question,
                target_module=target_module,
                target_action=target_action,
                target_inputs=dict(target_inputs),
                workspace_root=workspace_root,
                route=route,
                expires_at=now + 120,
                description=self._approval_description(target_module, target_action, target_inputs),
            )
            while len(self._pending_approvals) > 32:
                self._pending_approvals.popitem(last=False)
        return approval_id

    @staticmethod
    def _approval_description(module: str, action: str, inputs: Mapping[str, Any]) -> str:
        if module == "memory" and action == "store":
            return f"Store the note under key '{inputs.get('key', '')}' in local memory."
        if module == "memory" and action == "forget":
            return f"Delete the local memory entry named '{inputs.get('key', '')}'."
        if module == "action" and action == "execute" and inputs.get("operation") == "github.issue.create":
            return f"Create a GitHub issue in {inputs.get('repository')} titled '{inputs.get('title')}'."
        if module == "action" and action == "execute" and inputs.get("operation") == "desktop.app.open":
            label = {"calculator": "Calculator", "notepad": "Notepad", "paint": "Paint"}.get(inputs.get("application"), "the requested app")
            return f"Open {label} on this computer."
        if module == "action" and action == "execute" and inputs.get("operation") == "desktop.url.open":
            return f"Open this website in your browser: {inputs.get('url')}."
        return f"Run {module}.{action} once."

    @staticmethod
    def _add_approval_inputs(inputs: dict[str, Any], module: str, action: str, question: str, request_id: str) -> None:
        if module == "action" and action == "execute":
            app_match = re.fullmatch(
                r"\s*(?:(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?(?P<app>calculator|calc|notepad|text editor|paint|mspaint)|"
                r"(?P<app_hindi>calculator|calc|notepad|paint)\s+(?:kholo|khol(?:o)?|open\s+karo|start\s+karo))\s*[.!]?\s*",
                question,
                flags=re.IGNORECASE,
            )
            if app_match is not None:
                requested_app = (app_match.group("app") or app_match.group("app_hindi")).casefold()
                application = {
                    "calc": "calculator", "calculator": "calculator",
                    "notepad": "notepad", "text editor": "notepad",
                    "paint": "paint", "mspaint": "paint",
                }[requested_app]
                inputs.update({"operation": "desktop.app.open", "application": application})
                return
            website_match = re.fullmatch(
                r"""\s*(?:please\s+)?(?:open|visit|go\s+to|browse|kholo|khol(?:o)?)\s+(?:the\s+)?"""
                r"""(?P<url>https?://[^\s<>\"']+|www\.[^\s<>\"']+|[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}\.)+[A-Za-z]{2,63}(?::\d{1,5})?(?:[/?#][^\s<>\"']*)?)\s*[.!?]?\s*""",
                question,
                flags=re.IGNORECASE,
            )
            if website_match is not None:
                raw_url = website_match.group("url")
                # Preserve punctuation in explicit URLs: it can be meaningful in
                # query values/fragments. Only trim sentence punctuation from
                # shorthand hosts where it cannot be part of an explicit URL.
                if not raw_url.casefold().startswith(("http://", "https://")):
                    raw_url = raw_url.rstrip(".,!?;:")
                url = raw_url if raw_url.casefold().startswith(("http://", "https://")) else "https://" + raw_url
                if len(url) > 2048 or any(ord(char) < 32 or ord(char) == 127 for char in url):
                    raise ValueError("website address must contain 1 to 2048 valid characters")
                try:
                    parsed_url = urlsplit(url)
                    port = parsed_url.port
                except ValueError as exc:
                    raise ValueError("website address is invalid") from exc
                if (
                    parsed_url.scheme.casefold() not in {"http", "https"}
                    or not parsed_url.hostname
                    or parsed_url.username is not None
                    or parsed_url.password is not None
                    or (port is not None and not 1 <= port <= 65535)
                ):
                    raise ValueError("only valid HTTP or HTTPS websites can be approved")
                inputs.update({"operation": "desktop.url.open", "url": url})
                return
            match = re.fullmatch(
                r"\s*(?:create|open)\s+(?:a\s+)?(?:github\s+)?issue\s+in\s+([A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100})\s*(?::|with title\s+|titled\s+)(.+?)\s*",
                question,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match is None:
                raise ValueError("GitHub issue request must include an allowlisted repository and title")
            repository, details = match.group(1), match.group(2).strip()
            sections = re.split(r"\n\s*\n(?:body|description)\s*:\s*", details, maxsplit=1, flags=re.IGNORECASE)
            title, body = sections[0].strip(), sections[1].strip() if len(sections) == 2 else ""
            if not title or len(title) > 256 or len(body) > 10_000:
                raise ValueError("GitHub issue title or body exceeds the configured limit")
            inputs.update({"operation": "github.issue.create", "repository": repository, "title": title, "body": body})
            return
        if module != "memory":
            return
        if action == "store":
            content = re.sub(r"^\s*(?:remember(?:\s+(?:this|that))?|save(?:\s+(?:this|to memory))?|store(?:\s+(?:this|in memory))?|yaad rakh(?:na)?)\s*[:,-]?\s*", "", question, flags=re.IGNORECASE).strip()
            if not content or len(content) > 2000:
                raise ValueError("memory note must contain 1 to 2000 characters")
            match = re.fullmatch(r"(.{1,120}?)(?:\s+(?:is|are)\s+|\s*[:=]\s*)(.{1,2000})", content, flags=re.IGNORECASE | re.DOTALL)
            if match:
                key, value = match.group(1).strip(), match.group(2).strip()
            else:
                key = "note-" + hashlib.sha256(content.casefold().encode("utf-8")).hexdigest()[:16]
                value = content
            if not key or not value or len(value) > 2000:
                raise ValueError("memory note must contain a key and value")
            inputs.update({"key": key, "value": value})
        elif action == "forget":
            key = re.sub(r"^\s*(?:forget(?:\s+(?:this|my))?|delete from memory|remove from memory|bhool ja(?:o)?)\s*[:,-]?\s*", "", question, flags=re.IGNORECASE).strip().strip("\"'")
            if not key or len(key) > 120:
                raise ValueError("memory key must contain 1 to 120 characters")
            inputs["key"] = key

    @staticmethod
    def _validate_attachments(attachments: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        if not isinstance(attachments, Sequence) or isinstance(attachments, (str, bytes)) or len(attachments) > 20:
            raise ValueError("attachments are invalid")
        safe: list[dict[str, str]] = []
        total_content_bytes = 0
        max_encoded_bytes = 4 * ((10_000_000 + 2) // 3)
        for item in attachments:
            if not isinstance(item, Mapping) or set(item) - {"media_type", "name", "content_base64"}:
                raise ValueError("attachment metadata is invalid")
            media_type = item.get("media_type", "")
            name = item.get("name", "")
            if not isinstance(media_type, str) or not media_type or len(media_type) > 128:
                raise ValueError("attachment media_type is invalid")
            if not isinstance(name, str) or len(name) > 255:
                raise ValueError("attachment name is invalid")
            normalized_media_type = media_type.casefold()
            suffix = "." + name.rsplit(".", 1)[-1].casefold() if "." in name else ""
            if normalized_media_type.startswith("audio/") or suffix in _AUDIO_SUFFIX_TYPES:
                if normalized_media_type not in _AUDIO_MEDIA_TYPES:
                    normalized_media_type = _AUDIO_SUFFIX_TYPES.get(suffix, "")
                if normalized_media_type not in _AUDIO_MEDIA_TYPES:
                    raise ValueError("audio attachment format is not supported")
            normalized = {"media_type": normalized_media_type, "name": name}
            content = item.get("content_base64")
            if content is not None:
                if not isinstance(content, str) or not content or len(content) > max_encoded_bytes:
                    raise ValueError("attachment content is invalid")
                try:
                    decoded = base64.b64decode(content, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise ValueError("attachment content is invalid") from exc
                if not decoded or len(decoded) > 10_000_000:
                    raise ValueError("attachment content is outside the 10 MB size limit")
                total_content_bytes += len(decoded)
                if total_content_bytes > 10_000_000:
                    raise ValueError("combined attachment content exceeds the 10 MB per-message limit")
                normalized["content_base64"] = base64.b64encode(decoded).decode("ascii")
            safe.append(normalized)
        return safe

    @staticmethod
    def _specialist_attachments(
        module: str,
        action: str,
        attachments: Sequence[Mapping[str, str]],
    ) -> list[dict[str, str]]:
        def metadata(items: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
            return [{"media_type": item["media_type"], "name": item["name"]} for item in items]

        if module == "security":
            return metadata(attachments)
        if module == "code" and action == "plan":
            code_attachments = [
                dict(item)
                for item in attachments
                if item.get("content_base64")
                and item.get("name", "").casefold().endswith((
                    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
                    ".java", ".go", ".rs", ".c", ".h", ".cc", ".hh", ".hpp",
                    ".cpp", ".cxx", ".cs", ".rb", ".php", ".sh", ".bash", ".zsh",
                    ".ps1", ".sql", ".swift", ".kt", ".kts", ".dart", ".scala",
                    ".lua", ".pl", ".r", ".json", ".yaml", ".yml", ".toml", ".md"
                ))
            ][:4]
            total_source_bytes = sum(
                len(base64.b64decode(item["content_base64"], validate=True))
                for item in code_attachments
            )
            if total_source_bytes > 512_000:
                raise ValueError("Code accepts at most 512 KB of combined source attachments")
            return code_attachments
        if module == "vision" and action == "analyze":
            images = [
                dict(item) for item in attachments
                if item.get("media_type", "").casefold().startswith("image/")
                and item.get("content_base64")
            ][:4]
            if sum(len(base64.b64decode(item["content_base64"], validate=True)) for item in images) > 512_000:
                raise ValueError("Vision accepts at most 512 KB of combined image data")
            return images
        if module == "voice" and action == "transcribe":
            audio = [
                dict(item) for item in attachments
                if item.get("media_type", "").casefold().startswith("audio/")
                and item.get("content_base64")
            ][:1]
            if sum(len(base64.b64decode(item["content_base64"], validate=True)) for item in audio) > 512_000:
                raise ValueError("Voice accepts at most 512 KB of audio data")
            return audio
        if module == "study" and action == "create":
            study_files = [
                item for item in attachments
                if item.get("content_base64") and (
                    item.get("name", "").casefold().endswith((".txt", ".md", ".markdown", ".rst", ".csv", ".pdf"))
                    or item.get("media_type", "").casefold().startswith("text/")
                    or item.get("media_type", "").casefold() == "application/pdf"
                )
            ][:4]
            return [dict(item) for item in study_files]
        if module == "data" and action == "analyze":
            csv_files = [
                dict(item) for item in attachments
                if (
                    item.get("media_type", "").casefold() == "text/csv"
                    or item.get("name", "").casefold().endswith(".csv")
                )
                and item.get("content_base64")
            ][:1]
            if sum(len(base64.b64decode(item["content_base64"], validate=True)) for item in csv_files) > 512_000:
                raise ValueError("Data analysis accepts at most 512 KB of CSV data")
            return csv_files
        return []

    @staticmethod
    def _add_specialist_attachment_inputs(
        inputs: dict[str, Any],
        module: str,
        action: str,
        attachments: Sequence[Mapping[str, str]],
    ) -> None:
        if module == "code" and action == "plan":
            # Source code stays in the Code adapter's explicitly attached context.
            return
        if module == "vision" and action == "analyze":
            images = [item["content_base64"] for item in attachments if item.get("content_base64")]
            if images:
                inputs["images"] = images[:4]
        elif module == "voice" and action == "transcribe":
            audio = next((item for item in attachments if item.get("content_base64")), None)
            if audio is not None:
                # The media type is selected from the matching attachment metadata.
                inputs["audio_base64"] = audio["content_base64"]
                inputs["media_type"] = audio.get("media_type", "application/octet-stream")
        elif module == "data" and action == "analyze":
            csv_file = next((item for item in attachments if item.get("content_base64")), None)
            if csv_file is not None:
                try:
                    text = base64.b64decode(csv_file["content_base64"], validate=True).decode("utf-8-sig")
                except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
                    raise ValueError("CSV attachment is invalid") from exc
                inputs["csv_text"] = text
        if module in {"vision", "voice", "data"}:
            inputs["attachments"] = [
                {"media_type": item["media_type"], "name": item["name"]}
                for item in attachments
            ]

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


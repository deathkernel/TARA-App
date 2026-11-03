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
from tara_app.mcp_app import McpOrchestratorMixin
from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.ollama_models import OllamaModelCatalog
from tara_app.registry import CapabilityRegistry

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


class Orchestrator(McpOrchestratorMixin):
    """Uses Router proposals and registered module adapters; it never auto-approves."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        router: RouterClient,
        *,
        model_catalog: OllamaModelCatalog | None = None,
    ) -> None:
        self.registry = registry
        self.router = router
        self.model_catalog = model_catalog
        self._init_mcp_state(None)
        self._conversation_history: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        self._history_lock = RLock()
        self._pending_approvals: OrderedDict[str, PendingApproval] = OrderedDict()
        self._approval_lock = RLock()

    # NOTE: Body of Orchestrator methods is imported from the main implementation.
    # This truncated push is incomplete — DO NOT USE.

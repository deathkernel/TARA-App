"""Versioned, bounded contracts for TARA-App and specialist adapters."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
MAX_PAYLOAD_BYTES = 1_000_000
MAX_TIMEOUT_SECONDS = 600
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class ContractError(ValueError):
    """Raised when an adapter request or response violates the public contract."""


@dataclass(frozen=True, slots=True)
class Capability:
    """A module capability and its declared execution policy."""

    module_id: str
    action: str
    description: str
    read_only: bool
    requires_approval: bool = False

    def __post_init__(self) -> None:
        if not _NAME_PATTERN.fullmatch(self.module_id) or not _NAME_PATTERN.fullmatch(self.action):
            raise ContractError("module_id and action must be simple identifiers")
        if not self.description.strip() or len(self.description) > 500:
            raise ContractError("capability description must contain 1 to 500 characters")
        if self.read_only and self.requires_approval:
            raise ContractError("a read-only capability cannot require mutation approval")

    @property
    def capability_id(self) -> str:
        return f"{self.module_id}.{self.action}"


@dataclass(frozen=True, slots=True)
class ModuleRequest:
    """A validated call from TARA-App to one specialist adapter."""

    request_id: str
    session_id: str
    module: str
    action: str
    inputs: Mapping[str, Any]
    timeout_seconds: int = 30
    workspace_root: str | None = None
    approval_token: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported schema_version")
        if not self.request_id.strip() or len(self.request_id) > 128:
            raise ContractError("request_id must be a non-empty string of at most 128 characters")
        if not self.session_id.strip() or len(self.session_id) > 128:
            raise ContractError("session_id must be a non-empty string of at most 128 characters")
        if not _NAME_PATTERN.fullmatch(self.module) or not _NAME_PATTERN.fullmatch(self.action):
            raise ContractError("module and action must be simple identifiers")
        if not isinstance(self.inputs, Mapping):
            raise ContractError("inputs must be an object")
        if not 1 <= self.timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ContractError("timeout_seconds is outside the allowed range")
        if self.workspace_root is not None and (not isinstance(self.workspace_root, str) or len(self.workspace_root) > 4096):
            raise ContractError("workspace_root must be a bounded path string")
        if self.approval_token is not None and (not isinstance(self.approval_token, str) or len(self.approval_token) > 512):
            raise ContractError("approval_token must be a bounded string")
        try:
            encoded = json.dumps(self.to_payload(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ContractError("inputs must contain JSON values only") from exc
        if len(encoded) > MAX_PAYLOAD_BYTES:
            raise ContractError("module request exceeds the payload limit")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "module": self.module,
            "action": self.action,
            "inputs": dict(self.inputs),
            "workspace_root": self.workspace_root,
            "timeout_seconds": self.timeout_seconds,
            "approval_token": self.approval_token,
        }


@dataclass(frozen=True, slots=True)
class ModuleResult:
    """Normalized result from a specialist adapter."""

    status: str
    data: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    schema_version: str = SCHEMA_VERSION

    _STATUSES = frozenset(
        {"success", "unavailable", "invalid_request", "permission_denied", "approval_required", "timeout", "failed"}
    )

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported result schema_version")
        if self.status not in self._STATUSES:
            raise ContractError("unsupported module result status")
        if not isinstance(self.data, Mapping):
            raise ContractError("result data must be an object")
        if self.error is not None and (not isinstance(self.error, str) or len(self.error) > 2000):
            raise ContractError("result error must be a bounded string")
        if not isinstance(self.duration_ms, int) or self.duration_ms < 0:
            raise ContractError("duration_ms must be a non-negative integer")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "data": dict(self.data),
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    status: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status not in {"healthy", "degraded", "unavailable"}:
            raise ContractError("unsupported adapter health status")
        if len(self.detail) > 500:
            raise ContractError("health detail is too long")


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Validated result of a TARA-Router call."""

    request_id: str
    status: str
    module: str | None
    action: str | None
    reason_code: str
    reason: str
    intended_module: str | None = None
    intended_action: str | None = None
    requires_approval: bool = False
    policy_tags: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported route schema_version")
        if self.status not in {"routed", "unavailable", "invalid_request"}:
            raise ContractError("unsupported route status")
        if not self.request_id or len(self.request_id) > 128:
            raise ContractError("route request_id is invalid")
        if len(self.reason_code) > 100 or len(self.reason) > 500:
            raise ContractError("route explanation is too long")
        if self.status == "routed" and (not self.module or not self.action):
            raise ContractError("routed decisions require a module and action")
        if self.module is not None and not _NAME_PATTERN.fullmatch(self.module):
            raise ContractError("route module is invalid")
        if self.action is not None and not _NAME_PATTERN.fullmatch(self.action):
            raise ContractError("route action is invalid")
        if self.requires_approval and self.status == "routed" and self.module != "security":
            raise ContractError("approval-gated routes must first select TARA-Security")
        if len(self.policy_tags) > 32 or any(not isinstance(tag, str) or len(tag) > 100 for tag in self.policy_tags):
            raise ContractError("route policy tags are invalid")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> RouteDecision:
        if not isinstance(payload, Mapping):
            raise ContractError("route response must be an object")
        allowed = {
            "schema_version", "request_id", "status", "module", "action", "reason_code", "reason",
            "intended_module", "intended_action", "requires_approval", "policy_tags",
        }
        if set(payload) - allowed:
            raise ContractError("route response contains unsupported fields")
        version = payload.get("schema_version", SCHEMA_VERSION)
        strings = ("request_id", "status", "reason_code", "reason")
        if any(not isinstance(payload.get(key), str) for key in strings):
            raise ContractError("route response is missing required string fields")
        for key in ("module", "action", "intended_module", "intended_action"):
            if payload.get(key) is not None and not isinstance(payload.get(key), str):
                raise ContractError("route destination fields must be strings or null")
        approval = payload.get("requires_approval", False)
        tags = payload.get("policy_tags", [])
        if not isinstance(approval, bool) or not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ContractError("route policy fields are invalid")
        return cls(
            schema_version=version,
            request_id=payload["request_id"],
            status=payload["status"],
            module=payload.get("module"),
            action=payload.get("action"),
            reason_code=payload["reason_code"],
            reason=payload["reason"],
            intended_module=payload.get("intended_module"),
            intended_action=payload.get("intended_action"),
            requires_approval=approval,
            policy_tags=tuple(tags),
        )

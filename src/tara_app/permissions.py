"""Fail-closed capability permission decisions for orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class PermissionAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class PermissionDecision:
    action: PermissionAction
    capability: str
    reason: str


@dataclass(frozen=True)
class PermissionPolicy:
    """Explicit capability allowlist; unknown capabilities never execute."""

    allowed_capabilities: frozenset[str] = frozenset()
    approval_required: frozenset[str] = frozenset()
    disabled_capabilities: frozenset[str] = frozenset({"shell", "arbitrary_shell", "auto_merge", "silent_install"})

    @classmethod
    def from_iterables(
        cls,
        *,
        allowed_capabilities: Iterable[str] = (),
        approval_required: Iterable[str] = (),
        disabled_capabilities: Iterable[str] = ("shell", "arbitrary_shell", "auto_merge", "silent_install"),
    ) -> "PermissionPolicy":
        return cls(
            frozenset(allowed_capabilities),
            frozenset(approval_required),
            frozenset(disabled_capabilities),
        )

    def evaluate(self, capability: str, *, approved: bool = False) -> PermissionDecision:
        if not isinstance(capability, str) or not capability.strip():
            return PermissionDecision(PermissionAction.DENY, str(capability), "Capability must be a non-empty string")
        if capability in self.disabled_capabilities:
            return PermissionDecision(PermissionAction.DENY, capability, "Capability is disabled by safety policy")
        if capability not in self.allowed_capabilities:
            return PermissionDecision(PermissionAction.DENY, capability, "Capability is not explicitly allowlisted")
        if capability in self.approval_required and not approved:
            return PermissionDecision(PermissionAction.REQUIRE_APPROVAL, capability, "Explicit user approval is required")
        return PermissionDecision(PermissionAction.ALLOW, capability, "Capability is allowed by local policy")

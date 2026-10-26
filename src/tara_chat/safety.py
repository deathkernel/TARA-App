"""Small safety boundaries for TARA's future agent execution layer.

The safety layer is intentionally separate from PC tools. It decides whether
an action is permitted and records decisions, but does not execute anything.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Permission:
    """Named permission controlling one action capability."""

    name: str
    allowed: bool = False

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("permission name must be a non-empty string")


@dataclass(frozen=True)
class SafetyDecision:
    """Immutable record of an authorization decision."""

    action: str
    allowed: bool
    reason: str
    timestamp: str


class SafetyPolicy:
    """Explicit allow-list policy with an auditable decision log."""

    def __init__(self, permissions=()):
        self._permissions = {permission.name: permission.allowed
                             for permission in permissions}
        self._log = []

    def set_permission(self, name, allowed):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("permission name must be a non-empty string")
        self._permissions[name] = bool(allowed)

    def check(self, action):
        if not isinstance(action, str) or not action.strip():
            raise ValueError("action must be a non-empty string")
        allowed = bool(self._permissions.get(action, False))
        reason = "explicit permission" if action in self._permissions else "no permission"
        if not allowed and action in self._permissions:
            reason = "permission denied"
        decision = SafetyDecision(
            action=action,
            allowed=allowed,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._log.append(decision)
        return decision

    def audit_log(self):
        return list(self._log)

    def clear_audit_log(self):
        self._log.clear()


class ConfirmationGate:
    """Require explicit confirmation for designated destructive actions."""

    def __init__(self, destructive_actions=()):
        self._destructive = set(destructive_actions)

    def requires_confirmation(self, action):
        return action in self._destructive

    def authorize(self, action, confirmed=False):
        if self.requires_confirmation(action) and not confirmed:
            return False
        return True

"""Fail-closed policy gate for future coding-agent execution integrations."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SandboxCapabilities:
    isolated: bool = False
    network_enabled: bool = False
    write_enabled: bool = False
    max_seconds: int = 60
    max_output_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        for name in ("isolated", "network_enabled", "write_enabled"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if type(self.max_seconds) is not int or not 1 <= self.max_seconds <= 3600:
            raise ValueError("max_seconds must be between 1 and 3600")
        if type(self.max_output_bytes) is not int or not 1 <= self.max_output_bytes <= 10_000_000:
            raise ValueError("max_output_bytes must be between 1 and 10000000")

def may_execute(
    capabilities: SandboxCapabilities,
    *,
    user_approved: bool,
    requires_network: bool = False,
    requires_write: bool = False,
) -> bool:
    """Allow only explicitly approved, isolated operations with required capabilities.

    Network and filesystem writes are denied unless both the sandbox grants that
    capability and the caller explicitly declares that it is required.
    """
    if type(user_approved) is not bool or not user_approved:
        return False
    if type(requires_network) is not bool or type(requires_write) is not bool:
        return False
    if not capabilities.isolated:
        return False
    if requires_network and not capabilities.network_enabled:
        return False
    if requires_write and not capabilities.write_enabled:
        return False
    return True

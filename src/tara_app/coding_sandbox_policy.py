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
        if type(self.max_seconds) is not int or not 1 <= self.max_seconds <= 3600:
            raise ValueError("max_seconds must be between 1 and 3600")
        if type(self.max_output_bytes) is not int or not 1 <= self.max_output_bytes <= 10_000_000:
            raise ValueError("max_output_bytes must be between 1 and 10000000")

def may_execute(capabilities: SandboxCapabilities, *, user_approved: bool) -> bool:
    """Execution is denied unless isolation and explicit approval are both present."""
    if type(user_approved) is not bool:
        return False
    return capabilities.isolated and user_approved

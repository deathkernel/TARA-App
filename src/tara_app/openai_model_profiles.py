"""Validated metadata for optional local models; never downloads weights or calls a provider."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class LocalModelProfile:
    model_id: str
    runtime: str
    context_tokens: int | None = None
    min_ram_gb: int | None = None
    enabled: bool = False

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.runtime.strip():
            raise ValueError("model_id and runtime are required")
        for name in ("context_tokens", "min_ram_gb"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive integer when provided")
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be boolean")

def default_local_profiles() -> tuple[LocalModelProfile, ...]:
    """Return metadata only; hardware and runtime availability must be probed separately."""
    return (LocalModelProfile(model_id="gpt-oss", runtime="ollama", enabled=False),)

def profile_available(profile: LocalModelProfile, installed_runtimes: set[str]) -> bool:
    """Report configured runtime presence only; this does not imply model weights are installed."""
    return profile.runtime in installed_runtimes

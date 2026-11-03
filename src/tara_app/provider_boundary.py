"""Provider-neutral boundary; implementations must be injected and explicitly enabled."""
from __future__ import annotations
from collections.abc import Callable, Mapping
from typing import Any

class ProviderDisabledError(RuntimeError):
    pass

class OptionalProvider:
    def __init__(self, request: Callable[[Mapping[str, Any]], Any] | None = None, *, enabled: bool = False) -> None:
        if type(enabled) is not bool:
            raise ValueError("enabled must be boolean")
        self._request, self._enabled = request, enabled

    def complete(self, payload: Mapping[str, Any]) -> Any:
        if not self._enabled or self._request is None:
            raise ProviderDisabledError("remote provider is not configured and enabled")
        if not isinstance(payload, Mapping):
            raise ValueError("payload must be a mapping")
        # Secret handling, transport, retries, and redaction belong to a reviewed implementation.
        return self._request(payload)

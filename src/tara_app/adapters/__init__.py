"""Protocols shared by the TARA-App runtime and specialist adapters."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from tara_app.contracts import Capability, ModuleRequest, ModuleResult, RouteDecision


class RouterClient(Protocol):
    """Minimal contract required from the configured TARA-Router client."""

    def route(self, request_payload: Mapping[str, object]) -> RouteDecision: ...


class ModuleAdapter(Protocol):
    """Capability provider invoked by the central policy-enforcing orchestrator."""

    module_id: str
    capabilities: Sequence[Capability]

    def handle(self, request: ModuleRequest) -> ModuleResult: ...


__all__ = ["ModuleAdapter", "RouterClient"]

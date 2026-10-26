"""TARA-App runtime foundation."""

from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.orchestrator import DispatchOutcome, Orchestrator
from tara_app.registry import CapabilityRegistry, RegistryError
from tara_app.router_client import RouterUnavailableError, StdioRouterClient

__all__ = [
    "AdapterHealth",
    "Capability",
    "CapabilityRegistry",
    "DispatchOutcome",
    "ModuleRequest",
    "ModuleResult",
    "Orchestrator",
    "RegistryError",
    "RouteDecision",
    "RouterUnavailableError",
    "StdioRouterClient",
]

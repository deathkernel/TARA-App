"""TARA-App runtime foundation."""

from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.orchestrator import DispatchOutcome, Orchestrator
from tara_app.registry import CapabilityRegistry, RegistryError
from tara_app.router_client import RouterUnavailableError, StdioRouterClient
from tara_app.runtime import RuntimeConfigurationError, create_application

__all__ = [
    "AdapterHealth",
    "Capability",
    "CapabilityRegistry",
    "DispatchOutcome",
    "ModuleRequest",
    "ModuleResult",
    "Orchestrator",
    "RegistryError",
    "RuntimeConfigurationError",
    "RouteDecision",
    "RouterUnavailableError",
    "StdioRouterClient",
    "create_application",
]


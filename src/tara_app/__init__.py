"""SITA runtime foundation."""

from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.orchestrator import DispatchOutcome, Orchestrator
from tara_app.registry import CapabilityRegistry, RegistryError
from tara_app.router_client import RouterUnavailableError, StdioRouterClient
from tara_app.application.bootstrap import RuntimeConfigurationError, create_application
from tara_app.application.facade import ApplicationFacade

__all__ = [
    "AdapterHealth",
    "ApplicationFacade",
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


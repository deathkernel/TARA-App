"""Capability registry for explicitly registered specialist adapters."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from tara_app.contracts import (
    SPECIALIST_CONTRACT_VERSION, SpecialistAdapter, SpecialistRequest, SpecialistResult,
)


class CapabilityRegistryError(RuntimeError):
    """Raised for invalid or unavailable specialist registration/dispatch."""


@dataclass(frozen=True)
class CapabilityDescriptor:
    specialist_id: str
    capabilities: tuple[str, ...]
    contract_version: int
    enabled: bool


class CapabilityRegistry:
    """In-memory registry; it never discovers or launches arbitrary executables."""

    def __init__(self) -> None:
        self._adapters: dict[str, tuple[SpecialistAdapter, frozenset[str]]] = {}
        self._lock = RLock()

    def register(self, adapter: SpecialistAdapter, capabilities: tuple[str, ...], *, enabled: bool = False) -> None:
        specialist_id = getattr(adapter, "specialist_id", None)
        if not isinstance(specialist_id, str) or not specialist_id.strip():
            raise CapabilityRegistryError("adapter must provide a non-empty specialist_id")
        if not isinstance(capabilities, tuple) or not capabilities or any(
            not isinstance(capability, str) or not capability.strip() for capability in capabilities
        ):
            raise CapabilityRegistryError("capabilities must be a non-empty tuple of names")
        if type(enabled) is not bool:
            raise CapabilityRegistryError("enabled must be boolean")
        version = getattr(adapter, "contract_version", SPECIALIST_CONTRACT_VERSION)
        if type(version) is not int or version != SPECIALIST_CONTRACT_VERSION:
            raise CapabilityRegistryError("adapter contract version is unsupported")
        with self._lock:
            if specialist_id in self._adapters:
                raise CapabilityRegistryError(f"specialist {specialist_id!r} is already registered")
            self._adapters[specialist_id] = (adapter, frozenset(capabilities) if enabled else frozenset())

    def set_enabled(self, specialist_id: str, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise CapabilityRegistryError("enabled must be boolean")
        with self._lock:
            current = self._adapters.get(specialist_id)
            if current is None:
                raise CapabilityRegistryError("specialist is not registered")
            adapter, capabilities = current
            # Original declared capabilities are retained separately in the descriptor map.
            declared = getattr(adapter, "capabilities", None)
            if not isinstance(declared, (list, tuple, set, frozenset)):
                declared = capabilities
            self._adapters[specialist_id] = (adapter, frozenset(declared) if enabled else frozenset())

    def describe(self) -> list[CapabilityDescriptor]:
        with self._lock:
            return [
                CapabilityDescriptor(
                    specialist_id=specialist_id,
                    capabilities=tuple(sorted(capabilities)),
                    contract_version=getattr(adapter, "contract_version", SPECIALIST_CONTRACT_VERSION),
                    enabled=bool(capabilities),
                )
                for specialist_id, (adapter, capabilities) in sorted(self._adapters.items())
            ]

    def dispatch(self, specialist_id: str, request: SpecialistRequest) -> SpecialistResult:
        with self._lock:
            item = self._adapters.get(specialist_id)
        if item is None:
            raise CapabilityRegistryError("specialist is not registered")
        adapter, capabilities = item
        if request.contract_version != SPECIALIST_CONTRACT_VERSION:
            raise CapabilityRegistryError("request contract version is unsupported")
        if request.capability not in capabilities:
            raise CapabilityRegistryError("capability is disabled or not registered for this specialist")
        if request.payload is None or not isinstance(request.payload, dict):
            raise CapabilityRegistryError("request payload must be an object")
        result = adapter.handle(request)
        if not isinstance(result, SpecialistResult):
            raise CapabilityRegistryError("adapter returned an invalid result contract")
        if result.request_id != request.request_id:
            raise CapabilityRegistryError("adapter response request_id does not match request")
        if result.contract_version != SPECIALIST_CONTRACT_VERSION:
            raise CapabilityRegistryError("adapter response contract version is unsupported")
        return result

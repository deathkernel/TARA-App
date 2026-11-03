"""Capability registry for independently versioned TARA modules."""

from __future__ import annotations

from tara_app.adapters import ModuleAdapter
from tara_app.contracts import Capability


class RegistryError(ValueError):
    """Raised when an adapter registration is ambiguous or invalid."""


class CapabilityRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ModuleAdapter] = {}
        self._capabilities: dict[str, Capability] = {}

    def register(self, adapter: ModuleAdapter) -> None:
        module_id = adapter.module_id
        if not isinstance(module_id, str) or not module_id:
            raise RegistryError("adapter must declare a module_id")
        if module_id in self._adapters:
            raise RegistryError(f"module is already registered: {module_id}")
        capabilities = tuple(adapter.capabilities)
        if not capabilities:
            raise RegistryError("adapter must advertise at least one capability")
        for capability in capabilities:
            if not isinstance(capability, Capability) or capability.module_id != module_id:
                raise RegistryError("capability ownership must match the adapter module_id")
            if capability.capability_id in self._capabilities:
                raise RegistryError(f"capability is already registered: {capability.capability_id}")
        self._adapters[module_id] = adapter
        self._capabilities.update({capability.capability_id: capability for capability in capabilities})

    def capability_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))

    def capability(self, module_id: str, action: str) -> Capability | None:
        return self._capabilities.get(f"{module_id}.{action}")

    def adapter(self, module_id: str) -> ModuleAdapter | None:
        return self._adapters.get(module_id)

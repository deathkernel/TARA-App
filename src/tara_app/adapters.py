"""Public adapter protocols; implementations stay in their own repositories."""

from __future__ import annotations

from typing import Protocol, Sequence

from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult


class ModuleAdapter(Protocol):
    """Versioned specialist boundary used by TARA-App."""

    @property
    def module_id(self) -> str: ...

    @property
    def capabilities(self) -> Sequence[Capability]: ...

    def health(self) -> AdapterHealth: ...

    def execute(self, request: ModuleRequest) -> ModuleResult: ...


class RouterClient(Protocol):
    """Routes a question using only capabilities registered in TARA-App."""

    def route(self, request_payload: dict[str, object]): ...

"""Review-only TARA-Code adapter; never executes or applies proposed changes."""
from __future__ import annotations

from typing import Any, Callable

from tara_app.contracts import SPECIALIST_CONTRACT_VERSION, SpecialistRequest, SpecialistResult


class TaraCodeAdapter:
    specialist_id = "tara-code"
    contract_version = SPECIALIST_CONTRACT_VERSION

    def __init__(self, plan: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        if not callable(plan):
            raise ValueError("plan must be callable")
        self._plan = plan

    def handle(self, request: SpecialistRequest) -> SpecialistResult:
        if request.contract_version != self.contract_version:
            return SpecialistResult(request.request_id, "incompatible_contract")
        if request.capability not in {"code.plan", "code.review"}:
            return SpecialistResult(request.request_id, "unsupported_capability")
        if not isinstance(request.payload, dict):
            return SpecialistResult(request.request_id, "invalid_request")
        try:
            proposal = self._plan(dict(request.payload))
        except Exception:
            return SpecialistResult(request.request_id, "failed",
                                    warnings=("planning engine invocation failed",))
        if not isinstance(proposal, dict):
            return SpecialistResult(request.request_id, "invalid_response",
                                    warnings=("planning engine must return an object",))
        proposed_changes = proposal.get("proposed_changes", [])
        warnings = proposal.get("warnings", [])
        if not isinstance(proposed_changes, list) or any(not isinstance(change, dict) for change in proposed_changes):
            return SpecialistResult(request.request_id, "invalid_response",
                                    warnings=("proposed_changes must be a list of objects",))
        if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
            return SpecialistResult(request.request_id, "invalid_response",
                                    warnings=("warnings must be a list of strings",))
        # The adapter returns suggestions only. It has no filesystem or subprocess capability.
        output = {key: value for key, value in proposal.items()
                  if key not in {"proposed_changes", "warnings"}}
        return SpecialistResult(
            request.request_id, "ok", output=output,
            proposed_changes=tuple(proposed_changes), warnings=tuple(warnings),
        )

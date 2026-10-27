"""Narrow adapter for an injected TARA-Chat callable; no sibling import or process launch."""
from __future__ import annotations

from typing import Any, Callable

from tara_app.contracts import SPECIALIST_CONTRACT_VERSION, SpecialistRequest, SpecialistResult


class ChatAdapterError(RuntimeError):
    """Raised when the injected chat engine cannot satisfy the adapter contract."""


class TaraChatAdapter:
    specialist_id = "tara-chat"
    contract_version = SPECIALIST_CONTRACT_VERSION

    def __init__(self, reply: Callable[[str, list[dict[str, str]]], str]) -> None:
        if not callable(reply):
            raise ValueError("reply must be callable")
        self._reply = reply

    def handle(self, request: SpecialistRequest) -> SpecialistResult:
        if request.contract_version != self.contract_version:
            return SpecialistResult(request.request_id, "incompatible_contract")
        if request.capability != "chat.reply":
            return SpecialistResult(request.request_id, "unsupported_capability")
        payload = request.payload
        if not isinstance(payload, dict):
            return SpecialistResult(request.request_id, "invalid_request",
                                    warnings=("payload must be an object",))
        session_id = payload.get("session_id")
        messages = payload.get("messages")
        if not isinstance(session_id, str) or not session_id.strip():
            return SpecialistResult(request.request_id, "invalid_request",
                                    warnings=("session_id is required",))
        if not isinstance(messages, list) or not messages or any(
            not isinstance(item, dict)
            or set(item) != {"role", "content"}
            or item["role"] not in {"system", "user", "assistant"}
            or not isinstance(item["content"], str)
            for item in messages
        ):
            return SpecialistResult(request.request_id, "invalid_request",
                                    warnings=("messages must be a non-empty list of role/content objects",))
        try:
            answer = self._reply(session_id, messages)
        except Exception:
            return SpecialistResult(request.request_id, "failed",
                                    warnings=("chat engine invocation failed",))
        if not isinstance(answer, str):
            return SpecialistResult(request.request_id, "invalid_response",
                                    warnings=("chat engine must return text",))
        return SpecialistResult(request.request_id, "ok", output={"reply": answer})

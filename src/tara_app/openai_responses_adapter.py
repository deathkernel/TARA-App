"""Explicitly enabled OpenAI Responses API adapter using the optional official SDK.

No SDK import, client construction, or network request occurs at module import time.
Hosted inference can incur charges; callers must opt in explicitly.
"""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any

class OpenAISDKUnavailable(RuntimeError):
    """Raised when the optional SDK is not installed or configuration is missing."""

class OpenAIResponsesAdapter:
    def __init__(self, *, enabled: bool = False, client: Any | None = None) -> None:
        if type(enabled) is not bool:
            raise ValueError("enabled must be boolean")
        self._enabled = enabled
        self._client = client

    def _get_client(self) -> Any:
        if not self._enabled:
            raise OpenAISDKUnavailable("hosted OpenAI inference is disabled; explicitly enable it first")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise OpenAISDKUnavailable("install TARA-App with the optional 'openai' extra") from None
            # Official SDK reads OPENAI_API_KEY from the environment. Never log or persist it here.
            self._client = OpenAI()
        return self._client

    def complete(self, *, model: str, input_text: str, max_output_tokens: int = 1024) -> str:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be non-empty")
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("input_text must be non-empty")
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 16384:
            raise ValueError("max_output_tokens must be between 1 and 16384")
        client = self._get_client()
        response = client.responses.create(
            model=model,
            input=input_text,
            max_output_tokens=max_output_tokens,
        )
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str):
            raise OpenAISDKUnavailable("OpenAI returned an unexpected response shape")
        return output_text

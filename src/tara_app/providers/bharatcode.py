"""Server-side BharatCode OpenAI-compatible chat-completions provider.

The API key is read only from BHARATCODE_API_KEY. Requests are sent to the
fixed HTTPS BharatCode origin, never through browser code or a caller URL.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

BASE_URL = "https://bharatcode.ai/api/model/v1"
DEFAULT_MODEL = "qwen-3.8-27b"
MAX_REQUEST_BYTES = 1_000_000
MAX_RESPONSE_BYTES = 8_000_000
MAX_OUTPUT_TOKENS = 32_000


class BharatCodeError(RuntimeError):
    """A safe, provider-neutral BharatCode failure."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def _api_key() -> str:
    key = os.environ.get("BHARATCODE_API_KEY", "").strip()
    if not key or len(key) > 512 or any(ord(char) < 32 for char in key):
        raise BharatCodeError("BharatCode is not configured. Set BHARATCODE_API_KEY in the local environment.")
    return key


def _request(path: str, *, method: str = "GET", payload: Mapping[str, Any] | None = None, timeout: float = 120) -> dict[str, Any]:
    if path not in {"/models", "/chat/completions"}:
        raise ValueError("unsupported BharatCode endpoint")
    body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if body is not None and len(body) > MAX_REQUEST_BYTES:
        raise ValueError("BharatCode request exceeds the 1 MB limit")
    request = Request(
        BASE_URL + path,
        data=body,
        headers={"Authorization": "Bearer " + _api_key(), "Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        # Never include provider response bodies: they may echo submitted data.
        if exc.code == 429:
            raise BharatCodeError("BharatCode is rate-limiting this request or its shared queue is busy.") from None
        if exc.code in {401, 403}:
            raise BharatCodeError("BharatCode rejected the API key or account access.") from None
        if exc.code == 503:
            raise BharatCodeError("BharatCode model capacity is busy; try again later.") from None
        raise BharatCodeError(f"BharatCode request failed with HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise BharatCodeError("BharatCode could not be reached. Check the network and provider status.") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise BharatCodeError("BharatCode response exceeded the 8 MB safety limit.")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BharatCodeError("BharatCode returned malformed JSON.") from None
    if not isinstance(result, dict):
        raise BharatCodeError("BharatCode returned an unexpected response.")
    return result


class BharatCodeProvider:
    """TARA-compatible remote provider using BharatCode Chat Completions."""

    def __init__(self, *, model: str = DEFAULT_MODEL, timeout: float = 180.0) -> None:
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise ValueError("BharatCode model ID must be non-empty bounded text")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(float(timeout)) or not 1 <= float(timeout) <= 600:
            raise ValueError("BharatCode timeout must be between 1 and 600 seconds")
        self.model = model.strip()
        self.timeout = float(timeout)
        self.remote = True
        self.power_mode = "remote"
        self.num_ctx = "provider-managed"
        self.num_thread = "provider-managed"
        self.num_batch = "provider-managed"
        self.default_max_tokens = 2048

    @classmethod
    def from_env(cls, *, prefix: str = "BHARATCODE") -> "BharatCodeProvider":
        model = os.environ.get(prefix + "_MODEL", DEFAULT_MODEL).strip()
        raw_timeout = os.environ.get("TARA_LLM_TIMEOUT_SECONDS", "180").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError:
            raise ValueError("TARA_LLM_TIMEOUT_SECONDS must be a number") from None
        return cls(model=model, timeout=timeout)

    def list_models(self) -> list[dict[str, Any]]:
        result = _request("/models", timeout=min(self.timeout, 30))
        models = result.get("data", result.get("models", []))
        if not isinstance(models, list):
            raise BharatCodeError("BharatCode model catalogue has an unexpected shape.")
        return [item for item in models if isinstance(item, dict) and isinstance(item.get("id"), str)]

    def chat(self, messages: Sequence[Mapping[str, Any]], *, max_tokens: int = 4096, temperature: float = 0.2) -> str:
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)) or not messages or len(messages) > 32:
            raise ValueError("messages must contain between 1 and 32 message objects")
        normalized: list[dict[str, Any]] = []
        for item in messages:
            if not isinstance(item, Mapping) or item.get("role") not in {"system", "user", "assistant", "tool"}:
                raise ValueError("message role or shape is invalid")
            content = item.get("content")
            if not isinstance(content, (str, list)):
                raise ValueError("message content must be text or supported multimodal content")
            normalized.append({"role": item["role"], "content": content})
        if type(max_tokens) is not int or not 1 <= max_tokens <= MAX_OUTPUT_TOKENS:
            raise ValueError(f"max_tokens must be between 1 and {MAX_OUTPUT_TOKENS}")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(float(temperature)) or not 0 <= float(temperature) <= 2:
            raise ValueError("temperature must be between 0 and 2")
        result = _request(
            "/chat/completions",
            method="POST",
            payload={"model": self.model, "messages": normalized, "max_tokens": max_tokens, "temperature": float(temperature), "stream": False},
            timeout=self.timeout,
        )
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise BharatCodeError("BharatCode returned no completion.")
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise BharatCodeError("BharatCode response was truncated by its output limit; it is not a complete answer or tool call.")
        message = choice.get("message")
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise BharatCodeError("BharatCode returned an empty or unsupported response.")
        return text.strip()

    def complete(self, prompt: str, *, system: str | None = None, max_completion_tokens: int | None = None, temperature: float = 0.6) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty")
        messages: list[dict[str, str]] = []
        if isinstance(system, str) and system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, max_tokens=max_completion_tokens or self.default_max_tokens, temperature=temperature)


__all__ = ["BharatCodeError", "BharatCodeProvider", "DEFAULT_MODEL"]

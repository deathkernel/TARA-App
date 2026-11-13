"""OpenAI-compatible OmniRoute provider for TARA-Chat.

OmniRoute owns underlying model selection. TARA sends the configured auto-route
alias and retains conversation, memory, permissions, and tool execution locally.
"""
from __future__ import annotations

import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from typing import Any

from tara_app.http import NoRedirectHandler
from tara_app.omniroute_health import diagnose_gateway

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_COMPLETION_TOKENS = 4096


def _request_json(url: str, payload: dict[str, Any], api_key: str, timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with build_opener(ProxyHandler({}), NoRedirectHandler()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("OmniRoute response exceeded the 8 MiB safety limit")
        result = json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"OmniRoute returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("Could not reach the configured OmniRoute endpoint") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("OmniRoute returned malformed JSON") from None
    if not isinstance(result, dict):
        raise RuntimeError("OmniRoute returned an invalid response")
    return result


class OmniRouteProvider:
    """TARA provider that delegates model selection to OmniRoute Auto Router."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "http://127.0.0.1:20128/v1",
        model: str = "auto",
        timeout: float = 180.0,
        transport=None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip() or len(api_key) > 4096 or any(ord(char) < 33 or ord(char) == 127 for char in api_key):
            raise ValueError("TARA_OMNIROUTE_API_KEY must be a non-empty bounded value")
        if not isinstance(base_url, str) or not base_url.strip() or len(base_url) > 2048:
            raise ValueError("TARA_OMNIROUTE_BASE_URL must be a non-empty bounded URL")
        parsed = urlsplit(base_url.strip())
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("TARA_OMNIROUTE_BASE_URL is invalid") from None
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
            or parsed.path.rstrip("/") != "/v1"
        ):
            raise ValueError("TARA_OMNIROUTE_BASE_URL must target the local OmniRoute HTTP /v1 endpoint")
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or any(c.isspace() or ord(c) < 33 for c in model):
            raise ValueError("TARA_OMNIROUTE_MODEL must be a bounded model/route identifier")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(float(timeout)) or not 1 <= float(timeout) <= 3600:
            raise ValueError("TARA_OMNIROUTE_TIMEOUT_SECONDS must be between 1 and 3600")
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.model = model.strip()
        self.timeout = float(timeout)
        self._transport = transport or _request_json
        self.last_usage: dict[str, int] | None = None

    @classmethod
    def from_env(cls) -> "OmniRouteProvider":
        raw_timeout = os.getenv("TARA_OMNIROUTE_TIMEOUT_SECONDS", "180").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError:
            raise ValueError("TARA_OMNIROUTE_TIMEOUT_SECONDS must be numeric") from None
        return cls(
            api_key=os.getenv("TARA_OMNIROUTE_API_KEY", ""),
            base_url=os.getenv("TARA_OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1"),
            model=os.getenv("TARA_OMNIROUTE_MODEL", "auto"),
            timeout=timeout,
        )

    def health_diagnostic(self) -> str | None:
        return diagnose_gateway(self.base_url, self.api_key, timeout=min(self.timeout, 5.0))

    def health(self) -> bool:
        return self.health_diagnostic() is None

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_completion_tokens: int = 512,
        temperature: float = 0.6,
    ) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if system is not None and not isinstance(system, str):
            raise ValueError("system must be a string or None")
        if type(max_completion_tokens) is not int or not 1 <= max_completion_tokens <= MAX_COMPLETION_TOKENS:
            raise ValueError(f"max_completion_tokens must be between 1 and {MAX_COMPLETION_TOKENS}")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(float(temperature)) or not 0 <= float(temperature) <= 2:
            raise ValueError("temperature must be finite and between 0 and 2")

        messages = []
        if system and system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt.strip()})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "max_tokens": max_completion_tokens,
            "temperature": float(temperature),
        }
        self.last_usage = None
        result = self._transport(
            f"{self.base_url}/chat/completions", payload, self.api_key, self.timeout
        )
        usage = result.get("usage")
        if isinstance(usage, dict):
            normalized = {}
            for source, target in (
                ("prompt_tokens", "prompt_tokens"),
                ("completion_tokens", "completion_tokens"),
                ("total_tokens", "total_tokens"),
            ):
                value = usage.get(source)
                if type(value) is int and value >= 0:
                    normalized[target] = value
            self.last_usage = normalized or None

        choices = result.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise RuntimeError("OmniRoute response did not contain a chat completion")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str) or not message["content"].strip():
            raise RuntimeError("OmniRoute returned an empty or unsupported chat response")
        return message["content"].strip()


__all__ = ["OmniRouteProvider"]

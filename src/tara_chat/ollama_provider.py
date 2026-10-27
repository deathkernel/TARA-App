"""Local Llama inference through Ollama with resource-aware power profiles.

TARA keeps memory, planning, tools, and verification. Ollama serves a pretrained
local language model; this adapter does not train or fine-tune it.
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


JsonTransport = Callable[[str, dict[str, Any], float], dict[str, Any]]

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_COMPLETION_TOKENS = 4096
MAX_CONTEXT_TOKENS = 32768
MAX_CPU_THREADS = 256
MAX_BATCH_SIZE = 2048


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not let a configured Ollama endpoint redirect requests elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

# Eco is the safe default for everyday desktop use. Thread count limits CPU
# parallelism; context/batch limits reduce peak memory and prompt-processing work.
_POWER_PROFILES = {
    "eco": {"num_ctx": 2048, "num_thread": 4, "num_batch": 64, "keep_alive": "2m", "max_tokens": 128},
    "balanced": {"num_ctx": 4096, "num_thread": 0, "num_batch": 128, "keep_alive": "5m", "max_tokens": 256},
    "performance": {"num_ctx": 8192, "num_thread": 0, "num_batch": 256, "keep_alive": "10m", "max_tokens": 512},
}


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _http_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Ollama response exceeded the 8 MiB safety limit")
        data = json.loads(body.decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach the local Ollama server at {url}: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ollama returned malformed JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Ollama returned an invalid JSON response")
    return data


class OllamaProvider:
    """TARA-compatible local LLM provider backed by an Ollama server."""

    def __init__(
        self,
        *,
        model: str = "llama3.2:3b",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
        power_mode: str = "eco",
        num_ctx: int | None = None,
        num_thread: int | None = None,
        num_batch: int | None = None,
        keep_alive: str | None = None,
        transport: JsonTransport | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty URL")
        try:
            parsed_url = urlsplit(base_url.strip())
            parsed_port = parsed_url.port
        except ValueError as exc:
            raise ValueError("base_url must be a valid HTTP(S) URL") from exc
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.path not in {"", "/"}
            or (parsed_port is not None and not 1 <= parsed_port <= 65535)
        ):
            raise ValueError("base_url must be an HTTP(S) origin without credentials, path, query, or fragment")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("timeout must be finite and between 0 and 3600 seconds")
        try:
            timeout_value = float(timeout)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("timeout must be finite and between 0 and 3600 seconds") from exc
        if not math.isfinite(timeout_value) or not 0 < timeout_value <= 3600:
            raise ValueError("timeout must be finite and between 0 and 3600 seconds")
        if not isinstance(power_mode, str):
            raise ValueError("TARA_POWER_MODE must be eco, balanced, or performance")
        normalized_mode = power_mode.strip().lower()
        if normalized_mode not in _POWER_PROFILES:
            raise ValueError(f"Unsupported TARA_POWER_MODE {power_mode!r}; use eco, balanced, or performance")
        profile = _POWER_PROFILES[normalized_mode]
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_value
        self.power_mode = normalized_mode
        self.num_ctx = profile["num_ctx"] if num_ctx is None else num_ctx
        self.num_thread = profile["num_thread"] if num_thread is None else num_thread
        self.num_batch = profile["num_batch"] if num_batch is None else num_batch
        if type(self.num_ctx) is not int or not 1 <= self.num_ctx <= MAX_CONTEXT_TOKENS:
            raise ValueError(f"num_ctx must be an integer between 1 and {MAX_CONTEXT_TOKENS}")
        if type(self.num_thread) is not int or not 0 <= self.num_thread <= MAX_CPU_THREADS:
            raise ValueError(f"num_thread must be an integer between 0 (auto) and {MAX_CPU_THREADS}")
        if type(self.num_batch) is not int or not 1 <= self.num_batch <= MAX_BATCH_SIZE:
            raise ValueError(f"num_batch must be an integer between 1 and {MAX_BATCH_SIZE}")
        if keep_alive is not None and not isinstance(keep_alive, str):
            raise ValueError("keep_alive must be a non-empty string")
        self.keep_alive = profile["keep_alive"] if keep_alive is None else keep_alive
        if not self.keep_alive.strip():
            raise ValueError("keep_alive must be a non-empty string")
        self._profile_max_tokens = profile["max_tokens"]
        self._transport = transport or _http_json

    @classmethod
    def from_env(cls) -> "OllamaProvider":
        """Build a provider from TARA/Ollama environment settings."""
        raw_timeout = os.getenv("TARA_LLM_TIMEOUT_SECONDS", "120").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ValueError("TARA_LLM_TIMEOUT_SECONDS must be a number") from exc
        mode = os.getenv("TARA_POWER_MODE", "eco").strip().lower()
        if mode not in _POWER_PROFILES:
            raise ValueError("TARA_POWER_MODE must be eco, balanced, or performance")
        profile = _POWER_PROFILES[mode]
        cpu_count = os.cpu_count() or 4
        eco_threads = min(4, max(1, cpu_count))
        return cls(
            model=os.getenv("TARA_LLAMA_MODEL", "llama3.2:3b").strip(),
            base_url=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip(),
            timeout=timeout,
            power_mode=mode,
            num_ctx=_positive_int_env("TARA_OLLAMA_NUM_CTX", profile["num_ctx"]),
            num_thread=int(os.getenv("TARA_OLLAMA_NUM_THREADS", str(eco_threads if mode == "eco" else profile["num_thread"]))),
            num_batch=_positive_int_env("TARA_OLLAMA_NUM_BATCH", profile["num_batch"]),
            keep_alive=os.getenv("TARA_OLLAMA_KEEP_ALIVE", profile["keep_alive"]).strip(),
        )

    @property
    def default_max_tokens(self) -> int:
        """Recommended output cap for the selected resource profile."""
        return self._profile_max_tokens

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_completion_tokens: int | None = None,
        temperature: float = 0.6,
    ) -> str:
        """Generate one local response using the configured resource profile."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if system is not None and not isinstance(system, str):
            raise ValueError("system must be a string or None")
        if max_completion_tokens is None:
            max_completion_tokens = self.default_max_tokens
        if type(max_completion_tokens) is not int or not 1 <= max_completion_tokens <= MAX_COMPLETION_TOKENS:
            raise ValueError(f"max_completion_tokens must be an integer between 1 and {MAX_COMPLETION_TOKENS}")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise ValueError("temperature must be finite and between 0 and 2")
        try:
            temperature_value = float(temperature)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("temperature must be finite and between 0 and 2") from exc
        if not math.isfinite(temperature_value) or not 0.0 <= temperature_value <= 2.0:
            raise ValueError("temperature must be finite and between 0 and 2")

        messages: list[dict[str, str]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature_value,
                "num_predict": max_completion_tokens,
                "num_ctx": self.num_ctx,
                "num_thread": self.num_thread,
                "num_batch": self.num_batch,
            },
        }
        result = self._transport(f"{self.base_url}/api/chat", payload, self.timeout)
        if not isinstance(result, dict):
            raise RuntimeError("Ollama returned an invalid JSON response")
        if result.get("error"):
            raise RuntimeError(f"Ollama error: {result['error']}")
        message = result.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("Ollama response did not contain message.content")
        return message["content"]


__all__ = ["OllamaProvider"]

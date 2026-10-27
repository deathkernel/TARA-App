"""Loopback-only Ollama adapter. It never installs or launches a runtime."""
from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from typing import Any


class ProviderError(RuntimeError):
    """Safe, normalized local-provider error."""


@dataclass(frozen=True)
class OllamaModel:
    name: str
    size: int | None = None
    digest: str | None = None
    modified_at: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization_level: str | None = None
    model_format: str | None = None


class OllamaProvider:
    """Talk to Ollama on 127.0.0.1 only; no remote endpoint configuration."""

    def __init__(self, port: int = 11434, timeout_seconds: float = 10.0) -> None:
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port must be an integer between 1 and 65535")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be numeric")
        if not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        self._port = port
        self._timeout = float(timeout_seconds)

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=self._timeout)
        body = None if payload is None else json.dumps(payload)
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            connection.request("GET" if body is None else "POST", path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(2 * 1024 * 1024 + 1)
            if response.status < 200 or response.status >= 300:
                raise ProviderError(f"Ollama returned HTTP {response.status}")
            if len(raw) > 2 * 1024 * 1024:
                raise ProviderError("Ollama response exceeded the 2 MiB limit")
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise ProviderError("Ollama returned an unexpected response shape")
            return result
        except ProviderError:
            raise
        except (OSError, TimeoutError, http.client.HTTPException, json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("Ollama is unavailable or returned invalid JSON") from None
        finally:
            connection.close()

    def health(self) -> bool:
        try:
            self._request("/api/tags")
            return True
        except ProviderError:
            return False

    def list_models(self) -> list[OllamaModel]:
        records = self._request("/api/tags").get("models")
        if not isinstance(records, list):
            raise ProviderError("Ollama model catalogue has an unexpected shape")
        models = []
        for item in records:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            size = item.get("size")
            details = item.get("details")
            if not isinstance(details, dict):
                details = {}
            models.append(OllamaModel(
                name=item["name"],
                size=size if isinstance(size, int) and not isinstance(size, bool) else None,
                digest=item.get("digest") if isinstance(item.get("digest"), str) else None,
                modified_at=item.get("modified_at") if isinstance(item.get("modified_at"), str) else None,
                family=details.get("family") if isinstance(details.get("family"), str) else None,
                parameter_size=details.get("parameter_size") if isinstance(details.get("parameter_size"), str) else None,
                quantization_level=details.get("quantization_level") if isinstance(details.get("quantization_level"), str) else None,
                model_format=details.get("format") if isinstance(details.get("format"), str) else None,
            ))
        return models

    def chat(self, model: str, messages: list[dict[str, str]]) -> str:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list")
        if any(
            not isinstance(message, dict)
            or not isinstance(message.get("role"), str)
            or not isinstance(message.get("content"), str)
            for message in messages
        ):
            raise ValueError("messages must contain role/content string pairs")
        response = self._request("/api/chat", {"model": model, "messages": messages, "stream": False})
        message = response.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError("Ollama chat response has an unexpected shape")
        return message["content"]

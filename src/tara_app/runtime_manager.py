"""Small fail-closed provider registry/runtime manager.

The manager never installs or launches provider processes. A provider must be
explicitly enabled in a local JSON config before it can be queried.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Any

from tara_app.config import SettingsError, load_runtime_settings
from tara_app.contracts import ModelInfo, ModelProvider, ProviderStatus
from tara_app.providers.ollama import OllamaProvider, ProviderError


class RuntimeConfigurationError(RuntimeError):
    """Raised when local runtime configuration is invalid."""


class RuntimeManager:
    def __init__(
        self,
        registry_path: Path,
        settings_path: Path,
        *,
        provider_factory: Callable[..., ModelProvider] = OllamaProvider,
    ) -> None:
        self._registry_path = Path(registry_path)
        self._settings_path = Path(settings_path)
        self._provider_factory = provider_factory
        self._registry = self._read_json(self._registry_path, "tool registry")
        try:
            self._settings = load_runtime_settings(self._settings_path)
        except SettingsError as exc:
            raise RuntimeConfigurationError(str(exc)) from None
        self._providers: dict[str, ModelProvider] = {}
        self._configure_providers()

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise RuntimeConfigurationError(f"{label} file does not exist: {path}") from None
        except json.JSONDecodeError:
            raise RuntimeConfigurationError(f"{label} contains invalid JSON") from None
        except OSError:
            raise RuntimeConfigurationError(f"{label} could not be read") from None
        if not isinstance(data, dict):
            raise RuntimeConfigurationError(f"{label} must be a JSON object")
        return data

    def _configure_providers(self) -> None:
        if type(self._registry.get("schema_version")) is not int or self._registry.get("schema_version") != 1:
            raise RuntimeConfigurationError("unsupported tool registry schema_version")

        entries = self._registry.get("tools")
        if not isinstance(entries, list):
            raise RuntimeConfigurationError("tool registry must contain a tools array")
        by_id: dict[str, dict[str, Any]] = {}
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise RuntimeConfigurationError(f"tool registry entry {index} must be an object")
            tool_id = entry.get("id")
            if not isinstance(tool_id, str) or not tool_id.strip():
                raise RuntimeConfigurationError(f"tool registry entry {index} must have a non-empty id")
            if tool_id in by_id:
                raise RuntimeConfigurationError(f"duplicate provider/tool id {tool_id!r} in registry")
            by_id[tool_id] = entry

        for provider_id, options in self._settings.providers.items():
            if not options.enabled:
                continue
            registry_entry = by_id.get(provider_id)
            if not isinstance(registry_entry, dict):
                raise RuntimeConfigurationError(f"provider {provider_id!r} is not present in the registry")
            if registry_entry.get("adapter") != "ollama_http":
                raise RuntimeConfigurationError(f"provider {provider_id!r} has no implemented adapter")
            if registry_entry.get("network_scope") != "loopback_only":
                raise RuntimeConfigurationError("Ollama provider must be restricted to loopback")
            try:
                self._providers[provider_id] = self._provider_factory(
                    port=options.port,
                    timeout_seconds=options.timeout_seconds,
                )
            except (TypeError, ValueError) as exc:
                raise RuntimeConfigurationError(f"invalid settings for provider {provider_id!r}: {exc}") from None

    @property
    def configured_provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def refresh_provider_status(self, provider_id: str) -> ProviderStatus:
        """Probe an explicitly configured provider now; no process is started."""
        provider = self._providers.get(provider_id)
        if provider is None:
            return ProviderStatus(provider_id, False, False, "Provider is not explicitly enabled")
        try:
            healthy = provider.health()
        except Exception:
            # Adapters are a trust boundary; do not leak implementation exceptions.
            healthy = False
        return ProviderStatus(
            provider_id, True, healthy,
            "Local provider is healthy" if healthy else "Local provider is unavailable",
        )

    def provider_status(self, provider_id: str) -> ProviderStatus:
        """Return a fresh health status (compatibility alias)."""
        return self.refresh_provider_status(provider_id)

    def list_models(self, provider_id: str = "ollama") -> list[ModelInfo]:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise RuntimeConfigurationError(f"provider {provider_id!r} is not enabled in local settings")
        try:
            models = provider.list_models()
        except ProviderError:
            raise RuntimeConfigurationError(f"provider {provider_id!r} failed to list models") from None
        normalized = []
        for model in models:
            size = getattr(model, "size", None)
            normalized.append(ModelInfo(
                provider_id=provider_id,
                name=model.name,
                size_bytes=size if isinstance(size, int) and not isinstance(size, bool) else None,
                digest=getattr(model, "digest", None),
                modified_at=getattr(model, "modified_at", None),
                family=getattr(model, "family", None),
                parameter_size=getattr(model, "parameter_size", None),
                quantization_level=getattr(model, "quantization_level", None),
                model_format=getattr(model, "model_format", None),
            ))
        return normalized

    def chat(self, model: str, messages: list[dict[str, str]], provider_id: str = "ollama") -> str:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise RuntimeConfigurationError(f"provider {provider_id!r} is not enabled in local settings")
        try:
            return provider.chat(model, messages)
        except ProviderError:
            raise RuntimeConfigurationError(f"provider {provider_id!r} request failed") from None

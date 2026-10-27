"""Validated, fail-closed application runtime settings."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SettingsError(RuntimeError):
    """Raised when runtime settings are missing or unsafe."""


@dataclass(frozen=True)
class ProviderSettings:
    enabled: bool = False
    port: int = 11434
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class RuntimeSettings:
    schema_version: int
    providers: dict[str, ProviderSettings]


def load_runtime_settings(path: Path) -> RuntimeSettings:
    """Load and validate JSON settings without enabling unspecified providers."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SettingsError(f"runtime settings file does not exist: {path}") from None
    except json.JSONDecodeError:
        raise SettingsError("runtime settings contains invalid JSON") from None
    except OSError:
        raise SettingsError("runtime settings could not be read") from None

    if not isinstance(raw, dict):
        raise SettingsError("runtime settings must be a JSON object")
    version = raw.get("schema_version")
    if type(version) is not int or version != 1:
        raise SettingsError("unsupported runtime settings schema_version")
    provider_map = raw.get("providers")
    if not isinstance(provider_map, dict):
        raise SettingsError("runtime settings must contain a providers object")

    providers: dict[str, ProviderSettings] = {}
    for provider_id, options in provider_map.items():
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise SettingsError("provider IDs must be non-empty strings")
        if not isinstance(options, dict):
            raise SettingsError(f"provider settings for {provider_id!r} must be an object")
        enabled = options.get("enabled", False)
        if not isinstance(enabled, bool):
            raise SettingsError(f"provider {provider_id!r} enabled must be boolean")
        port: Any = options.get("port", 11434)
        timeout: Any = options.get("timeout_seconds", 10)
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise SettingsError(f"provider {provider_id!r} port must be an integer between 1 and 65535")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
            raise SettingsError(f"provider {provider_id!r} timeout_seconds must be between 1 and 120")
        providers[provider_id] = ProviderSettings(enabled, port, float(timeout))

    return RuntimeSettings(schema_version=version, providers=providers)

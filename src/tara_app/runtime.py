"""Load a trusted local runtime configuration and register TARA modules."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Mapping

from tara_app.contracts import Capability
from tara_app.handler_adapter import HandlerProcessAdapter
from tara_app.module_client import StdioModuleAdapter
from tara_app.orchestrator import Orchestrator
from tara_app.registry import CapabilityRegistry
from tara_app.router_client import StdioRouterClient

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_POLICIES: dict[str, tuple[Capability, ...]] = {
    "chat": (Capability("chat", "respond", "Conversation and bounded session context", True),),
    "code": (Capability("code", "plan", "Non-executing code task planning", True),),
    "security": (Capability("security", "assess", "Assess a requested capability against policy", True),),
    "planner": (Capability("planner", "plan", "Create a non-executing task plan", True),),
    "research": (Capability("research", "answer", "Search configured external sources", True),),
    "memory": (
        Capability("memory", "search", "Search explicitly stored local memory", True),
        Capability("memory", "store", "Store information after explicit approval", False, True),
        Capability("memory", "forget", "Forget information after explicit approval", False, True),
    ),
    "vision": (Capability("vision", "analyze", "Analyze user supplied images using local inference", True),),
    "data": (Capability("data", "analyze", "Analyze bounded tabular input", True),),
    "creative": (Capability("creative", "write", "Generate writing using local inference", True),),
    "voice": (
        Capability("voice", "transcribe", "Transcribe user supplied audio", True),
        Capability("voice", "speak", "Synthesize speech from text", True),
    ),
    "handler": (Capability("handler", "diagnose", "Inspect the local developer environment", True),),
}
_REMOTE_MODULES = frozenset({"research", "voice"})


class RuntimeConfigurationError(ValueError):
    """Raised when a local TARA-App configuration is incomplete or unsafe."""


def create_application(config_path: str | Path) -> Orchestrator:
    """Create the router and configured specialists from a TOML file.

    The TOML file is trusted application configuration. Request data cannot
    change process arguments, process environment, or working directories.
    """
    config_file = Path(config_path).expanduser().resolve(strict=True)
    if not config_file.is_file():
        raise RuntimeConfigurationError("configuration path must be a file")
    try:
        with config_file.open("rb") as stream:
            config = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeConfigurationError("configuration file could not be read") from exc
    if set(config) - {"router", "modules"}:
        raise RuntimeConfigurationError("configuration contains unsupported top-level settings")

    root = config_file.parent
    router_config = _table(config.get("router"), "router")
    if set(router_config) - {"command", "working_directory", "timeout_seconds", "max_response_bytes"}:
        raise RuntimeConfigurationError("router contains unsupported settings")
    router = StdioRouterClient(
        _command(router_config.get("command")),
        working_directory=_directory(root, router_config.get("working_directory")),
        timeout_seconds=_integer(router_config.get("timeout_seconds", 10), "router.timeout_seconds", 1, 60),
        max_response_bytes=_integer(router_config.get("max_response_bytes", 64_000), "router.max_response_bytes", 256, 1_000_000),
    )

    modules = config.get("modules", [])
    if not isinstance(modules, list) or len(modules) > len(_POLICIES):
        raise RuntimeConfigurationError("modules must be a bounded list")
    registry = CapabilityRegistry()
    seen: set[str] = set()
    for index, raw in enumerate(modules):
        item = _table(raw, f"modules[{index}]")
        if set(item) - {"id", "command", "working_directory", "environment", "allow_remote"}:
            raise RuntimeConfigurationError(f"modules[{index}] contains unsupported settings")
        module_id = item.get("id")
        if not isinstance(module_id, str) or module_id not in _POLICIES:
            raise RuntimeConfigurationError(f"modules[{index}].id is not a supported module")
        if module_id in seen:
            raise RuntimeConfigurationError(f"module is configured more than once: {module_id}")
        seen.add(module_id)
        if module_id in _REMOTE_MODULES and item.get("allow_remote") is not True:
            continue
        env_names = item.get("environment", [])
        if not isinstance(env_names, list) or any(not isinstance(name, str) or not _ENV_NAME.fullmatch(name) for name in env_names):
            raise RuntimeConfigurationError(f"modules[{index}].environment must contain environment variable names")
        module_environment = {name: os.environ[name] for name in env_names if name in os.environ}
        adapter_args = {
            "working_directory": _directory(root, item.get("working_directory")),
            "timeout_seconds": _integer(item.get("timeout_seconds", 30), f"modules[{index}].timeout_seconds", 1, 600),
            "environment": module_environment,
        }
        if module_id == "handler":
            adapter = HandlerProcessAdapter(
                _command(item.get("command")),
                max_response_bytes=_integer(item.get("max_response_bytes", 256_000), f"modules[{index}].max_response_bytes", 256, 1_000_000),
                **{key: value for key, value in adapter_args.items() if key != "timeout_seconds"},
                timeout_seconds=_integer(item.get("timeout_seconds", 30), f"modules[{index}].timeout_seconds", 1, 120),
            )
        else:
            adapter = StdioModuleAdapter(
                module_id,
                _POLICIES[module_id],
                _command(item.get("command")),
                max_response_bytes=_integer(item.get("max_response_bytes", 1_000_000), f"modules[{index}].max_response_bytes", 256, 1_000_000),
                **adapter_args,
            )
        registry.register(adapter)
    return Orchestrator(registry, router)


def _table(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeConfigurationError(f"{label} must be a TOML table")
    return value


def _command(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(part, str) or not part or "\x00" in part for part in value):
        raise RuntimeConfigurationError("command must be a non-empty array of argument strings")
    return tuple(sys.executable if part == "{python}" else part for part in value)


def _directory(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigurationError("working_directory must be a non-empty path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RuntimeConfigurationError("working_directory does not exist") from exc
    if not resolved.is_dir():
        raise RuntimeConfigurationError("working_directory must name a directory")
    return resolved


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise RuntimeConfigurationError(f"{label} is outside the allowed range")
    return value


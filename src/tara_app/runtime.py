"""Load a trusted local runtime configuration and register TARA modules."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from tara_app.contracts import Capability
from tara_app.handler_adapter import HandlerProcessAdapter
from tara_app.module_client import StdioModuleAdapter
from tara_app.orchestrator import Orchestrator
from tara_app.registry import CapabilityRegistry
from tara_app.router_client import StdioRouterClient

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_POLICIES: dict[str, tuple[Capability, ...]] = {
    "chat": (Capability("chat", "respond", "Conversation and bounded session context", True), Capability("chat", "audit_repository", "Read-only static audit of the configured local repository", True)),
    "code": (Capability("code", "plan", "Non-executing code task planning", True),),
    "security": (Capability("security", "assess", "Assess a requested capability against policy", True),),
    "planner": (Capability("planner", "plan", "Create a non-executing task plan", True),),
    "research": (Capability("research", "answer", "Search configured external sources", True),),
    "memory": (
        Capability("memory", "search", "Search explicitly stored local memory", True),
        Capability("memory", "store", "Store information after explicit approval", False, True),
        Capability("memory", "forget", "Forget information after explicit approval", False, True),
    ),
    "vision": (Capability("vision", "analyze", "Analyze user supplied images through OmniRoute", True),),
    "data": (Capability("data", "analyze", "Analyze bounded tabular input", True),),
    "study": (Capability("study", "create", "Create source-grounded study notes, quizzes and flashcards or a bounded revision plan", True),),
    "weather": (Capability("weather", "forecast", "Fetch current conditions and short forecasts from public Open-Meteo endpoints", True),),
    "models": (
        Capability("models", "catalog", "Discover models exposed by the configured OmniRoute gateway", True),
        Capability("models", "generate", "Generate an answer through the configured OmniRoute gateway", True),
    ),
    "creative": (Capability("creative", "write", "Generate writing through OmniRoute", True),),
    "voice": (
        Capability("voice", "transcribe", "Transcribe user supplied audio", True),
        Capability("voice", "speak", "Synthesize speech from text", True),
    ),
    "action": (Capability("action", "execute", "Open allowlisted local apps or websites and create allowlisted GitHub issues after explicit approval", False, True),),
    "handler": (Capability("handler", "diagnose", "Inspect the local developer environment", True),),
}
_REMOTE_MODULES = frozenset({"research", "voice", "weather", "models", "chat", "code", "vision", "creative"})
_OMNIROUTE_MODULES = frozenset({"chat", "code", "vision", "creative", "models"})
_LEGACY_LOCAL_MODEL_ENV = frozenset({
    "TARA_LLAMA_MODEL", "OLLAMA_HOST", "TARA_CODE_OLLAMA_URL",
    "TARA_CREATIVE_OLLAMA_URL", "TARA_VISION_OLLAMA_URL",
    "TARA_POWER_MODE", "TARA_LLM_TIMEOUT_SECONDS", "TARA_OLLAMA_KEEP_ALIVE",
    "GEMINI_API_KEY",
})
_OLLAMA_DEFAULT_MODELS = {
    "chat": "llama3.2:3b",
    "creative": "llama3.2:3b",
    "vision": "gemma3:4b",
}
_OLLAMA_MODULE_ENV = {
    "chat": ("TARA_LLAMA_MODEL", "OLLAMA_HOST"),
    "creative": ("TARA_CREATIVE_MODEL", "TARA_CREATIVE_OLLAMA_URL"),
    "vision": ("TARA_VISION_MODEL", "TARA_VISION_OLLAMA_URL"),
}


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
    if set(config) - {"router", "modules", "ollama", "omniroute"}:
        raise RuntimeConfigurationError("configuration contains unsupported top-level settings")

    root = config_file.parent
    ollama_settings = _ollama_settings(config.get("ollama"))
    omniroute_settings = _omniroute_settings(config.get("omniroute"))
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
        if set(item) - {"id", "command", "working_directory", "environment", "allow_remote", "timeout_seconds", "max_response_bytes"}:
            raise RuntimeConfigurationError(f"modules[{index}] contains unsupported settings")
        module_id = item.get("id")
        if not isinstance(module_id, str) or module_id not in _POLICIES:
            raise RuntimeConfigurationError(f"modules[{index}].id is not a supported module")
        if module_id in seen:
            raise RuntimeConfigurationError(f"module is configured more than once: {module_id}")
        seen.add(module_id)
        if module_id in _REMOTE_MODULES and item.get("allow_remote") is not True:
            registry.mark_disabled(
                module_id,
                "Remote processing is disabled. Set allow_remote = true in this module's [[modules]] entry only if you approve sending its content through OmniRoute.",
            )
            continue
        env_names = item.get("environment", [])
        if not isinstance(env_names, list) or any(not isinstance(name, str) or not _ENV_NAME.fullmatch(name) for name in env_names):
            raise RuntimeConfigurationError(f"modules[{index}].environment must contain environment variable names")
        if module_id in _OMNIROUTE_MODULES:
            module_environment = dict(omniroute_settings.get(module_id, {}))
            module_environment.update({
                name: os.environ[name]
                for name in env_names
                if name in os.environ and name not in _LEGACY_LOCAL_MODEL_ENV
            })
            if module_id == "chat":
                module_environment["TARA_LLM_BACKEND"] = "omniroute"
        else:
            module_environment = dict(ollama_settings.get(module_id, {}))
            module_environment.update({name: os.environ[name] for name in env_names if name in os.environ})
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

    for module_id in sorted(_REMOTE_MODULES - seen):
        registry.mark_disabled(
            module_id,
            "The specialist is not configured in tara-app.toml. Add its [[modules]] entry from tara-app.example.toml.",
        )

    # TARA no longer starts or calls Ollama for language-model inference.
    # Model selection and lifecycle belong to OmniRoute.
    return Orchestrator(registry, router, model_catalog=None)


def _ollama_settings(value: Any) -> dict[str, dict[str, str]]:
    if value is None:
        return {}
    config = _table(value, "ollama")
    if set(config) - {"base_url", "models"}:
        raise RuntimeConfigurationError("ollama contains unsupported settings")
    base_url = config.get("base_url", "http://127.0.0.1:11434")
    if not isinstance(base_url, str) or not base_url.strip() or len(base_url) > 2048:
        raise RuntimeConfigurationError("ollama.base_url must be a bounded local URL")
    base_url = base_url.strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise RuntimeConfigurationError("ollama.base_url is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise RuntimeConfigurationError("ollama.base_url must target a local Ollama origin")

    models = _table(config.get("models", {}), "ollama.models")
    if set(models) - (set(_OLLAMA_DEFAULT_MODELS) | {"code"}):
        raise RuntimeConfigurationError("ollama.models contains an unsupported specialist")
    settings: dict[str, dict[str, str]] = {}
    for module_id, default_model in _OLLAMA_DEFAULT_MODELS.items():
        model = models.get(module_id, default_model)
        if (
            not isinstance(model, str)
            or not model.strip()
            or len(model) > 200
            or any(char.isspace() or ord(char) < 33 or ord(char) == 127 for char in model)
        ):
            raise RuntimeConfigurationError(f"ollama.models.{module_id} must be a bounded model identifier")
        model_env, url_env = _OLLAMA_MODULE_ENV[module_id]
        settings[module_id] = {model_env: model.strip(), url_env: base_url}
        if module_id == "chat":
            settings[module_id]["TARA_LLM_BACKEND"] = "ollama"
            settings[module_id]["TARA_POWER_MODE"] = "balanced"
            settings[module_id]["TARA_OLLAMA_KEEP_ALIVE"] = "15m"
    return settings


def _omniroute_settings(value: Any) -> dict[str, dict[str, str]]:
    """Validate the local OmniRoute gateway and build per-specialist settings."""
    config = {} if value is None else _table(value, "omniroute")
    if set(config) - {"base_url", "model", "models"}:
        raise RuntimeConfigurationError("omniroute contains unsupported settings")
    base_url = os.environ.get("TARA_OMNIROUTE_BASE_URL", config.get("base_url", "http://127.0.0.1:20128/v1"))
    if not isinstance(base_url, str) or not base_url.strip() or len(base_url) > 2048:
        raise RuntimeConfigurationError("omniroute.base_url must be a bounded local URL")
    base_url = base_url.strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        raise RuntimeConfigurationError("omniroute.base_url is invalid") from None
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username or parsed.password
        or parsed.path != "/v1"
        or parsed.query or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise RuntimeConfigurationError("omniroute.base_url must target the local OmniRoute /v1 endpoint")

    model_config = _table(config.get("models", {}), "omniroute.models")
    chat_default = config.get("model", "auto")
    if not isinstance(chat_default, str) or not chat_default.strip() or len(chat_default) > 200:
        raise RuntimeConfigurationError("omniroute.model must be a bounded route identifier")
    defaults = {
        "chat": ("TARA_OMNIROUTE_MODEL", chat_default),
        "code": ("TARA_CODE_MODEL", "auto/coding:cheap"),
        "vision": ("TARA_VISION_MODEL", "auto"),
        "creative": ("TARA_CREATIVE_MODEL", "auto/cheap"),
        "models": ("TARA_MODELS_MODEL", "auto"),
    }
    if set(model_config) - set(defaults):
        raise RuntimeConfigurationError("omniroute.models contains an unsupported specialist")
    api_key = os.environ.get("TARA_OMNIROUTE_API_KEY", "").strip()
    if len(api_key) > 4096 or any(ord(char) < 33 or ord(char) == 127 for char in api_key):
        raise RuntimeConfigurationError("TARA_OMNIROUTE_API_KEY is invalid")

    result: dict[str, dict[str, str]] = {}
    for module_id, (model_env, default_model) in defaults.items():
        model = os.environ.get(model_env, model_config.get(module_id, default_model))
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or any(char.isspace() or ord(char) < 32 for char in model):
            raise RuntimeConfigurationError(f"omniroute.models.{module_id} must be a bounded route identifier")
        common = {"TARA_OMNIROUTE_BASE_URL": base_url, "TARA_OMNIROUTE_API_KEY": api_key}
        if module_id == "chat":
            common.update({"TARA_OMNIROUTE_MODEL": model.strip(), "TARA_LLM_BACKEND": "omniroute"})
        elif module_id == "code":
            common.update({"TARA_CODE_API_BASE_URL": base_url, "TARA_CODE_API_KEY": api_key, "TARA_CODE_MODEL": model.strip()})
        elif module_id == "vision":
            common.update({"TARA_VISION_API_BASE_URL": base_url, "TARA_VISION_API_KEY": api_key, "TARA_VISION_MODEL": model.strip()})
        elif module_id == "creative":
            common.update({"TARA_CREATIVE_API_BASE_URL": base_url, "TARA_CREATIVE_API_KEY": api_key, "TARA_CREATIVE_MODEL": model.strip()})
        else:
            common.update({"TARA_MODELS_API_BASE_URL": base_url, "TARA_MODELS_API_KEY": api_key, "TARA_MODELS_MODEL": model.strip()})
        result[module_id] = common
    return result


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


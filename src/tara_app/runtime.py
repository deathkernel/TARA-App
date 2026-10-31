"""Load a trusted local runtime configuration and register TARA modules."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from threading import BoundedSemaphore
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from tara_app.contracts import Capability
from tara_app.handler_adapter import HandlerProcessAdapter
from tara_app.module_client import StdioModuleAdapter
from tara_app.ollama_models import OllamaModelCatalog
from tara_app.orchestrator import Orchestrator
from tara_app.registry import CapabilityRegistry
from tara_app.router_client import StdioRouterClient
from tara_app.sessions import SessionError, SessionStore

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
    "study": (Capability("study", "create", "Create source-grounded study notes, quizzes and flashcards or a bounded revision plan", True),),
    "weather": (Capability("weather", "forecast", "Fetch current conditions and short forecasts from public Open-Meteo endpoints", True),),
    "models": (
        Capability("models", "catalog", "Discover free-tier Gemini text models and installed local models", True),
        Capability("models", "generate", "Generate an answer with a selected free-tier Gemini model or installed local OpenAI gpt-oss model", True),
    ),
    "creative": (Capability("creative", "write", "Generate writing using local inference", True),),
    "voice": (
        Capability("voice", "transcribe", "Transcribe user supplied audio", True),
        Capability("voice", "speak", "Synthesize speech from text", True),
    ),
    "action": (Capability("action", "execute", "Open allowlisted local apps or websites and create allowlisted GitHub issues after explicit approval", False, True),),
    "handler": (Capability("handler", "diagnose", "Inspect the local developer environment", True),),
}
_REMOTE_MODULES = frozenset({"research", "voice", "weather", "models"})
_OLLAMA_DEFAULT_MODELS = {
    "chat": "llama3.2:3b",
    "code": "qwen2.5-coder:3b",
    "creative": "llama3.2:3b",
    "vision": "gemma3:4b",
}
_OLLAMA_MODULE_ENV = {
    "chat": ("TARA_LLAMA_MODEL", "OLLAMA_HOST"),
    "code": ("TARA_CODE_MODEL", "TARA_CODE_OLLAMA_URL"),
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
    if set(config) - {"router", "modules", "ollama", "sessions"}:
        raise RuntimeConfigurationError("configuration contains unsupported top-level settings")

    root = config_file.parent
    ollama_settings = _ollama_settings(config.get("ollama"))
    local_model_semaphore = BoundedSemaphore(_ollama_max_concurrent(config.get("ollama"))) if ollama_settings else None
    session_store = _session_store(config.get("sessions"), root)
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
            continue
        env_names = item.get("environment", [])
        if not isinstance(env_names, list) or any(not isinstance(name, str) or not _ENV_NAME.fullmatch(name) for name in env_names):
            raise RuntimeConfigurationError(f"modules[{index}].environment must contain environment variable names")
        module_environment = {name: os.environ[name] for name in env_names if name in os.environ}
        module_environment.update(ollama_settings.get(module_id, {}))
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
                execution_semaphore=local_model_semaphore if module_id in _OLLAMA_MODULE_ENV else None,
                **adapter_args,
            )
        registry.register(adapter)
    profiles: dict[str, str] = {}
    base_url: str | None = None
    for module_id, (model_env, url_env) in _OLLAMA_MODULE_ENV.items():
        module_settings = ollama_settings.get(module_id, {})
        model = module_settings.get(model_env)
        module_url = module_settings.get(url_env)
        if model and module_url:
            profiles[module_id] = model
            base_url = module_url
    model_catalog = OllamaModelCatalog(profiles, base_url) if profiles else OllamaModelCatalog()
    return Orchestrator(registry, router, model_catalog=model_catalog, session_store=session_store)


def _session_store(value: Any, root: Path) -> SessionStore | None:
    if value is None:
        return None
    config = _table(value, "sessions")
    allowed = {"database_path", "max_sessions", "max_messages_per_session", "max_content_chars"}
    if set(config) - allowed:
        raise RuntimeConfigurationError("sessions contains unsupported settings")
    database_path = config.get("database_path")
    if database_path is None:
        if config:
            raise RuntimeConfigurationError("sessions.database_path is required when session limits are configured")
        return None
    if not isinstance(database_path, str) or not database_path.strip() or len(database_path) > 4096:
        raise RuntimeConfigurationError("sessions.database_path must be a bounded file path")
    path = Path(database_path).expanduser()
    if not path.is_absolute():
        path = root / path
    try:
        path = path.resolve()
    except OSError as exc:
        raise RuntimeConfigurationError("sessions.database_path could not be resolved") from exc
    try:
        return SessionStore(
            database_path=path,
            max_sessions=_integer(config.get("max_sessions", 100), "sessions.max_sessions", 1, 512),
            max_messages_per_session=_integer(config.get("max_messages_per_session", 24), "sessions.max_messages_per_session", 2, 24),
            max_content_chars=_integer(config.get("max_content_chars", 20_000), "sessions.max_content_chars", 1, 20_000),
        )
    except SessionError as exc:
        raise RuntimeConfigurationError("persistent session storage could not be initialized") from exc


def _ollama_max_concurrent(value: Any) -> int:
    if value is None:
        return 1
    config = _table(value, "ollama")
    return _integer(config.get("max_concurrent_requests", 1), "ollama.max_concurrent_requests", 1, 2)


def _ollama_settings(value: Any) -> dict[str, dict[str, str]]:
    if value is None:
        return {}
    config = _table(value, "ollama")
    if set(config) - {"base_url", "models", "max_concurrent_requests"}:
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
    if set(models) - set(_OLLAMA_DEFAULT_MODELS):
        raise RuntimeConfigurationError("ollama.models contains an unsupported specialist")
    settings: dict[str, dict[str, str]] = {}
    for module_id, default_model in _OLLAMA_DEFAULT_MODELS.items():
        model = models.get(module_id, default_model)
        if (
            not isinstance(model, str)
            or not model.strip()
            or len(model) > 200
            or any(char.isspace() or ord(char) < 32 for char in model)
        ):
            raise RuntimeConfigurationError(f"ollama.models.{module_id} must be a bounded model identifier")
        model_env, url_env = _OLLAMA_MODULE_ENV[module_id]
        settings[module_id] = {model_env: model.strip(), url_env: base_url}
        if module_id == "chat":
            settings[module_id]["TARA_LLM_BACKEND"] = "ollama"
            settings[module_id]["TARA_POWER_MODE"] = "balanced"
            settings[module_id]["TARA_OLLAMA_KEEP_ALIVE"] = "15m"
    return settings


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


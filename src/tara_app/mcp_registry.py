"""Opt-in, allowlisted MCP server registry for TARA-App.

This module is the safety boundary for Model Context Protocol servers:

- MCP is **disabled by default**.
- Only **explicitly listed** stdio servers may be registered.
- Commands are fixed argv lists (no shell expansion).
- The optional ``mcp`` Python package is required only when MCP is enabled.
- Listing or calling tools against a live server is a later slice; this module
  validates configuration and describes what would be started.

Never treat model text as an MCP server command or as authorization to add one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_MAX_SERVERS = 16
_MAX_NAME_LEN = 64
_MAX_ARGV = 32
_MAX_ARG_LEN = 512
_MAX_TIMEOUT = 300.0
_MIN_TIMEOUT = 1.0

# Servers whose default upstream packages are known; still require explicit
# enablement and a fixed command in config. Names are documentation only.
KNOWN_REFERENCE_SERVERS = frozenset(
    {
        "filesystem",
        "git",
        "fetch",
        "memory",
        "time",
    }
)


class McpConfigError(ValueError):
    """Raised when MCP configuration is invalid or unsafe."""


@dataclass(frozen=True)
class McpServerSpec:
    """One allowlisted stdio MCP server."""

    name: str
    command: tuple[str, ...]
    working_directory: str | None
    timeout_seconds: float
    enabled: bool
    read_only: bool

    def argv(self) -> list[str]:
        return list(self.command)


@dataclass(frozen=True)
class McpRegistryConfig:
    """Top-level MCP settings. Disabled unless enable is true."""

    enable: bool
    servers: tuple[McpServerSpec, ...]

    @property
    def enabled_servers(self) -> tuple[McpServerSpec, ...]:
        if not self.enable:
            return ()
        return tuple(server for server in self.servers if server.enabled)


def default_mcp_config() -> McpRegistryConfig:
    """Safe default: MCP off, no servers."""
    return McpRegistryConfig(enable=False, servers=())


def parse_mcp_config(raw: Mapping[str, Any] | None) -> McpRegistryConfig:
    """Parse a ``[mcp]`` table from application config.

    Expected shape::

        [mcp]
        enable = false

        [[mcp.servers]]
        name = "time"
        command = ["uvx", "mcp-server-time"]
        enabled = true
        read_only = true
        timeout_seconds = 30
    """
    if raw is None:
        return default_mcp_config()
    if not isinstance(raw, Mapping):
        raise McpConfigError("mcp config must be a table")

    enable = raw.get("enable", False)
    if not isinstance(enable, bool):
        raise McpConfigError("mcp.enable must be a boolean")
    servers_raw = raw.get("servers", [])
    if servers_raw is None:
        servers_raw = []
    if not isinstance(servers_raw, Sequence) or isinstance(servers_raw, (str, bytes)):
        raise McpConfigError("mcp.servers must be a list")
    if len(servers_raw) > _MAX_SERVERS:
        raise McpConfigError(f"mcp.servers exceeds {_MAX_SERVERS} entries")

    servers: list[McpServerSpec] = []
    seen_names: set[str] = set()
    for index, item in enumerate(servers_raw):
        if not isinstance(item, Mapping):
            raise McpConfigError(f"mcp.servers[{index}] must be a table")
        spec = _parse_server(item, index)
        if spec.name in seen_names:
            raise McpConfigError(f"duplicate mcp server name: {spec.name}")
        seen_names.add(spec.name)
        servers.append(spec)

    return McpRegistryConfig(enable=enable, servers=tuple(servers))


def _parse_server(item: Mapping[str, Any], index: int) -> McpServerSpec:
    name = item.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > _MAX_NAME_LEN:
        raise McpConfigError(f"mcp.servers[{index}].name must be a non-empty bounded string")
    if any(ord(char) < 33 or ord(char) == 127 for char in name):
        raise McpConfigError(f"mcp.servers[{index}].name has invalid characters")
    cleaned_name = name.strip()

    command = item.get("command")
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
        raise McpConfigError(f"mcp.servers[{index}].command must be a list of strings")
    if not command or len(command) > _MAX_ARGV:
        raise McpConfigError(
            f"mcp.servers[{index}].command must have 1..{_MAX_ARGV} arguments"
        )
    argv: list[str] = []
    for arg_index, arg in enumerate(command):
        if not isinstance(arg, str) or not arg or len(arg) > _MAX_ARG_LEN:
            raise McpConfigError(
                f"mcp.servers[{index}].command[{arg_index}] must be a non-empty bounded string"
            )
        if "\x00" in arg:
            raise McpConfigError(f"mcp.servers[{index}].command must not contain NUL")
        argv.append(arg)

    working_directory = item.get("working_directory")
    if working_directory is not None:
        if not isinstance(working_directory, str) or not working_directory.strip():
            raise McpConfigError(
                f"mcp.servers[{index}].working_directory must be a non-empty string when set"
            )
        if len(working_directory) > _MAX_ARG_LEN:
            raise McpConfigError(f"mcp.servers[{index}].working_directory is too long")
        working_directory = working_directory.strip()

    timeout = item.get("timeout_seconds", 30)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise McpConfigError(f"mcp.servers[{index}].timeout_seconds must be a number")
    timeout_f = float(timeout)
    if not _MIN_TIMEOUT <= timeout_f <= _MAX_TIMEOUT:
        raise McpConfigError(
            f"mcp.servers[{index}].timeout_seconds must be between {_MIN_TIMEOUT} and {_MAX_TIMEOUT}"
        )

    enabled = item.get("enabled", True)
    read_only = item.get("read_only", True)
    if not isinstance(enabled, bool):
        raise McpConfigError(f"mcp.servers[{index}].enabled must be a boolean")
    if not isinstance(read_only, bool):
        raise McpConfigError(f"mcp.servers[{index}].read_only must be a boolean")

    return McpServerSpec(
        name=cleaned_name,
        command=tuple(argv),
        working_directory=working_directory,
        timeout_seconds=timeout_f,
        enabled=enabled,
        read_only=read_only,
    )


def mcp_package_available() -> bool:
    """Return True if the optional ``mcp`` package can be imported."""
    try:
        import mcp  # noqa: F401
    except ImportError:
        return False
    return True


def require_mcp_ready(config: McpRegistryConfig) -> None:
    """Fail closed when MCP is enabled but the optional package is missing."""
    if not config.enable:
        return
    if not config.enabled_servers:
        return
    if not mcp_package_available():
        raise McpConfigError(
            "MCP is enabled but the optional package is not installed; "
            "run: python -m pip install -e '.[mcp]'"
        )


def describe_registry(config: McpRegistryConfig) -> dict[str, Any]:
    """Safe, JSON-serializable summary for health/diagnostics (no secrets)."""
    return {
        "enable": config.enable,
        "package_available": mcp_package_available(),
        "server_count": len(config.servers),
        "enabled_server_count": len(config.enabled_servers),
        "servers": [
            {
                "name": server.name,
                "enabled": server.enabled,
                "read_only": server.read_only,
                "command0": server.command[0] if server.command else "",
                "arg_count": len(server.command),
                "timeout_seconds": server.timeout_seconds,
                "known_reference": server.name in KNOWN_REFERENCE_SERVERS,
            }
            for server in config.servers
        ],
    }


__all__ = [
    "KNOWN_REFERENCE_SERVERS",
    "McpConfigError",
    "McpRegistryConfig",
    "McpServerSpec",
    "default_mcp_config",
    "describe_registry",
    "mcp_package_available",
    "parse_mcp_config",
    "require_mcp_ready",
]

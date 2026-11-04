"""Load the optional [mcp] section from a TARA TOML config file."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tara_app.mcp_registry import (
    McpConfigError,
    McpRegistryConfig,
    default_mcp_config,
    parse_mcp_config,
    require_mcp_ready,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 not supported
    tomllib = None  # type: ignore[assignment]


def load_mcp_config_from_toml(path: Path | str, *, require_ready: bool = False) -> McpRegistryConfig:
    """Parse only the ``[mcp]`` table from ``tara-app.toml``.

    Missing file or missing ``[mcp]`` table → disabled default config.
    Invalid MCP tables raise ``McpConfigError``.
    """
    if tomllib is None:
        raise McpConfigError("tomllib is required (Python 3.11+)")

    path = Path(path)
    if not path.is_file():
        return default_mcp_config()

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise McpConfigError(f"could not read config: {path}") from exc

    try:
        data: dict[str, Any] = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        raise McpConfigError(f"invalid TOML in {path}") from exc

    mcp_raw = data.get("mcp")
    config = parse_mcp_config(mcp_raw)
    if require_ready:
        require_mcp_ready(config)
    return config


__all__ = ["load_mcp_config_from_toml"]

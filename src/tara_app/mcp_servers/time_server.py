"""Minimal stdio MCP time server for TARA-App (optional reference).

Run via tara-app.toml::

    [[mcp.servers]]
    name = "time"
    command = ["{python}", "-m", "tara_app.mcp_servers.time_server"]
    enabled = true
    read_only = true

Requires: ``python -m pip install -e ".[mcp]"``
"""
from __future__ import annotations

from datetime import datetime, timezone


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "MCP package required. Run: python -m pip install -e '.[mcp]'"
        ) from exc

    mcp = FastMCP("tara-time")

    @mcp.tool()
    def get_current_time(timezone_name: str = "UTC") -> str:
        """Return the current UTC time as ISO-8601. timezone_name is informational."""
        now = datetime.now(timezone.utc).isoformat()
        return f"{now} (requested zone hint: {timezone_name})"

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

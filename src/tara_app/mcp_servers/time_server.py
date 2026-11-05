"""Built-in MCP time server (read-only)."""
from __future__ import annotations

import json
import sys

from tara_app.mcp_servers.time_logic import current_time_payload


def main() -> int:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print(
            "optional mcp package is not installed; run: python -m pip install -e '.[mcp]'",
            file=sys.stderr,
        )
        return 2

    server = FastMCP("tara-time")

    @server.tool()
    def get_current_time(timezone: str | None = None) -> str:
        """Return the current UTC time and optional local time for a timezone name."""
        try:
            payload = current_time_payload(timezone)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(payload)

    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

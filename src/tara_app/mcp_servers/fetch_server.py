"""Built-in bounded HTTP(S) fetch MCP server (read-only)."""
from __future__ import annotations

import json
import sys

from tara_app.mcp_servers.fetch_logic import FetchError, fetch_text


def main() -> int:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print(
            "optional mcp package is not installed; run: python -m pip install -e '.[mcp]'",
            file=sys.stderr,
        )
        return 2

    server = FastMCP("tara-fetch")

    @server.tool()
    def fetch(url: str) -> str:
        """Fetch a public http(s) URL and return bounded text content."""
        try:
            payload = fetch_text(url)
        except FetchError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(payload)

    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

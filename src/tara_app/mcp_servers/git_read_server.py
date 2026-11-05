"""Built-in read-only git MCP server.

Roots come from ``TARA_MCP_GIT_ROOTS`` (semicolon-separated absolute directories).
Only status / log / show-file are exposed. No network or mutation commands.
"""
from __future__ import annotations

import json
import os
import sys

from tara_app.mcp_servers.git_read_logic import (
    GitReadError,
    git_log,
    git_show_file,
    git_status,
)


def _roots_from_env() -> list[str]:
    raw = os.environ.get("TARA_MCP_GIT_ROOTS", "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def main() -> int:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print(
            "optional mcp package is not installed; run: python -m pip install -e '.[mcp]'",
            file=sys.stderr,
        )
        return 2

    roots = _roots_from_env()
    if not roots:
        print(
            "TARA_MCP_GIT_ROOTS must list at least one allowlisted directory "
            "(semicolon-separated)",
            file=sys.stderr,
        )
        return 2

    server = FastMCP("tara-git-read")

    @server.tool()
    def status(repo_path: str) -> str:
        """Return porcelain git status for a repo under the allowlisted roots."""
        try:
            payload = git_status(repo_path, roots)
        except GitReadError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(payload)

    @server.tool()
    def log(repo_path: str, max_count: int = 10) -> str:
        """Return a bounded commit log (read-only)."""
        try:
            payload = git_log(repo_path, roots, max_count=max_count)
        except GitReadError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(payload)

    @server.tool()
    def show_file(repo_path: str, path: str, revision: str = "HEAD") -> str:
        """Show a tracked file at a revision (read-only)."""
        try:
            payload = git_show_file(repo_path, roots, path=path, revision=revision)
        except GitReadError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(payload)

    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Built-in read-only scoped filesystem MCP server.

Roots are taken from the ``TARA_MCP_FS_ROOTS`` environment variable: a
semicolon-separated list of absolute directories. Paths outside those roots
are denied.

Run::

    TARA_MCP_FS_ROOTS=/safe/project python -m tara_app.mcp_servers.scoped_fs_server

Requires the optional ``mcp`` package.
"""
from __future__ import annotations

import json
import os
import sys

from tara_app.mcp_servers.scoped_fs_logic import ScopedFsError, list_directory, read_text_file


def _roots_from_env() -> list[str]:
    raw = os.environ.get("TARA_MCP_FS_ROOTS", "").strip()
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
            "TARA_MCP_FS_ROOTS must list at least one allowlisted directory "
            "(semicolon-separated)",
            file=sys.stderr,
        )
        return 2

    server = FastMCP("tara-scoped-fs")

    @server.tool()
    def list_dir(path: str) -> str:
        """List entries in a directory under the allowlisted roots (read-only)."""
        try:
            entries = list_directory(path, roots)
        except ScopedFsError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"path": path, "entries": entries})

    @server.tool()
    def read_file(path: str) -> str:
        """Read a UTF-8 text file under the allowlisted roots (bounded size)."""
        try:
            text = read_text_file(path, roots)
        except ScopedFsError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"path": path, "content": text})

    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

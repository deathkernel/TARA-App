"""Built-in MCP reference servers shipped with TARA-App.

Opt-in only via ``[mcp]`` allowlist. No mutating host tools.
"""

__all__ = ["KNOWN_BUILTIN_SERVERS"]

KNOWN_BUILTIN_SERVERS = frozenset({"time", "scoped_fs", "fetch"})

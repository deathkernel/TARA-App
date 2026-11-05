"""Built-in MCP reference servers shipped with TARA-App.

These servers are **opt-in**. They must be listed under ``[mcp]`` with a fixed
``command`` argv and ``enable = true``. They never run unless the operator
configures them. Mutating host tools are intentionally absent.
"""

__all__ = ["KNOWN_BUILTIN_SERVERS"]

KNOWN_BUILTIN_SERVERS = frozenset({"time", "scoped_fs", "git_read"})

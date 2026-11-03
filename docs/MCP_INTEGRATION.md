# MCP integration

Status: **foundation + tool gateway** (still not wired into Chat UI).

## What exists

| Module | Role |
|--------|------|
| `tara_app.mcp_registry` | Parse/validate `[mcp]` allowlist; disabled by default |
| `tara_app.mcp_toml` | Load `[mcp]` from `tara-app.toml` via `tomllib` |
| `tara_app.mcp_client.McpToolGateway` | `list_tools` / `call_tool` against allowlisted servers only |

Optional package: `python -m pip install -e ".[mcp]"`

## Safety rules

1. MCP is **off** unless `[mcp] enable = true`.
2. Only servers under `[[mcp.servers]]` may be used.
3. Each `command` is a fixed argv list (no shell string).
4. `call_tool` requires a non-empty app-issued `approval_token`.
5. Prefer `read_only = true` until mutating tools have Security review.
6. Do not enable unrestricted filesystem or shell MCP servers on the host.

## Example config

```toml
[mcp]
enable = false

[[mcp.servers]]
name = "time"
command = ["uvx", "mcp-server-time"]
enabled = true
read_only = true
timeout_seconds = 30
```

## Code usage (library)

```python
from pathlib import Path
from tara_app.mcp_toml import load_mcp_config_from_toml
from tara_app.mcp_client import McpToolGateway

config = load_mcp_config_from_toml(Path("tara-app.toml"), require_ready=True)
gateway = McpToolGateway(config)
tools = gateway.list_tools()  # requires enable=true + package if using live stdio
# text = gateway.call_tool("time", "get_current_time", {}, approval_token="…")
```

## Next slices

1. Register MCP diagnostics on `/api/health`.
2. Wire `list_tools` into a read-only app capability.
3. Wire `call_tool` through Security + one-shot approval UX.
4. Optional reference servers: time → fetch → scoped filesystem → git (read).
5. Agent tool-loop patterns (claude-agent-sdk) without host shell.

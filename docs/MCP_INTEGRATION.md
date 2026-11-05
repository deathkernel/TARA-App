# MCP integration

Status: **foundation + read-only HTTP discovery** (tool execution remains disabled until the explicit approval UI is implemented).

## What exists

| Module | Role |
|--------|------|
| `tara_app.mcp_registry` | Parse/validate `[mcp]` allowlist; disabled by default |
| `tara_app.mcp_toml` | Load `[mcp]` from `tara-app.toml` via `tomllib` |
| `tara_app.mcp_client.McpToolGateway` | `list_tools` / `call_tool`; execution requires an opaque app-issued approval grant |

Optional package: `python -m pip install -e ".[mcp]"`

## Safety rules

1. MCP is **off** unless `[mcp] enable = true`.
2. Only servers under `[[mcp.servers]]` may be used.
3. Each `command` is a fixed argv list (no shell string).
4. `call_tool` requires an opaque approval grant created only after the orchestrator validates and consumes its one-shot token.
5. MCP HTTP mutation endpoints are disabled until a user-facing confirmation flow displays the exact server, tool, and arguments.
6. Prefer `read_only = true` until mutating tools have Security review.
7. Do not enable unrestricted filesystem or shell MCP servers on the host.

## Built-in reference servers

| Module | Tools | Notes |
|--------|-------|-------|
| `python -m tara_app.mcp_servers.time_server` | `get_current_time` | Read-only clock |
| `python -m tara_app.mcp_servers.scoped_fs_server` | `list_dir`, `read_file` | Paths under `TARA_MCP_FS_ROOTS` only |
| `python -m tara_app.mcp_servers.git_read_server` | `status`, `log`, `show_file` | Repos under `TARA_MCP_GIT_ROOTS` only; no fetch/push/commit |

Logic for these servers is unit-tested without a live stdio MCP session. The optional `mcp` package is required only to *run* the stdio process.

## Example config

```toml
[mcp]
enable = false

[[mcp.servers]]
name = "time"
command = ["{python}", "-m", "tara_app.mcp_servers.time_server"]
enabled = true
read_only = true
read_only_tools = ["get_current_time"]
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
# Tool execution is intentionally unavailable through the public HTTP API until
# the explicit MCP approval UI is connected to the orchestrator.
```

## Next slices

1. Register MCP diagnostics on `/api/health` (see `feat/mcp-health-and-fetch`).
2. Wire `list_tools` into a read-only app capability.
3. Wire `call_tool` through Security + one-shot approval UX.
4. Optional reference servers: time → fetch → scoped filesystem → ~~git (read)~~.
5. Agent tool-loop patterns (claude-agent-sdk) without host shell.

# MCP integration

Status: **foundation + read-only HTTP discovery** (tool execution remains disabled until the explicit approval UI is implemented).

## What exists

| Module | Role |
|--------|------|
| `tara_app.mcp_registry` | Parse/validate `[mcp]` allowlist; disabled by default |
| `tara_app.mcp_toml` | Load `[mcp]` from `tara-app.toml` via `tomllib` |
| `tara_app.mcp_client.McpToolGateway` | `list_tools` / `call_tool`; execution requires an opaque app-issued approval grant |
| `tara_app.tool_loop` | Bounded multi-step tool plan validation and sequential runner |

Optional package: `python -m pip install -e ".[mcp]"`

## Safety rules

1. MCP is **off** unless `[mcp] enable = true`.
2. Only servers under `[[mcp.servers]]` may be used.
3. Each `command` is a fixed argv list (no shell string).
4. `call_tool` requires an opaque approval grant.
5. Prefer `read_only = true` until mutating tools have Security review.

## Built-in reference servers

| Module | Tools | Notes |
|--------|-------|-------|
| `python -m tara_app.mcp_servers.time_server` | `get_current_time` | Read-only clock |
| `python -m tara_app.mcp_servers.scoped_fs_server` | `list_dir`, `read_file` | Paths under `TARA_MCP_FS_ROOTS` only |
| `python -m tara_app.mcp_servers.git_read_server` | `status`, `log`, `show_file` | Repos under `TARA_MCP_GIT_ROOTS` only |\n| `python -m tara_app.mcp_servers.fetch_server` | `fetch_text` | Public HTTP(S) only; pinned DNS result; redirects rejected |

## Tool-loop foundation

`tara_app.tool_loop` validates multi-step tool plans and runs them only through an
injected executor. Plans are **data** — model text is never executed as a host shell
command. Approval-gated steps pause until the application supplies a one-shot
token keyed by `step_id`. See `tara_app.tool_loop_bridge`.


## Reference-server hardening

- Fetch validates every DNS answer as public, pins the connection to a validated
  address, and rejects redirects to prevent DNS-rebinding and redirect-based
  access to private networks.
- Git read operations disable repository fsmonitor hooks and external Git
  configuration; commands remain fixed-argument and shell-free.
- Scoped filesystem reads use no-follow file opening and verify the opened file
  is a regular file before reading.
- The built-in time server uses the optional timezone database dependency for
  reliable IANA timezone conversion across supported platforms.

## Time server tests

`tests/test_mcp_time_server.py` covers UTC output, Unix timestamps, timezone
conversion, invalid timezone handling, stdio registration, and the missing
optional dependency path. It uses a fake FastMCP module and does not launch a
subprocess.

Run the focused tests with:

```powershell
python -m unittest discover -s tests -p "test_mcp_time_server.py" -v
```

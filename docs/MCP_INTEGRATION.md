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
| `python -m tara_app.mcp_servers.git_read_server` | `status`, `log`, `show_file` | Repos under `TARA_MCP_GIT_ROOTS` only |

## Tool-loop foundation

`tara_app.tool_loop` validates multi-step tool plans and runs them only through an
injected executor. Plans are **data** — model text is never executed as a host shell
command. Approval-gated steps pause until the application supplies a one-shot
token keyed by `step_id`. See `tara_app.tool_loop_bridge`.

## Time server tests

`tests/test_mcp_time_server.py` covers the UTC payload and Unix timestamp,
timezone normalization and conversion, invalid timezone handling, stdio server
registration, and the missing-optional-dependency message. The server tests use a
small fake FastMCP module, so they do not launch a subprocess or require the
optional MCP package.

Run the focused tests with:

```powershell
python -m unittest discover -s tests -p "test_mcp_time_server.py" -v
```

The repository CI also discovers this test through
`python -m unittest discover -s tests -v`.

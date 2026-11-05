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
4. `call_tool` requires an opaque approval grant created only after the orchestrator validates and consumes its one-shot token.
5. MCP HTTP mutation endpoints are disabled until a user-facing confirmation flow displays the exact server, tool, and arguments.
6. Prefer `read_only = true` until mutating tools have Security review.
7. Do not enable unrestricted filesystem or shell MCP servers on the host.

## Built-in reference servers

| Module | Tools | Notes |
|--------|-------|-------|
| `python -m tara_app.mcp_servers.time_server` | `get_current_time` | Read-only clock |
| `python -m tara_app.mcp_servers.scoped_fs_server` | `list_dir`, `read_file` | Paths under `TARA_MCP_FS_ROOTS` only |

## Tool-loop foundation

`tara_app.tool_loop` validates multi-step tool plans and runs them only through an
injected executor. Plans are **data** — model text is never executed as a host shell
command. Approval-gated steps pause until the application supplies a one-shot
token keyed by `step_id`. See `ApplicationFacade.validate_tool_plan` and
`run_validated_tool_plan`.

## Next slices

1. Register MCP diagnostics on `/api/health`.
2. Wire `list_tools` into a read-only app capability.
3. Wire `call_tool` through Security + one-shot approval UX (UI surface).
4. Optional reference servers: time → fetch → scoped filesystem → git (read).
5. ~~Agent tool-loop patterns~~ (foundation landed; Chat UI integration pending).

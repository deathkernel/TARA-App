# MCP Phase 2 (clean)

Branch: `feat/mcp-phase2-clean`

## What this phase adds

1. Allowlisted MCP registry + client (from foundation)
2. `attach_mcp(app, gateway)` — no Orchestrator rewrite
3. Runtime loads optional `[mcp]` from `tara-app.toml`
4. Built-in **time** MCP server: `python -m tara_app.mcp_servers.time_server`
5. Web health includes `mcp` status when attached
6. Optional APIs: `/api/mcp/tools`, `/api/mcp/approve`, `/api/mcp/call`

## Enable

```toml
[mcp]
enable = true

[[mcp.servers]]
name = "time"
command = ["{python}", "-m", "tara_app.mcp_servers.time_server"]
enabled = true
read_only = true
timeout_seconds = 30
```

```bat
python -m pip install -e ".[mcp]"
```

## Safety

- Default OFF
- Fixed argv only (no shell)
- `call_tool` requires app-issued one-shot approval token
- Never treat model text as server command

## Next phases

- Chat tool-loop proposals (data-only)
- filesystem/git/fetch reference servers (allowlisted only)
- Skills pack loader

# MCP integration (foundation)

Status: **foundation only** — configuration and allowlist validation exist; Chat does not yet call MCP tools.

## Safety rules

1. MCP is **off** unless `[mcp] enable = true` in `tara-app.toml`.
2. Only servers listed under `[[mcp.servers]]` may be used.
3. Each server `command` is a **fixed argv list** (no shell string).
4. Optional dependency: `python -m pip install -e ".[mcp]"`.
5. Prefer `read_only = true` until a mutating tool has an approval path.
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

## Code entry points

- `tara_app.mcp_registry.parse_mcp_config`
- `tara_app.mcp_registry.require_mcp_ready`
- `tara_app.mcp_registry.describe_registry`

## Next slices

1. Load `[mcp]` from the real app config parser.
2. Stdio session lifecycle (start/stop) with timeouts.
3. `list_tools` / `call_tool` behind Security approval.
4. Optional reference servers: time → fetch → scoped filesystem → git (read).

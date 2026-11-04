# MCP HTTP API

MCP is disabled unless `[mcp].enable = true` and at least one server is explicitly configured. The local HTTP API is loopback-only and reuses the app's origin, JSON content-type, and 1 MB request-size checks.

## Available endpoints

- `GET /api/mcp/status` — safe registry summary; never includes credentials.
- `GET /api/mcp/tools` — list tools from enabled servers.
- `GET /api/mcp/tools?server=time` — list tools from one enabled server.

Tool discovery is metadata-only from TARA's perspective, but it launches the explicitly configured MCP server process. Enable only trusted server commands.

## Tool execution is intentionally not exposed over HTTP yet

`POST /api/mcp/approve` and `POST /api/mcp/call` are not available. The previous HTTP design allowed any local client that could reach the loopback API to request an approval token and execute an allowlisted tool. A session ID supplied by that client is not proof of human identity or consent.

TARA does not yet have an MCP-specific confirmation surface that displays the exact server, tool, and arguments and requires a deliberate user action. Until that UX is implemented and connected to TARA's approval flow, the HTTP mutation endpoints remain disabled.

The orchestrator retains operation-bound, one-shot approval tokens for trusted in-process integration. The gateway additionally requires an opaque grant created only after the orchestrator validates and consumes the token; a caller-supplied non-empty string is not accepted as approval. This is defense in depth, not a security boundary against malicious code already executing inside the TARA Python process.

## Read-only server policy

MCP tool metadata cannot reliably prove that a tool is non-mutating. Therefore, a server configured with `read_only = true` may execute only tool names explicitly reviewed and listed in `read_only_tools`. An empty list blocks every tool call for that server. This list is an administrator's trust decision about the named tools; it is not inferred from tool names or descriptions. Servers with `read_only = false` may call listed server tools, but every call still requires the one-shot approval flow.

Example:

```toml
[mcp]
enable = true

[[mcp.servers]]
name = "time"
command = ["uvx", "mcp-server-time"]
enabled = true
read_only = true
read_only_tools = ["get_current_time"]
timeout_seconds = 30
```

No server definitions or shell commands are accepted through the HTTP API.

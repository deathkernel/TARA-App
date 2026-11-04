# MCP HTTP API

MCP is disabled unless `[mcp].enable = true` and at least one server is explicitly configured. The local HTTP API is loopback-only and reuses the app's origin, JSON content-type, and 1 MB request-size checks.

## Endpoints

- `GET /api/mcp/status` — safe registry summary; never includes credentials.
- `GET /api/mcp/tools` — list tools from enabled servers.
- `GET /api/mcp/tools?server=time` — list tools from one enabled server.
- `POST /api/mcp/approve` — issue a one-shot approval token bound to the session, server, tool, and canonical arguments digest.
- `POST /api/mcp/call` — consume that token and execute exactly the approved call.

Approval request:

```json
{
  "server": "time",
  "tool": "get_current_time",
  "arguments": {"timezone": "Asia/Kolkata"},
  "session_id": "local-session"
}
```

The response contains an opaque `approval_token`. Send it with the exact same server, tool, arguments, and session to `/api/mcp/call`. Tokens expire, are one-shot, and are rejected if any bound field differs. Do not expose tokens to model-generated text or remote clients.

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

Tool listing is metadata discovery only. No server is launched unless it is explicitly enabled, and no shell command is accepted through the HTTP API.

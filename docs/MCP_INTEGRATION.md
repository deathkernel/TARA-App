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


## External integration catalogue (templates, not enabled servers)

TARA's generic stdio gateway can connect to trusted third-party MCP servers. These
entries are integration targets, **not claims that credentials, setup, or a
working connection are already present**. Keep MCP disabled until each server is
installed, its command is reviewed, and the user-facing approval/audit gate is
complete.

| Integration | Intended capabilities | Suggested access policy | State |
|---|---|---|---|
| GitHub | Search repositories/code; inspect files, issues, and pull requests | Read-only allowlist first; writes require the full Security approval gate | External server candidate |
| Google Drive | Search and read files/metadata | Read-only; OAuth scopes limited to selected Drive files | External server candidate |
| PostgreSQL | Schema inspection and SELECT queries | Dedicated read-only database role; never expose DDL/DML by default | External server candidate |
| Browser (Playwright MCP) | Navigate pages and inspect accessible page content | Treat navigation and page interaction as network access; no form submission/downloads without explicit approval | External server candidate |
| Slack | Search and read messages in approved workspaces | Read-only, least-privilege OAuth scopes | Future candidate |
| Notion | Search and read approved pages/databases | Read-only integration token and workspace/page allowlist | Future candidate |
| Linear | Read issues, projects, and cycles | Read-only first; mutations gated | Future candidate |
| Google Calendar | Read events and availability | Read-only calendar scope | Future candidate |
| Sentry | Read errors, issues, and releases | Read-only project scope | Future candidate |
| Docker | Inspect containers/images and logs | Read-only metadata first; never mount host socket for unrestricted control | Future candidate |

### Integration safety checklist

Before adding a server to a user's local `[[mcp.servers]]` configuration:

1. Verify the upstream project, package/registry owner, license, release activity,
   and installation instructions.
2. Pin the package or container to a reviewed version/digest; avoid floating
   `latest` tags for production use.
3. Keep credentials outside TOML and source control. Use a dedicated secret
   store or a narrowly scoped environment/credential handoff.
4. Restrict filesystem roots, repository allowlists, database roles, OAuth
   scopes, and workspace/project IDs to the minimum required.
5. Inspect the server's actual tool list and arguments. Add only reviewed
   non-mutating tool names to `read_only_tools`; tool descriptions alone do not
   prove safety.
6. Keep writes, browser submissions, shell/terminal, and administrative actions
   disabled until the confirmation UI, TARA-Security decision, and audit event
   are wired end-to-end.
7. Test denial paths, timeouts, oversized outputs, credential redaction, and
   server shutdown before enabling it.

**Current limitation:** TARA's approval-token issuer currently permits only
explicitly allowlisted read-only tools. Writable-server approval, the MCP
confirmation UI, and end-to-end audit integration are not complete. Therefore
the catalogue above must not be interpreted as permission to enable write
operations. The HTTP API exposes discovery only; HTTP tool execution remains
disabled.

For current built-in server implementations and exact local configuration,
see the sections above and `tara-app.example.toml`.

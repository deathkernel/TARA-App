# TARA-App Integration Contracts (Draft v1)

This document specifies the target API. It does not imply that the adapters are implemented.

## Module identifiers

- `chat`
- `code`
- `handler`

## Request

```json
{
  "schema_version": "1.0",
  "request_id": "uuid",
  "session_id": "uuid",
  "module": "chat|code|handler",
  "action": "capability identifier",
  "inputs": {},
  "workspace_root": null,
  "timeout_seconds": 30,
  "approval_token": null
}
```

Validation rules:
- Reject unknown schema versions, modules, actions, and fields not allowed by the capability schema.
- Put hard upper bounds on payload size and timeout.
- A workspace-scoped capability must supply a configured workspace root; the adapter must independently validate it.
- Mutating capabilities must require a valid, short-lived approval token tied to the exact request and target scope.
- Never accept arbitrary executable paths or shell command strings from model-generated inputs.

## Result

```json
{
  "schema_version": "1.0",
  "request_id": "uuid",
  "ok": true,
  "status": "success|unavailable|permission_denied|invalid_request|timeout|cancelled|failed",
  "data": {},
  "error": null,
  "duration_ms": 0,
  "audit_ref": "event-id"
}
```

The adapter must preserve the original request ID, bound returned data, redact secrets, and normalize exceptions to known error states. Errors must not leak tokens, environment secrets, or full sensitive paths.

## Initial capability examples

| Module | Capability | Initial policy |
|---|---|---|
| chat | `chat.respond` | Local provider configuration, bounded input/output |
| code | `code.plan` | Read-only planning/reporting |
| code | `code.inspect_workspace` | Configured workspace only |
| code | `code.run_tests` | Disabled until sandbox runner is configured |
| handler | `handler.doctor` | Allowlisted read-only diagnostic |
| handler | `handler.health` | Allowlisted read-only diagnostic |
| handler | `handler.deps` | Allowlisted read-only diagnostic |
| handler | `handler.repair` | Disabled through app natural-language dispatch pending explicit approval design |

Actual capabilities must be checked against each engine version before enabling. This draft is not a guarantee that each command exists in all versions.


## Request concurrency and duplicate submissions

The app orchestrator rejects an identical in-flight question when it is submitted
again in the same session (case- and surrounding-whitespace-insensitive). The
rejection uses status `unavailable` and reason code `duplicate_request`; it does
not enqueue or silently discard the first request. Once the first request
finishes, the same question can be submitted again as a normal retry. This is
request de-duplication, not process cancellation or a guarantee that semantically
similar prompts are identical.


## Active request cancellation

The local UI assigns a unique request ID to each chat submission and can send
`POST /api/cancel-request` with that ID and its session ID. The orchestrator
checks the session binding and delegates cancellation only to the adapter
currently executing that request. The stdio and Handler adapters terminate the associated process tree (and
force-kill it if it does not exit promptly), then return the normalized
`cancelled` status. This does not cancel routing, model preparation, or health
checks before specialist execution begins. Adapters that do not expose process
cancellation report the operation as unsupported/not running. The
existing `POST /api/cancel` endpoint remains dedicated to cancelling pending
human approvals.


## Specialist input limits

TARA-Code accepts at most four explicitly attached source files and 512 KB of
combined decoded source. TARA-App applies this limit before dispatch so a
request that exceeds the specialist contract is rejected as `invalid_request`
instead of being sent to the module and failing later. The app forwards the
supported source suffixes from TARA-Code, including JSON, YAML, TOML, and
Markdown files. Code execution remains disabled; the specialist returns
review-first plans and proposals only.

## Graceful shutdown

When the local server stops, TARA-App stops accepting new orchestration and
approval work, requests cancellation of active specialist process trees, and
then waits for HTTP worker threads to close. The app does not claim that
non-cancellable external operations (such as model preparation) are interrupted.


## UI file attachments

The local chat UI reads selected files in the browser and sends bounded base64
attachments only with the user's submitted message. The HTTP request is capped
at 15 MB and the decoded attachment total at 10 MB across at most 20 files.
The orchestrator forwards only attachment types relevant to the selected
specialist and enforces the narrower Code, Vision, Voice, and Data input
limits before dispatch. Study receives at most four supported text/PDF files;
its module applies its own 200,000-character extracted-source limit.


## Conversation session persistence

Backend SQLite persistence is opt-in through the `[sessions]` table in
`tara-app.toml`. Without `sessions.database_path`, the backend keeps session
history in memory and the React UI keeps its existing local browser history.
The configured store persists at most 100 sessions by default, with up to 24
messages per session, 20,000 characters per message, and a 120,000-character
aggregate orchestration-history budget. Older messages are trimmed first. When capacity is
reached, the least-recently-updated session is evicted; there is no time-based
expiry. Closing a session deletes its rows.

The SQLite schema uses `PRAGMA user_version = 1`; unknown future versions fail
closed rather than being silently rewritten. The database file is restricted
to owner read/write permissions on POSIX systems. SQLite content is not
encrypted at rest; choose a local path protected by the operating system's
user permissions. Browser history remains limited to the 12 most recent chats.

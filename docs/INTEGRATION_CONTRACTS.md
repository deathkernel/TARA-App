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
  "status": "success|unavailable|permission_denied|invalid_request|timeout|failed",
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
currently executing that request. The stdio adapter terminates the associated
child process (and force-kills it if it does not exit promptly), then returns
the normalized `cancelled` status. This does not cancel routing or health
checks before specialist execution begins, and adapters that do not expose
process cancellation report the operation as unsupported/not running. The
existing `POST /api/cancel` endpoint remains dedicated to cancelling pending
human approvals.

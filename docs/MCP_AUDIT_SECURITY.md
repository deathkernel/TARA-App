# MCP Audit and Approval Security

## Scope

TARA uses the existing `JsonlAuditLog` for MCP audit events. There is one
audit implementation; the separate `McpAuditLog` proposal is not adopted.
MCP remains opt-in and disabled by default.

## Recorded lifecycle

The local JSONL log records:

- `approval_issued` after the approval is bound to one session, server, tool,
  canonical-JSON argument digest and expiry.
- `approval_rejected` for invalid, expired or mismatched approvals.
- `tool_call_started` after a valid one-shot approval is consumed and before
  the gateway is invoked.
- `tool_call_succeeded` or `tool_call_failed` after the gateway returns.

Raw approval tokens, session identifiers and tool arguments are never written.
Only SHA-256 digests and allowlisted metadata are recorded. The generic audit
sink applies recursive key-based redaction, appends JSONL records, flushes and
fsyncs each record, and rotates the MCP log at a 1 MiB limit.

## Failure semantics

- If approval issuance cannot be audited, the newly created in-memory approval
  is revoked, no token is returned, and MCP audit health is marked degraded.
- If the pre-dispatch `tool_call_started` event cannot be persisted, the
  one-shot approval remains consumed, the gateway is not called, and MCP
  audit health is marked degraded.
- If the gateway fails, TARA attempts to persist a failure event and preserves
  the original gateway exception.
- If a successful tool call cannot have its outcome event persisted, TARA
  returns the already-produced result and marks MCP audit health as degraded.
  The durable `tool_call_started` event remains evidence that dispatch began;
  callers must not blindly retry an operation whose outcome is uncertain.

## Boundaries

There is no HTTP endpoint for approval issuance or tool execution in this
change. The existing read-only MCP status, tool-discovery and integration
catalogue endpoints remain separate. A future approval UI must display the
exact operation and arguments, require an explicit user action, bind the
approval to the active session, and show the result before any HTTP execution
path is considered.

## Verification

Tests cover redaction, bounded rotation, approval binding, expiry, replay,
audit-write failure before dispatch, gateway failure and post-dispatch audit
degradation. CI verification is recorded in the pull request and the
remaining-features inventory; local Windows/browser smoke testing remains a
separate acceptance check.

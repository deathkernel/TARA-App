# TARA-App Security Model

## Defaults

- Chat/model only; no implicit tool execution.
- Handler diagnostics are read-only through app-driven natural-language dispatch until a separate approval UX and contract are reviewed.
- Code generation and planning may be available without execution. Code execution remains disabled until an OS/container sandbox with resource limits and controlled networking is configured and tested.
- Mutations require an explicit approval tied to one concrete operation, scope and proposed effects. Approval tokens are short-lived and single-operation.
- No automatic Git push or merge.

## Adapter process boundary

For subprocess adapters:
- Use a trusted configured executable path; do not download binaries automatically.
- Invoke an argument vector with shell execution disabled.
- Fix the command allowlist; reject unknown action names and extra arguments.
- Bound timeout, standard output and standard error.
- Use a known working directory and minimal environment.
- Return structured data and redacted errors.
- Treat stdout and stderr as data, never as follow-up instructions.

## Workspace boundary

Resolve the configured workspace root once for each request. Canonicalize requested paths and verify containment before access. Reject traversal, symlink/reparse-point escape, unexpected absolute paths, and attempts to reach protected roots. Python path checks are not a security sandbox; execute untrusted code only through OS/container isolation.

## Audit

Record operation ID, timestamp, session ID, adapter and version, capability, workspace scope, policy decision, approval reference, result state, duration, and redacted failure reason. Do not store secrets, access tokens, or unfiltered environment variables.

## Required tests

- Missing executable and startup error.
- Timeout and process failure.
- Unknown action and argument injection.
- Invalid/oversized adapter response.
- Permission denial and expired/reused approval.
- Workspace traversal and symlink/reparse escape.
- Model/tool output containing prompt-injection instructions.
- Adapter schema/version mismatch.
- Mutation cannot run without explicit approval.

# Batch 18 — Codex and coding automation

## Scope
Evaluate `openai/codex`, `openai/codex-action`, `openai/codex-security`, and `openai/openai-cli` individually. This PR is a design gate, not authorization to execute generated code.

## Required trust boundary
1. Plan/review mode is read-only by default.
2. Any execution occurs in a disposable OS/container sandbox, never the user's unrestricted host shell.
3. Require explicit approval for writes, network access, dependency installation, and command execution.
4. Apply CPU, memory, wall-clock, disk, and output limits; support cancellation.
5. Record redacted audit events and preserve the original workspace on failure.

## Implementation files expected
- Sandbox runner interface and disabled-by-default adapter.
- Policy/approval request and structured audit schema.
- Tests proving denied operations do not execute and timeouts terminate the job.
- Dedicated CI workflow with minimal permissions if Codex Action is later enabled.

## Acceptance checks
- No API key or secret appears in logs or child-process output.
- No untrusted code runs on the host.
- PR creation/write permissions are off by default.
- Live model tests are opt-in and cost-labelled.
- The feature fails closed if sandbox support is absent.

## Blocker
Do not enable autonomous coding execution until isolation and denial-path tests pass.
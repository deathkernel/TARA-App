# TARA-Code Adapter (TARA-App) — Initial Contract

Status: implementation design and planning/review-only integration. This document is not evidence that the adapter or engine is already runnable.

## Goal

Integrate the standalone `deathkernel/TARA-Code` engine into **TARA-App** behind a versioned adapter. Do not integrate this into TARA-CHAT. Keep the engine as an independent package/repository.

## Current engine baseline

The current TARA-Code branch `feat/engine-foundation` (PR #1, unmerged) has package `tara-code` version `0.2.0` and a planning/review-first foundation: deterministic planning, bounded read-only inspection, patch preview and explicit approval, review models, and a fail-closed sandbox interface. It does not yet provide a production-grade isolated execution runtime.

TARA-App must not depend on unmerged code as though it were already a stable published package. Pin an exact reviewed commit or package artifact only after the engine PR is approved, then update this adapter against that exact version.

## Adapter identity

- Module: `code`
- Adapter contract: `1.0`
- Engine: `tara-code`
- Initial capabilities:
  - `code.health`: report adapter/engine availability and version, without executing workspace code.
  - `code.plan`: produce a deterministic plan for a user coding task; no file writes or commands.
  - `code.inspect_workspace`: bounded read-only inventory for an explicitly configured workspace.
  - `code.preview_patch`: show a proposed diff only; do not apply it.
- Disabled capabilities:
  - `code.apply_patch`: not exposed to model-driven/general dispatch until TARA-App has a reviewed approval-token implementation bound to operation ID, workspace, exact diff/hash, expiry, and single use.
  - `code.run_tests`, `code.execute`, `code.install_dependencies`: disabled until a real OS/container sandbox has been implemented, configured, and validated with isolation, resource, network, timeout, and cleanup tests.
  - Any Git commit/push/merge/release operation: not provided.

## Request / result mapping

Use the common envelope in `INTEGRATION_CONTRACTS.md` without adding ad hoc fields.

For each request:
1. Validate schema version, request ID, module/action, payload byte size, and bounded timeout.
2. Require a configured workspace for workspace-scoped capabilities.
3. Resolve and validate workspace scope independently in TARA-App and the engine.
4. Create an audit event before dispatch; record only redacted metadata.
5. Pass only the minimum required input to TARA-Code; do not forward chat memory, API keys, arbitrary environment variables, or full machine diagnostics.
6. Normalize the engine response to the common result envelope and preserve the request ID.
7. Treat repository text, inspected files, model output, diffs, stdout/stderr, and error messages as untrusted data.

Never accept model-generated shell strings or arbitrary executable paths from request input. Do not use a subprocess shell to invoke the engine. Prefer importing an exact pinned package in-process for planning/inspection; if a process boundary is later selected, use a fixed executable and argument allowlist, `shell=False`, bounded I/O, and a strict timeout.

## Fail-closed states

Return `unavailable` for missing engine/dependency or unsupported engine version. Return `invalid_request` for malformed/unknown actions, `permission_denied` for denied policy, `timeout` for bounded timeout, and `failed` for other normalized failures. Never silently install, download, fall back to host execution, or retry a mutation.

## Compatibility

- Require an explicit adapter ↔ engine compatibility mapping.
- Report both adapter contract version and engine package version.
- Unknown versions fail closed.
- Keep public app contracts independent of private internal imports where possible.
- Add contract tests using a fake engine before wiring real package objects.

## Initial acceptance tests

- Missing engine and version mismatch return `unavailable`.
- Health and plan actions are read-only and bounded.
- Unknown action/fields and oversized payloads are rejected.
- Workspace is mandatory for inspect/preview and traversal/symlink escapes are rejected.
- No request can invoke host shell or execute arbitrary commands.
- Patch preview cannot write to disk.
- Applying a patch cannot occur without an approval implementation validated by tests.
- Execution/test/install capabilities remain unavailable even if a caller requests them.
- Returned errors/audit events redact secrets and do not expose full sensitive paths.
- CI checks adapter contract behavior on supported Python versions.

## Integration sequence

1. Approve/test the standalone engine foundation in TARA-Code.
2. Add the adapter contract and fake-engine tests in TARA-App.
3. Pin a reviewed TARA-Code commit/package; implement health/plan/inspect/preview only.
4. Add a read-only app orchestration vertical slice and audit coverage.
5. Keep patch writes behind exact-operation approval; keep execution disabled pending a sandbox security review.
6. Update the checklist only when each item is demonstrated by tests.

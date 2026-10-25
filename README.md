# TARA-App

TARA-App is the unified application shell for the TARA ecosystem. It coordinates TARA-Chat, TARA-Code, and TARA-Handler through explicit adapters while keeping each engine independently testable.

## Current verified repository state

This repository began as an empty application scaffold. The sibling repositories currently have different maturity levels:

- **TARA-CHAT** (`deathkernel/TARA-CHAT`): Python conversation runtime with Ollama provider, bounded session history, explicit local memory, tests, and a narrow read-only subprocess bridge for Handler.
- **TARA-Code** (`deathkernel/TARA-Code`): independent coding-engine scaffold. Its README specifies bounded task planning, workspace-root constraints, sandbox-runner contracts, test/change-review reports, and human-reviewed promotion. The code engine is not yet a mature runtime integration.
- **TARA-Handler** (`deathkernel/TARA-Handler`): native C++17 CLI for developer-environment diagnostics and guarded maintenance/repair workflows. Keep it a separate executable and use a narrow process boundary.

Do not represent a planned adapter as an already working integration. Enable each adapter only after its contract and integration tests pass.

## Target architecture

```text
TARA-App UI / CLI
      |
Application API + session manager
      |
Orchestrator (intent routing, policy, correlation IDs, error normalization)
      |
      +---- TARA-Chat adapter ---- Python/Ollama chat runtime
      |
      +---- TARA-Code adapter ---- bounded plans / workspace / sandbox runner
      |
      +---- TARA-Handler adapter - native handler executable
      |
Shared contracts: config, capability registry, permissions, audit events
```

## Integration principles

1. Keep each engine separately versioned and independently testable.
2. Define explicit, versioned adapter contracts; avoid importing internal module paths across repositories as the permanent API.
3. Fail closed when a module, executable, sandbox, or permission is unavailable.
4. Never run model-generated shell text directly on the host. TARA-Code execution must go through a real OS/container sandbox; path checks alone are not a sandbox.
5. Keep Handler's C++ executable behind a subprocess boundary. Use fixed argument vectors, `shell=False`, timeouts, bounded output, and an explicit command allowlist.
6. Treat model, repository, tool, and diagnostic output as untrusted data, not as instructions or authorization.
7. Default to read-only diagnostics. Any mutation must show a plan, scope, risk and expected effects and require an explicit approval bound to that operation.
8. Store secrets outside code and logs. Do not send secrets to local models, tools, or sandboxes by default.
9. Emit structured audit events with operation ID, adapter/version, requested capability, approval state, outcome, duration, and redacted error.
10. Do not automatically merge Git changes. Show a diff and test report and leave promotion to a human.

## Suggested repository layout

```text
src/tara_app/
  app.py
  config.py
  orchestrator.py
  contracts.py
  capabilities.py
  permissions.py
  audit.py
  adapters/
    chat.py
    code.py
    handler.py
tests/
docs/
  ARCHITECTURE.md
  SECURITY.md
  INTEGRATION_CONTRACTS.md
```

This layout is a target, not a claim that those modules are already implemented.

## Adapter contract (target)

Each adapter should support:
- `health() -> HealthStatus`
- `capabilities() -> Capability[]`
- `execute(request: ModuleRequest) -> ModuleResult`

Use a versioned request with `schema_version`, `request_id`, `session_id`, `module`, `action`, structured `inputs`, `workspace_root` when applicable, `timeout_seconds`, and `approval_token` when a mutating operation requires approval.

A result should include `schema_version`, `request_id`, `ok`, `status`, structured `data`, redacted `error`, duration, and any approval/audit references. Validate payload size, field types, allowable actions, workspace boundaries, and timeout limits before dispatch.

## Initial milestones

1. **Contracts first:** specify stable request/result schemas, capability identifiers, error model and versioning policy.
2. **Read-only vertical slice:** start the app shell, expose Chat, and run Handler's existing read-only diagnostics via its current bridge.
3. **Code adapter:** integrate TARA-Code planning/reporting first; keep execution disabled until a real sandbox runner and isolation tests exist.
4. **Approval and audit:** implement explicit confirmation for all mutations, append-only structured audit events and secret redaction.
5. **Cross-module tests:** missing executable, timeout, malformed adapter output, denied permissions, path escape, injection attempts, oversized output, and adapter version mismatch.
6. **UI and packaging:** expose Chat, Code Tasks, Environment Diagnostics, approvals, and settings only after their underlying contracts are testable.

## Local development

The app shell is currently a design scaffold. Until implementation and integration tests are added, do not treat TARA-App as a runnable integrated application.

Suggested sibling checkout:

```powershell
git clone https://github.com/deathkernel/TARA-App.git
git clone https://github.com/deathkernel/TARA-CHAT.git
git clone https://github.com/deathkernel/TARA-Code.git
git clone https://github.com/deathkernel/TARA-Handler.git
```

Use the individual repositories' own setup instructions to build/test each component. Never assume a sibling binary or its dependencies are installed automatically.
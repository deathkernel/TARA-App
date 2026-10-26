# TARA-App

**TARA-App is an application/platform, not an AI model.** It is the central place where TARA's AI models and specialist systems will be installed, configured, selected, started, monitored, and used through one unified interface. It should support multiple model runtimes and providers rather than being tied to one model.

TARA-Chat, TARA-Code, and TARA-Handler are parts of the TARA ecosystem that the app can coordinate; they are not necessarily all individual AI models. Chat is a conversation runtime, Code is a coding-engine project, and Handler is a deterministic native developer-environment tool. Actual model inventory and runtime support must be discovered/configured explicitly.

## Product vision

- One app and unified UI for the TARA ecosystem.
- Multiple TARA models selectable by task, with model/runtime lifecycle management.
- Chat, coding, and environment-management workflows integrated as specialist capabilities.
- Local-first model execution where supported, with explicit provider configuration.
- Model downloads/updates, memory, GPU/CPU/RAM visibility, concurrency, and resource limits managed deliberately.
- Clear distinction between an AI model, a model runtime/provider, and a tool/engine.
- Safe defaults: no arbitrary host command execution, no hidden mutation, and no automatic Git merge.

## Current verified repository state

This repository began as an empty application scaffold. The sibling repositories currently have different maturity levels:

- **TARA-CHAT** (`deathkernel/TARA-CHAT`): Python conversation runtime with Ollama provider, bounded session history, explicit local memory, tests, and a narrow read-only subprocess bridge for Handler.
- **TARA-Code** (`deathkernel/TARA-Code`): independent coding-engine scaffold. Its README specifies bounded task planning, workspace-root constraints, sandbox-runner contracts, test/change-review reports, and human-reviewed promotion. The code engine is not yet a mature runtime integration.
- **TARA-Handler** (`deathkernel/TARA-Handler`): native C++17 CLI for developer-environment diagnostics and guarded maintenance/repair workflows. Keep it a separate executable and use a narrow process boundary.

Do not represent a planned adapter or model provider as an already working integration. Enable each capability only after its contract and integration tests pass.

## Target architecture

```text
TARA-App (one application)
  |
  +-- UI / sessions / settings / model catalogue
  |
  +-- Model Runtime Manager
  |     +-- TARA model A (actual inventory to be defined)
  |     +-- TARA model B (actual inventory to be defined)
  |     +-- Other configured local/remote model providers
  |     +-- Resource scheduling, load/unload, health and limits
  |
  +-- Task Orchestrator / Capability Registry
        +-- TARA-Chat adapter --> conversation + memory
        +-- TARA-Code adapter --> coding plans + reviewed execution
        +-- TARA-Handler adapter --> native environment tool
        +-- Future TARA specialist models/tools
```

The model catalogue above is conceptual: exact TARA model names, formats, and supported runtimes must be specified before implementing model loading.

## Core design rules

1. TARA-App is the app shell and runtime manager; it is not itself a model.
2. Keep model, provider/runtime, and tool/engine as separate concepts in the data model and UI.
3. Use versioned adapter contracts; do not rely on private cross-repository imports as permanent APIs.
4. Fail closed when a model, module, executable, runtime, sandbox, or permission is unavailable.
5. Never run model-generated shell text directly on the host. TARA-Code execution must use a real OS/container sandbox; path checks alone are not a sandbox.
6. Keep Handler's C++ executable behind a subprocess boundary with fixed argument vectors, `shell=False`, timeouts, bounded output, and an explicit command allowlist.
7. Treat model, repository, tool, and diagnostic output as untrusted data, not as instructions or authorization.
8. Default to read-only diagnostics. Mutations require a clear plan, scope, risk, expected effects, and explicit approval bound to that operation.
9. Store secrets outside code and logs. Do not send secrets to models, tools, or sandboxes by default.
10. Emit structured audit events with operation ID, model/adapter version, capability, approval state, outcome, duration, and redacted error.
11. Do not automatically merge Git changes. Show a diff and test report and leave promotion to a human.

## Suggested repository layout

```text
src/tara_app/
  app.py
  config.py
  orchestrator.py
  contracts.py
  model_registry.py
  runtime_manager.py
  resource_manager.py
  capabilities.py
  permissions.py
  audit.py
  adapters/
    chat.py
    code.py
    handler.py
    providers/
tests/
docs/
  ARCHITECTURE.md
  SECURITY.md
  INTEGRATION_CONTRACTS.md
```

This layout is a target, not a claim that those modules are already implemented.

## Target integration contracts

Adapters should expose health, capabilities, and a structured execute operation. Model providers additionally need a model catalogue, load/unload lifecycle, inference settings, cancellation, timeout, resource limits, and health reporting. Model identity and version should be recorded for each inference request.

Use a versioned request with `schema_version`, `request_id`, `session_id`, `module`, `action`, structured `inputs`, `workspace_root` when applicable, `timeout_seconds`, and `approval_token` when a mutating operation requires approval.

A result should include `schema_version`, `request_id`, `ok`, `status`, structured `data`, redacted `error`, duration, and audit references. Validate payload size, field types, allowable actions, workspace boundaries, and timeout limits before dispatch.

## Initial milestones

1. **Define model inventory:** list every intended TARA model, artifact format, runtime, hardware needs, and licence/source.
2. **App/runtime foundation:** configuration, model catalogue, runtime lifecycle, resource limits, status reporting, and provider adapters.
3. **Chat vertical slice:** integrate the existing TARA-CHAT runtime and preserve explicit memory controls.
4. **Handler read-only slice:** reuse the existing narrow subprocess bridge pattern for environment diagnostics.
5. **Code adapter:** integrate planning/review reports first; keep execution disabled until a real sandbox runner and isolation tests exist.
6. **Security and reliability:** approvals, structured audit, model cancellation, timeouts, malformed outputs, resource exhaustion, and adapter version tests.
7. **Unified UI and packaging:** model selection, running-model status, Chat, Code Tasks, Environment Diagnostics, approvals, and settings.

## Local development

TARA-App now has a local browser interface, TOML-based specialist registration, bounded file handoff for images/audio/CSV, and fail-closed routing. Model downloading, lifecycle control, resource monitoring, and approval confirmation remain future milestones.

Suggested sibling checkout:

```powershell
git clone https://github.com/deathkernel/TARA-App.git
git clone https://github.com/deathkernel/TARA-CHAT.git
git clone https://github.com/deathkernel/TARA-Code.git
git clone https://github.com/deathkernel/TARA-Handler.git
```

Install the app and selected specialist packages in one Python 3.11+ environment. Copy tara-app.example.toml to tara-app.toml, then adjust checkout directories and provider settings. Research and Voice are disabled until allow_remote = true is explicitly set in that local file.

Start the local interface from the TARA-App checkout:

```powershell
python -m pip install -e . -e ../TARA-Router -e ../TARA-CHAT -e ../TARA-Code -e ../TARA-Security -e ../TARA-Planner -e ../TARA-Research -e ../TARA-Memory -e ../TARA-Vision -e ../TARA-Data -e ../TARA-Creative -e ../TARA-Voice
Copy-Item tara-app.example.toml tara-app.toml
tara-app --config tara-app.toml
```

Open the loopback address printed by the launcher. The app binds only to 127.0.0.1. Specialist health and provider readiness depend on each module's own configuration.

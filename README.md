# TARA-App

**TARA-App is an application/platform, not an AI model.** It is the central place where TARA's AI models and specialist systems will be installed, configured, selected, started, monitored, and used through one unified interface. It should support multiple model runtimes and providers rather than being tied to one model.

TARA-Chat, TARA-Code, and TARA-Handler are parts of the TARA ecosystem that the app can coordinate; they are not necessarily all individual AI models. Chat is a conversation runtime, Code is a coding-engine project, and Handler is a deterministic native developer-environment tool. Actual model inventory and runtime support must be discovered/configured explicitly.

## Product vision

- One app and unified UI for the TARA ecosystem.
- Multiple model profiles selectable by task, with model/runtime lifecycle management.
- Chat, coding, and environment-management workflows integrated as specialist capabilities.
- Local-first model execution where supported, with explicit provider configuration.
- Model downloads/updates, memory, GPU/CPU/RAM visibility, concurrency, and resource limits managed deliberately.
- Clear distinction between an AI model, a model runtime/provider, and a tool/engine.
- Safe defaults: no arbitrary host command execution, no hidden mutation, and no automatic Git merge.

## Current implementation state

TARA-App is being consolidated as a single Python monorepo. The current integrated source packages are:

- `tara_app`: the local app, capability registry, approval flow, Ollama lifecycle manager, and ChatGPT-style browser UI.
- `tara_router`: a deterministic local router included in this repository; it requires no API key or paid inference.
- `tara_chat`: the conversation-only specialist, kept separate from Code.
- `tara_code`: a coding specialist using the local Ollama profile; it returns review-first proposals and never executes code.
- `tara_research`: a source-first module that queries free Crossref and Wikipedia public APIs and returns links and excerpts.
- `tara_planner`: bounded plans with validated dependencies; plans are never executed.
- `tara_memory`: local SQLite memory; write and delete requests require Security review and per-request approval.
- `tara_creative`: local Ollama writing, with no paid inference provider.
- `tara_security`: deterministic policy assessment for sensitive capabilities.
- `tara_action`: optional GitHub issue creation through the public API, gated by credentials, a repository allowlist, Security review, and explicit approval.
- `tara_voice`: optional faster-whisper transcription when compatible wheels are available; read-aloud uses installed local browser voices.
- `tara_vision`: local Ollama image analysis; images stay on the device.
- `tara_data`: deterministic, read-only CSV summaries.

TARA-Handler's C++17 source is included in TARA-App. The launchers explicitly prepare its optional native diagnostic before starting the app; only the environment-diagnosis command is exposed. If CMake or a C++ compiler is unavailable, the app uses read-only Python diagnostics. GitHub issue creation remains inactive until local credentials and a repository allowlist are configured.

## Target architecture

```text
TARA-App (one application)
  |
  +-- UI / sessions / settings / model catalogue
  |
  +-- Model Runtime Manager
  |     +-- Local Ollama profiles (configured below)
  |     +-- Other configured local/remote model providers
  |     +-- Resource scheduling, load/unload, health and limits
  |
  +-- Task Orchestrator / Capability Registry
        +-- TARA-Chat adapter --> conversation + memory
        +-- TARA-Code adapter --> coding plans + reviewed execution
        +-- TARA-Handler adapter --> native environment tool
        +-- Future TARA specialist models/tools
```

The model catalogue is configured explicitly. Model weights, provider/runtime, and specialist tools are separate concepts.

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

## Runtime and development options

See [runtime and development option notes](docs/runtime-evaluation.md) for the current scope of Amp, GitHub Copilot sandboxing, GitHub Package Firewall, and AWS TorchNeuron. These are optional references, not built-in TARA runtimes. The [native Handler integration notes](docs/native-handler.md) describe its explicit build step and read-only app boundary.

## Local Ollama model profiles

TARA-App is the only user-facing process. It starts or reuses the local Ollama service, routes each request to Chat, Code, Planner, Creative, Data, Vision, Voice, Memory, or Research, and downloads only the selected local model the first time it is needed.

| Specialist | Default model | Use |
| --- | --- | --- |
| Chat | `llama3.2:3b` | Local conversation |
| Planner | deterministic dependency checks | Reviewable plans; no execution |
| Creative | `llama3.2:3b` | Local writing and rewriting |
| Code | `qwen2.5-coder:3b` | Local code analysis and proposed changes |
| Vision | `gemma3:4b` | Local image understanding |

These are free-to-download model weights served locally by Ollama; no paid inference API is configured. Model names can be changed in `[ollama.models]`. The app does not preload models at startup. Ollama may keep a recently used model in memory during its idle period.

Research uses Crossref and Wikipedia public APIs for source records. No API key is required and no paid model is called. A research query is sent to those public services when Research is selected. Voice transcription uses the optional local faster-whisper package and weights; audio is processed on-device. The launcher skips that optional package on Python 3.15 or newer, so other app features still install. Read-aloud uses only browser voices marked local.

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

TARA-App now includes the local Router, Chat, Code, Planner, Memory, Creative, Security, Action, Data, Vision, Voice, and Research packages in the same repository. Chat and Code remain distinct specialists. Code suggestions and plans are data only; the current module does not run commands or modify a workspace. Voice transcription uses the optional local faster-whisper package when the Python runtime supports its dependencies; read-aloud uses installed local browser voices. Vision and Creative use local Ollama models; Data performs bounded, read-only CSV analysis.

### Run on Windows

1. Install Python 3.11 or newer and Ollama once.
2. Clone this repository.
3. Double-click `run-tara.bat`.

The launcher creates a local virtual environment, installs this repository, creates `tara-app.toml` from the example when needed, prepares the optional native Handler diagnostic, and starts TARA-App. TARA-App starts or reuses Ollama and downloads the model for the selected specialist on first use.


### Run on macOS or Linux

1. Install Python 3.11 or newer and Ollama once.
2. Clone this repository.
3. Run `./run-tara.sh` from the repository folder.

The script creates a virtual environment, installs TARA-App, initializes the local config, explicitly prepares the optional native Handler diagnostic, and starts the app. If a local CMake/C++ toolchain is missing, Handler keeps working through the read-only Python fallback.

### Run from a terminal

```bash
python -m pip install -e .
python -m pip install -e ".[voice]"  # optional; omit on Python 3.15+
cp tara-app.example.toml tara-app.toml
python -m tara_app.handler_launcher prepare  # optional native C++ diagnostic; safe fallback works without it
python -m tara_app --config tara-app.toml
```

On Windows PowerShell, use `Copy-Item tara-app.example.toml tara-app.toml` in place of `cp`. The app binds to loopback. The Handler preparation command is explicit; normal app execution never builds native code. Research sends only the requested search text to Crossref and Wikipedia; it returns source links and snippets for review.


### Python 3.15 and Voice transcription

If installation previously stopped with `No matching distributions found for onnxruntime`, pull the latest `main` branch and rerun `run-tara.bat`. The core app no longer requires faster-whisper. The launcher skips its Voice transcription dependency on Python 3.15 or newer (and continues if optional Voice installation fails); Chat, Code, Vision, and other app features can still run. Local audio transcription needs a Python version with compatible faster-whisper/onnxruntime packages. Browser read-aloud remains available locally.

### Consolidation status

The draft PR now contains the local Router, Chat, Code, Planner, Memory, Creative, Security, Action, Data, Vision, Voice, and Research packages. The native Handler source and on-demand adapter are included; the app exposes only environment diagnosis. GitHub issue creation requires local credentials, a repo allowlist, Security review, and one-time user approval. A final smoke run on the target computer is still needed to confirm Ollama availability and hardware-specific model performance.

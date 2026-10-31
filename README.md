# TARA-App

**TARA-App is an application/platform, not an AI model.** It is the central place where TARA's AI models and specialist systems will be installed, configured, selected, started, monitored, and used through one unified interface. It should support multiple model runtimes and providers rather than being tied to one model.

Chat, Code, Handler, Router, and the other specialist capabilities are maintained as components inside this `TARA-App` repository. The app must not depend on deleted sibling model repositories or private cross-repository imports. Chat is a conversation runtime, Code is a coding specialist, and Handler is a deterministic native developer-environment tool; these are not all individual AI models. Actual model inventory and runtime support must be discovered/configured explicitly.

> **Project handover & live roadmap:** New contributors and the daily development task should start with [Project History, Current Status & Roadmap](docs/PROJECT_STATUS_AND_ROADMAP.md). It tracks what happened, what is implemented versus unverified, the dependency-ordered remaining work, and the rules for updating progress.

## Product vision

- One app and unified UI for the TARA ecosystem.
- Multiple model profiles selectable by task, with model/runtime lifecycle management.
- Chat, coding, and environment-management workflows integrated as specialist capabilities.
- Local-first model execution where supported, with explicit provider configuration.
- Model downloads/updates, memory, GPU/CPU/RAM visibility, concurrency, and resource limits managed deliberately.
- Clear distinction between an AI model, a model runtime/provider, and a tool/engine.
- Safe defaults: no arbitrary host command execution, no hidden mutation, and no automatic Git merge.

## Current implementation state

TARA-App is being consolidated as a single Python monorepo. The current integrated source packages, all maintained within this repository, are:

- `tara_app`: the local app, capability registry, approval flow, Ollama lifecycle manager, conversation controls, and safe Markdown chat UI.
- `tara_router`: a deterministic local router included in this repository; it requires no API key or paid inference.
- `tara_chat`: the conversation-only specialist, kept separate from Code.
- `tara_code`: a coding specialist using the local Ollama profile; it returns review-first proposals and never executes code.
- `tara_research`: a source-first module that queries free Crossref and Wikipedia public APIs and returns links and excerpts.
- `tara_planner`: bounded plans with validated dependencies; plans are never executed.
- `tara_memory`: local SQLite memory; write and delete requests require Security review and per-request approval.
- `tara_creative`: local Ollama writing, with no paid inference provider.
- `tara_security`: deterministic policy assessment for sensitive capabilities.
- `tara_action`: local desktop and browser actions plus optional GitHub issue creation; every action is gated by TARA-Security and explicit approval, while GitHub writes also require credentials and a repository allowlist.
- `tara_voice`: optional faster-whisper transcription when compatible wheels are available; read-aloud uses installed local browser voices.
- `tara_vision`: local Ollama image analysis; images stay on the device.
- `tara_data`: deterministic, read-only CSV summaries.
- `tara_study`: optional local-first study notes, fill-in-the-blank quizzes, flashcards, and bounded revision plans.
- `tara_weather`: public Open-Meteo geocoding and weather forecasts, with attribution.
- `tara_models`: a free-first model catalogue, Gemini free-tier API adapter, BharatCode Qwen hosted inference, and local OpenAI gpt-oss via Ollama.

TARA-Handler's C++17 source is included in TARA-App. The launchers explicitly prepare its optional native diagnostic before starting the app; only the environment-diagnosis command is exposed. If CMake or a C++ compiler is unavailable, the app uses read-only Python diagnostics. GitHub issue creation remains inactive until local credentials and a repository allowlist are configured.

### Personal desktop automation

TARA can open Calculator, Notepad, and Paint, or open an HTTP(S) website in the default browser. Commands such as `Open Calculator`, `Notepad kholo`, and `Open https://example.com` are routed to TARA-Security and require a one-operation approval before launch. Each app maps to a fixed operating-system command; website addresses are validated and handed to the system browser. If an app or browser is unavailable, TARA reports that instead of claiming success.

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


## Optional BharatCode hosted model (integration planned)

**Recommended hosted model for TARA: BharatCode Qwen 3.8 27B** (`qwen-3.8-27b`). This is a hosted model accessed through BharatCode; BharatCode is the API platform, not the model itself. The shared provider adapter is implemented on the `feat/bharatcode-multi-specialist-routing` branch; its CI and target-machine verification are pending before merge.

- **Student access:** verified eligible Indian students receive up to 10,000,000 total Qwen tokens per IST day. Input, cached input, output, and reasoning tokens count; the allowance resets at midnight IST.
- **Other access:** Qwen API access is included in BharatCode Lite and Pro paid plans. DeepSeek V4.1 Flash (`deepseek-v4.1-flash`) is Pro-only; it is not part of the free student Qwen allowance.
- **Endpoint:** `https://bharatcode.ai/api/model/v1` (OpenAI-compatible). Use `qwen-3.8-27b` as the model ID.
- **Supported API routes:** `POST /responses` and `POST /chat/completions`. The Responses API supports text/image input, streaming, structured output, and caller-defined function tools.
- **Important API limits:** requests are stateless; send the required conversation history and function-call outputs with each request. `store:true`, `previous_response_id`, hosted tools, background jobs, and audio/video/file input are unsupported. Output limits include reasoning; incomplete/length responses must not be treated as complete tool calls.
- **Capacity:** student requests use shared capacity and may queue, time out, or be delayed during busy periods. The 10M/day allowance is not unlimited throughput or a service-level guarantee.
- **Security:** keep `BHARATCODE_API_KEY` on the server side, never in browser bundles, desktop frontend code, source control, or logs. Remote inference sends the submitted prompt/context (and any supported image input) to BharatCode; do not send secrets or sensitive workspace contents without explicit user consent.
- **TARA integration design:** make hosted inference an explicit opt-in provider profile. Keep local Ollama available as the local/offline option and fallback. Do not silently upload repository files, memory, desktop data, or tool output. Route tool calls back to TARA's local capability registry; validate arguments with TARA-Security and require the existing approval flow for mutations. The model must never execute host commands directly.

### BharatCode task-wise provider setup

The BharatCode adapter is shared by compatible text/image specialists. It uses the fixed HTTPS endpoint above, standard-library HTTP transport, bounded request/response sizes, disabled redirects, and redacted provider errors. No API key is stored in TOML or sent to the browser.

Set the key in the same local environment that launches TARA-App. On Windows PowerShell:

```powershell
$env:BHARATCODE_API_KEY = "your-bharatcode-key"
$env:TARA_LLM_BACKEND = "bharatcode"       # Chat: bharatcode or ollama
$env:TARA_CODE_PROVIDER = "bharatcode"     # Code: bharatcode or ollama
$env:TARA_CREATIVE_PROVIDER = "bharatcode" # Creative: bharatcode or ollama
$env:TARA_VISION_PROVIDER = "bharatcode"   # Vision: bharatcode or ollama
.\run-tara.bat
```

Each specialist is independently selectable; omit a provider variable or set it to `ollama` to keep local inference. Chat uses `BHARATCODE_MODEL`; Code, Creative, and Vision can override it with `BHARATCODE_CODE_MODEL`, `BHARATCODE_CREATIVE_MODEL`, and `BHARATCODE_VISION_MODEL`. All default to `qwen-3.8-27b`. The example TOML forwards the secret only to the selected module processes; it never contains the secret value.

- **Chat:** uses the existing bounded conversation history assembled by TARA and sends it as a stateless request.
- **Code:** sends the user's prompt and any attached source text to BharatCode only when `TARA_CODE_PROVIDER=bharatcode`. Code remains review-first; it cannot execute commands or modify files.
- **Creative:** sends the writing brief to BharatCode only when `TARA_CREATIVE_PROVIDER=bharatcode`.
- **Vision:** sends supported image data and the question to BharatCode only when `TARA_VISION_PROVIDER=bharatcode`. This transfers the images off-device; keep Ollama selected for local-only image analysis.
- **Research, Planner, Study, Handler, Security, Memory, and deterministic data/actions:** remain local or source-first. They are not silently switched to remote inference. Future AI-backed Planner/Study actions can adopt the same provider interface after their input/privacy contracts are defined.

Remote mode sends the selected specialist's submitted prompt/context (and images for Vision) to BharatCode. Do not enable it for confidential source, secrets, personal data, or workspace content unless you explicitly accept that transfer. TARA's Security and approval boundary remains local; BharatCode does not receive permission to execute local tools. A response ending with `finish_reason=length` is treated as incomplete and is never accepted as a complete answer or tool call.

To verify account access and the current model ID, call `GET https://bharatcode.ai/api/model/v1/models` with the bearer key. TARA's adapter does not assume that a student allowance guarantees immediate capacity: shared requests can queue, time out, or be rate-limited.
- **Cost classification:** free only for verified student Qwen access within its daily allowance. Lite/Pro are paid subscriptions. Do not describe all BharatCode models or all API calls as free.

Official references: [BharatCode model/API guide](https://auth.bharatcode.ai/build), [BharatCode pricing and student terms](https://www.bharatcode.ai/), and [BharatCode Terms of Service](https://auth.bharatcode.ai/terms).

The existing local Ollama profiles below remain local fallbacks and are not removed by this hosted-provider option. Model availability, IDs, student eligibility, pricing, and API capabilities can change; check BharatCode's live `GET /models` before relying on a model ID.

## Local Ollama model profiles

TARA-App is the only user-facing process. It starts or reuses local Ollama, prepares the Chat model before the interface becomes ready, and routes each request to the matching specialist and its configured model. Other specialist models download on first use.

| Specialist | Default model | Use |
| --- | --- | --- |
| Chat | `llama3.2:3b` | Local conversation |
| Planner | deterministic dependency checks | Reviewable plans; no execution |
| Creative | `llama3.2:3b` | Local writing and rewriting |
| Code | `qwen2.5-coder:3b` | Local code analysis and proposed changes |
| Vision | `gemma3:4b` | Local image understanding |

These are free-to-download model weights served locally by Ollama; no paid inference API is configured. Model names can be changed in `[ollama.models]`. On startup, TARA-App installs the Chat profile if needed and preloads it into Ollama memory, so the first chat request does not wait for model setup. Other specialist models are loaded when their tasks are selected. The Chat profile uses balanced CPU scheduling and stays loaded for 15 minutes after its last request, subject to available memory.

### Chat experience

Assistant replies render safe Markdown for headings, lists, quotes, links, inline formatting, and code blocks. HTML in model output is treated as text; links are limited to HTTP or HTTPS. Replies and code blocks can be copied. Users can edit and resend a text-only prompt or regenerate its latest answer. TARA synchronizes the edited conversation context with its local chat runtime, including after the app restarts. Prompts with file attachments cannot be edited or regenerated because attachment bytes are not stored in the local chat history. Uploads support files up to 10 MB each, with a 10 MB combined attachment limit per message.

Research uses Crossref and Wikipedia public APIs for source records. No API key is required and no paid model is called. A research query is sent to those public services when Research is selected. Voice transcription uses the optional local faster-whisper package and weights; audio is processed on-device. The launcher skips that optional package on Python 3.15 or newer, so other app features still install. Read-aloud uses only browser voices marked local.

## Target integration contracts

Adapters should expose health, capabilities, and a structured execute operation. Model providers additionally need a model catalogue, load/unload lifecycle, inference settings, cancellation, timeout, resource limits, and health reporting. Model identity and version should be recorded for each inference request.

Use a versioned request with `schema_version`, `request_id`, `session_id`, `module`, `action`, structured `inputs`, `workspace_root` when applicable, `timeout_seconds`, and `approval_token` when a mutating operation requires approval.

A result should include `schema_version`, `request_id`, `ok`, `status`, structured `data`, redacted `error`, duration, and audit references. Validate payload size, field types, allowable actions, workspace boundaries, and timeout limits before dispatch. The serialized adapter-request payload limit is 50,000,000 bytes (about 50 MB) to accommodate larger attachment-bearing requests while retaining a hard resource bound; encoded attachment data may consume extra space.

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

The launcher creates a local virtual environment, installs this repository, creates `tara-app.toml` from the example when needed, prepares the optional native Handler diagnostic, and starts TARA-App. TARA-App starts or reuses Ollama and prepares the Chat model before showing the ready message. The first launch may download Chat; other specialist models download only when that specialist is first selected.


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

The consolidated Router, Chat, Code, Planner, Memory, Creative, Security, Action, Data, Vision, Voice, and Research packages are merged into `main`. The native Handler source and on-demand adapter are included; the app exposes only environment diagnosis. GitHub issue creation requires local credentials, a repo allowlist, Security review, and one-time user approval. A final smoke run on the target computer is still needed to confirm Ollama availability and hardware-specific model performance.


## Study Mode (free and local-first)

TARA-App includes an optional, read-only Study specialist for source-grounded notes, fill-in-the-blank practice quizzes, flashcards, and bounded revision plans. It uses no paid API and does not need a model for these deterministic learning aids. Study requests are routed only when the `study.create` capability is configured. Copy the updated `tara-app.example.toml` into your local config to enable it.

- Attach UTF-8 `.txt`, Markdown, or text-based PDF notes and ask TARA to make notes, a quiz, or flashcards from them.
- Study answers derived from supplied material are marked source-grounded and include source-line hints for quiz/flashcard items. They are extracted from the source, not independently fact-checked.
- Ask for a `7-day study plan for biology` to generate a bounded plan (1–30 days) without uploading a file.
- PDF text extraction is optional: install `pip install -e '.[study]'` to add the free `pypdf` library. Scanned PDFs need OCR; OCR integration is a later batch.
- Input limits: four study attachments, 200,000 combined source characters, 200 pages per PDF, 50 quiz/flashcard items. The app's existing 10 MB combined upload limit still applies.

The first release intentionally avoids pretending deterministic sentence extraction is a full AI tutor. More advanced subject explanations, real MCQ distractors, spaced repetition, OCR, semantic search, and study progress tracking are follow-up batches.


## Free Model Hub and Weather

- **Gemini API:** when `GEMINI_API_KEY` is configured, TARA discovers the current available model list and exposes only the text models in its maintained free-tier allowlist. Free-tier quotas, eligibility, and model availability depend on the Google AI Studio project. Gemini requests send the selected prompt to Google; do not use this mode for sensitive data unless you accept that transfer.
- **OpenAI open weights:** `gpt-oss:20b` and `gpt-oss:120b` can be run through local Ollama. They are not free OpenAI API models; model weights are free, but hardware, electricity, storage, and hosting can cost money. TARA does not automatically download these large models.
- **Model Hub prompts:** ask `List all available free models`, `Use Gemini: ...`, `Use gemini-3.5-flash-lite: ...`, or `Use gpt-oss:20b: ...`. Only explicitly selected Gemini prompts go to the remote API.
- **Weather:** ask `weather in Pune` or `forecast for London for the next 7 days`. TARA uses Open-Meteo's public geocoding and forecast APIs without an API key, includes attribution, and limits response size and network timeouts. Its free endpoint is for non-commercial use and subject to provider rate limits.
- **Readable answers:** TARA normalizes excessive whitespace and bullet glyphs and uses wider answer cards, consistent line spacing, and clearer heading hierarchy.


### Configure the optional Gemini free tier (PowerShell)

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. In the same PowerShell window used to start TARA, set the environment variable: `$env:GEMINI_API_KEY = "your-key"`.
3. Start TARA normally, then ask `List all available free models` or `Use Gemini: explain photosynthesis`.

Keep the key local and never commit it. Gemini free-tier usage is subject to Google’s current model eligibility and quota. Without a key, the Model Hub still lists documented candidates but cannot verify access for your project.


## React + TypeScript frontend (migration in progress)

The maintained frontend source is in `frontend/` and uses React, TypeScript, and Vite. The migration is incremental: the existing UI remains available as a fallback until the React build is generated.

```bash
cd frontend
npm install
npm run typecheck
npm run build
cd ..
python -m pip install -e .
tara-app
```

When `src/tara_app/web/react-dist/` exists, the local server serves the compiled React UI at `/` and its hashed assets from `/assets/`. Without a build, it serves the existing static UI. The Vite development server uses `127.0.0.1:5173` and proxies API requests to the local TARA-App server on `127.0.0.1:8765`.

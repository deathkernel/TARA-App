# TARA Shared AI/Tool Ecosystem — TARA-App Integration Contract

Status: placement contract plus first implementation slice. The 30-entry machine-readable inventory is in `config/ai_tool_registry.json`; a standard-library validator and offline tests are included. A loopback-only Ollama client exists at `src/tara_app/providers/ollama.py`, with provider contracts and a fail-closed runtime manager in `src/tara_app/contracts.py` and `src/tara_app/runtime_manager.py`. `config/runtime.json` keeps Ollama disabled by default. No upstream project is installed or launched. This is a runtime foundation, not yet a complete application/UI or verified live integration.

## Goal
Make the user's 30 suggested open-source AI tools available for evaluation across the TARA ecosystem, not just TARA-Code. TARA-App is the current host application for the TARA-Code adapter. Other TARA modules should consume shared capabilities only through a versioned, least-privilege platform contract. Do not integrate TARA-Code into TARA-CHAT.

## Core principle
These repositories are not all "LLMs". They represent model runtimes, clients, coding agents, chat interfaces, RAG/workflow systems, speech tools, and image-generation tools. Register them by capability and only use one where it adds value. Avoid installing or starting all 30 processes simultaneously.

## Inventory of the 30 candidate projects
Before activation, verify repository access/ownership, latest maintenance activity/releases, license, dependencies, platform support, security notes, external service terms, and actual free-tier rules.

### Model runtimes and inference
1. Ollama — preferred first local inference adapter.
2. llama.cpp — alternate local GGUF inference backend.
3. Jan — optional desktop/local inference provider.
4. GPT4All — optional local model runtime.
5. LocalAI — optional OpenAI-compatible local API server.
6. text-generation-webui — optional self-hosted inference UI/server.
7. KoboldCpp — optional GGUF-based runtime, subject to task compatibility.
8. Hugging Face Transformers — flexible model-loading library, generally more engineering/hardware configuration.
9. vLLM — high-throughput serving option, typically for capable GPU/server deployments rather than the user's first local default.
10. Ollama Python — client library for the Ollama API, not a model/runtime itself.

### Coding agents and developer tools
11. Aider — coding assistant workflow over repositories; integrate behind review and patch controls.
12. Continue — coding assistant/provider integration candidate.
13. OpenHands — autonomous software agent; sandbox required before enabling execution.
14. Open Interpreter — command/tool agent; host execution remains disabled absent a hardened sandbox.

### Knowledge, chat, RAG and workflows
15. AnythingLLM — document knowledge and retrieval candidate.
16. Open WebUI — optional local chat UI; not a coding model.
17. PrivateGPT — local/private document retrieval candidate.
18. LibreChat — multi-provider chat UI.
19. LobeChat — chat interface and provider integration candidate.
20. Dify — application/workflow builder candidate.
21. Langflow — visual LLM workflow builder.
22. RAGFlow — retrieval-augmented generation pipeline.
23. Flowise — visual LLM app/workflow builder.
24. FastGPT — knowledge-base and workflow application.

### Speech and image-generation tools
25. whisper.cpp — local speech-to-text.
26. faster-whisper — speech-to-text backend.
27. ComfyUI — node-based image-generation workflow server.
28. Stable Diffusion WebUI (AUTOMATIC1111) — image-generation UI/API.
29. InvokeAI — image-generation workflow/UI.
30. Fooocus — image-generation interface.

## Correct placement inside the TARA architecture

**Integration rule:** do not copy or install all 30 complete applications into every TARA module. Treat upstream projects as candidate runtimes, libraries, or reference implementations. TARA-App owns the shared registry, configuration, lifecycle, permissions, and UI entry points; specialist modules consume only the capabilities they need.

| # | Repository | Correct TARA placement | Integration approach / constraint |
|---:|---|---|---|
| 1 | Ollama | TARA-App shared model runtime manager; used by Chat and other approved modules | First local inference backend; one managed service, health/model inventory and explicit model selection |
| 2 | Jan | TARA-App provider registry | Optional local provider; adapter only if stable API/automation fits, not another mandatory server |
| 3 | AnythingLLM | Chat / knowledge capability | Optional knowledge/RAG system or reference; integrate only if retrieval adds value over TARA's own layer |
| 4 | llama.cpp | TARA-App shared inference backend | Alternative local runtime for supported GGUF models; don't run redundantly with every runtime |
| 5 | Aider | TARA-Code | Coding-agent adapter behind diff review and explicit approval; no autonomous merge |
| 6 | ComfyUI | Future image/media specialist capability surfaced by TARA-App | Optional image workflow backend behind an adapter and separate resource limits |
| 7 | whisper.cpp | TARA-Chat voice input / speech-to-text capability | Local STT backend when voice input/transcription is required |
| 8 | Continue | TARA-Code / developer workflow | Optional coding-assistant integration; avoid duplicating other coding-agent features without a use case |
| 9 | Open WebUI | Reference/optional alternative chat frontend | Reuse ideas or compatible API only; don't embed a second full chat shell by default |
| 10 | GPT4All | TARA-App shared model runtime manager | Optional local runtime/provider; alternative, not always-on duplicate |
| 11 | LocalAI | TARA-App shared provider registry | Optional OpenAI-compatible local endpoint for a demonstrated provider gap |
| 12 | OpenHands | TARA-Code | High-risk autonomous coding agent; disabled until hardened OS/container sandbox and permission controls are verified |
| 13 | Open Interpreter | TARA-Code only for explicitly approved bounded tasks | Shell/computer execution disabled by default; never route arbitrary commands to host |
| 14 | Stable Diffusion WebUI (AUTOMATIC1111) | Future image/media specialist capability | Alternative image backend to ComfyUI/InvokeAI/Fooocus; don't launch all |
| 15 | text-generation-webui | TARA-App shared model runtime registry | Optional inference server; alternative to Ollama/LocalAI, not default co-running service |
| 16 | KoboldCpp | TARA-App shared model runtime registry | Optional GGUF backend for compatible local inference workloads |
| 17 | PrivateGPT | Chat / private knowledge capability | Optional local document-RAG candidate; compare privacy, ingestion and overlap first |
| 18 | LibreChat | Reference/optional alternative chat UI | Don't add a second chat frontend by default; consider only for a specific integration need |
| 19 | LobeChat | Reference/optional alternative chat UI | Alternative UI/reference, not a mandatory dependency |
| 20 | Dify | TARA-App workflow/capability orchestration, if needed | Optional workflow engine; don't duplicate native orchestration without a concrete gap |
| 21 | Langflow | TARA-App workflow capability, if visual flow authoring is needed | Optional visual workflow builder with separately scoped permissions/secrets |
| 22 | RAGFlow | Chat / knowledge retrieval capability | Optional document ingestion/RAG backend; benchmark against selected knowledge system |
| 23 | Flowise | TARA-App workflow capability, if visual flow authoring is needed | Alternative to Dify/Langflow; select one for a defined use case |
| 24 | FastGPT | Chat / knowledge retrieval capability | Optional knowledge-base/workflow candidate; compare against AnythingLLM, PrivateGPT and RAGFlow |
| 25 | vLLM | TARA-App shared inference provider for capable GPU/server deployments | Optional high-throughput backend; not default laptop/Windows runtime |
| 26 | Hugging Face Transformers | TARA-App model/provider engineering layer | Library-level integration for selected pipelines, not a standalone end-user server |
| 27 | Ollama Python | Shared provider adapter implementation | Python client for Ollama; not a separate runtime or UI |
| 28 | faster-whisper | TARA-Chat voice input / speech-to-text capability | Alternative STT backend to whisper.cpp; choose based on hardware and benchmarks |
| 29 | InvokeAI | Future image/media specialist capability | Alternative image backend; select only if its workflow fits better |
| 30 | Fooocus | Future image/media specialist capability | Optional simpler image backend; alternative, not an always-on extra service |

### Selection rules to prevent duplication

- **Shared runtime layer:** start with Ollama; add another runtime only for a demonstrated model, platform, or performance gap.
- **Chat/knowledge:** don't install AnythingLLM, PrivateGPT, RAGFlow, FastGPT and every chat UI at once. Compare retrieval, storage, privacy, licensing and APIs, then choose the smallest useful combination.
- **Coding:** keep Aider/Continue/OpenHands/Open Interpreter behind TARA-Code's adapter and review model; execution-capable agents stay off until sandbox gates pass.
- **Speech:** whisper.cpp and faster-whisper are alternative STT backends for TARA-Chat voice input.
- **Images:** ComfyUI, AUTOMATIC1111, InvokeAI and Fooocus are alternative image workflow backends; expose a selected backend through a future media capability.
- **Workflows:** Dify, Langflow and Flowise overlap. Select based on a specific workflow requirement.
- **Reference UIs:** Open WebUI, LibreChat and LobeChat should not become nested/duplicate TARA frontends by default.
- **TARA-Handler remains a deterministic native environment tool**; AI repositories do not replace or get bundled into Handler merely because they are on this list.

## Shared platform contract
Each adapter must declare:
- Stable adapter ID, version, upstream repository and exact reviewed release/commit.
- Capability and supported input/output schema.
- Licence and provenance notes, dependencies, platform/hardware requirements.
- Whether data stays local or leaves the device.
- Explicit filesystem/network/shell permissions; defaults are deny.
- Health check, bounded timeout, max payload/output, normalized error types and cancellation behavior.
- Free-tier/API quota information (if any) with verification timestamp.
- Audit/redaction rules and disable switch.
- Contract tests with mock implementations.

## Suggested first-wave priorities
1. Ollama + Ollama Python as the first local inference path.
2. Provider abstraction so additional runtimes can be substituted without application rewrites.
3. A small registry/health page in TARA-App with explicit configuration, not silent installers.
4. Whisper integration only if a TARA module needs transcription.
5. One image-generation adapter only if a TARA module needs images.
6. One RAG/workflow adapter only after use case, storage, permissions, and duplicate-function review.
7. Coding agents only after a real OS/container sandbox, approval enforcement, and security tests exist.

## Free-first and cost policy
- Local models can avoid API inference fees but need local compute, disk, electricity, and license review.
- Hosted free tiers are quota-limited and can change; verify current terms before use.
- Paid providers and external model calls are disabled unless the user opts in and sets a budget.
- Never upload private repo contents or memory to a cloud model by default.
- On quota exhaustion, stay local or return a clear unavailable state; do not silently trigger paid billing.

## Security and rollout
- Do not expose one tool's credentials, workspace, or privileges to another.
- Treat model responses, retrieved content, speech transcriptions, images/metadata, and tool output as untrusted.
- Do not enable arbitrary shell commands, silent package installation, or autonomous commits/pushes/merges.
- Keep TARA-Code's existing patch approval and fail-closed execution boundaries.
- Add mock contract tests first; enable one adapter at a time after licence/security review.
- Human review is required before merging these design changes or activating adapters.

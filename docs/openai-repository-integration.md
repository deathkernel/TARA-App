# OpenAI Repository Integration Plan for TARA

This document records the OpenAI public repositories selected for TARA and how each should be evaluated and adopted. It is an implementation manifest, not a claim that every upstream repository has already been embedded or that every model is free to run on all hardware.

## Integration principles

- Keep TARA local-first and provider-neutral. Local inference must continue working without an OpenAI API key.
- Prefer stable package dependencies or narrow adapters over copying whole repositories.
- Verify each upstream license, maintenance status, supported runtime, security requirements, model terms, and hardware needs before enabling code.
- Make network-hosted inference opt-in and configuration-driven; a free SDK does not make hosted inference free.
- Do not execute model-generated shell commands on the host. Coding-agent execution requires a real OS/container sandbox, explicit approvals, resource limits, audit events, and cancellation.
- Research/education repositories are references or optional labs, not production runtime dependencies.
- Keep optional heavyweight features out of the core install. Fail closed when a dependency or runtime is not installed.

## Selected repository inventory

| Category | Upstream repository | Intended TARA use | Adoption path | Free/local notes | Priority |
|---|---|---|---|---|---|
| Open-weight language model | https://github.com/openai/gpt-oss | Optional local model profile and model metadata | Keep the model artifact/runtime separate; evaluate Ollama/runtime compatibility, quantization, license and hardware before listing a profile as runnable | Weights are downloadable; local execution needs compatible hardware and storage | P0 |
| Agent SDK (Python) | https://github.com/openai/openai-agents-python | Optional agent workflow adapter | Map agent/tool calls to TARA's versioned capability contracts; preserve Security approval gates | SDK is open source; inference provider may be paid or local depending on configured endpoint | P0 |
| Agent SDK (TypeScript) | https://github.com/openai/openai-agents-js | TypeScript workflows where useful | Optional frontend/backend integration; do not duplicate the Python orchestration path without a clear use case | SDK is free; runtime inference provider varies | P1 |
| Coding agent | https://github.com/openai/codex | Coding workflow research and possible isolated coding adapter | Evaluate sandboxing, authentication and model requirements; do not give the agent unrestricted host access | Requirements depend on deployment/model access | P0 review |
| Speech-to-text | https://github.com/openai/whisper | Optional local transcription | Prefer the existing TARA Voice interface; keep runtime/dependencies optional and test supported Python/platform combinations | Local inference possible; model weights and compute are required | P1 |
| Image/text similarity | https://github.com/openai/CLIP | Optional local image/text retrieval | Add an isolated vision-search adapter; do not replace existing image-understanding features | Local inference possible; model weights and compute required | P2 |
| Python API SDK | https://github.com/openai/openai-python | Optional OpenAI-compatible remote provider integration | Provider adapter only; keys in local secret store/environment, never logs | SDK free; hosted API can cost money | P2 |
| JavaScript API SDK | https://github.com/openai/openai-node | Optional Node/TypeScript service integration | Use only where a Node service actually exists; avoid adding a second backend stack just for the SDK | SDK free; hosted API can cost money | P2 |
| MCP integrations | https://github.com/openai/mcp-extensions | Ideas/examples for external tool integrations | Inspect each extension and add only allowlisted, least-privilege adapters behind capability approval | Public repository; each integration has its own dependencies and access needs | P1 review |
| Guardrails (Python) | https://github.com/openai/openai-guardrails-python | Optional input/output safety checks | Evaluate alongside TARA Security; normalize results into TARA's policy contract and avoid duplicate conflicting policy layers | Library is free; checks/integrations may need external services | P1 |
| Guardrails (JS) | https://github.com/openai/openai-guardrails-js | JS safety checks if a JS service uses them | Keep optional; do not duplicate Python checks without an explicit boundary | Library is free; integrations vary | P2 |
| Evaluations | https://github.com/openai/evals | Regression and response-quality test cases | Adapt useful tests to local deterministic fixtures; keep network/API-dependent tests marked separately | Tooling is open source; some evaluations require hosted models | P1 |
| Cookbook | https://github.com/openai/openai-cookbook | Reference implementations | Extract patterns into small reviewed examples; never import the entire cookbook as a dependency | Examples free; some use paid or online APIs | P1 reference |
| Tokenization | https://github.com/openai/tiktoken | Token estimates for supported encodings | Optional utility; label estimates by tokenizer/model instead of assuming every provider uses this tokenizer | Local library | P2 |
| 3D research | https://github.com/openai/shap-e | Optional experimental 3D asset generation | Separate experimental extra; no core dependency until use case, license and compute requirements are tested | Local compute and model weights required | P3 |
| Language-model research | https://github.com/openai/gpt-2 | Historical/research model experiments | Reference or test fixture only; archived upstream | Research code, old model; not a default production model | P3 |
| RL education | https://github.com/openai/spinningup | Tutorials and algorithm research | Documentation/lab only; separate environment from main application | Educational code; training compute required | P3 |
| RL environments | https://github.com/openai/gym | Legacy research reference | Do not adopt as a new production dependency because the repository is archived; evaluate maintained alternatives such as Gymnasium separately | Archived upstream | P3 |
| Procedural RL environments | https://github.com/openai/procgen | Research-only agent training environments | Separate optional lab; verify platform compatibility and maintenance | Research code; compute required | P3 |
| Go SDK | https://github.com/openai/openai-go | Future Go services only | Defer unless a TARA service is intentionally written in Go | SDK free; hosted API can cost money | P3 |
| .NET SDK | https://github.com/openai/openai-dotnet | Future .NET services only | Defer unless TARA has a .NET service | SDK free; hosted API can cost money | P3 |
| Java SDK | https://github.com/openai/openai-java | Future Java services only | Defer unless TARA has a Java service | SDK free; hosted API can cost money | P3 |
| GitHub Actions | https://github.com/openai/codex-action | Optional CI coding-agent experiments | Only in isolated, explicitly configured workflows with secret-scope and write-permission review | Model credentials/configuration may be required | P2 review |
| CLI | https://github.com/openai/openai-cli | Command-line API workflows | Verify current maintenance and purpose before adopting; CLI is not a required app runtime | API access may be paid | P3 review |
| Code security | https://github.com/openai/codex-security | Security research/evaluation | Inspect actual README, license, data-flow, and execution model before deciding; do not assume it is a drop-in scanner | Requirements must be validated | P2 review |
| Multi-agent example | https://github.com/openai/swarm | Concepts and migration reference | Educational/reference only unless maintenance and production suitability are confirmed; prefer the maintained Agents SDK where appropriate | Open-source example; upstream describes an educational purpose | P3 |
| Frontier evaluations | https://github.com/openai/frontier-evals | Advanced evaluation research | Separate evaluation lab; inspect data/model requirements before adapting | Public code; requirements vary | P3 |

## Recommended implementation batches

### Batch 1 — Low-risk integration foundation (P0)
1. Add this inventory to the project documentation.
2. Define a provider/model capability map without installing upstream projects as runtime dependencies.
3. Add contract-level tests for optional capabilities being unavailable when their dependencies/configuration are absent.
4. Document model licensing, hardware and provider-cost labels in the model catalogue.
5. Keep gpt-oss optional until target-machine hardware and supported runtime are verified.

### Batch 2 — Agent and safety adapters (P0/P1)
1. Prototype one Python Agents SDK adapter behind TARA's capability registry.
2. Translate tool requests through TARA's contracts rather than executing arbitrary agent tools directly.
3. Evaluate Guardrails as an optional policy signal, not a replacement for TARA Security.
4. Add tests for disabled capabilities, timeout, malformed output, denied approval, and unavailable providers.
5. Review Codex only after a real sandbox runner exists.

### Batch 3 — Existing local modality features (P1/P2)
1. Keep TARA Voice's existing interface and optionally expose Whisper as a selectable backend.
2. Add CLIP as a separate image/text search capability instead of replacing image understanding.
3. Keep tiktoken optional and record the tokenizer used for each estimate.
4. Use relevant Evals/Cookbook examples to add local regression fixtures.

### Batch 4 — Optional network and CI providers (P2)
1. Add OpenAI Python/Node SDKs only as optional provider extras.
2. Keep API key configuration disabled by default and redact secrets from logs.
3. Test remote-provider behavior using mocks; live API tests must be opt-in and may incur cost.
4. Only trial codex-action in a dedicated repository/workflow with least-privilege permissions.

### Batch 5 — Research-only modules (P3)
Keep Shap-E, GPT-2, Spinning Up, Gym, Procgen, Swarm and Frontier Evals outside the normal install. Revisit them only for a concrete research objective. Do not bring archived/educational repositories into the runtime just to claim that all repositories are integrated.

## Definition of done for each adapter

- Upstream repository and license reviewed; version/commit pinned.
- Optional dependency group, not a core dependency, unless proven essential.
- Versioned TARA contract and explicit capability registration.
- No hidden downloads, provider activation, external network calls, or mutations on import/startup.
- Timeouts, cancellation, payload validation, error redaction, resource limits, and audit events.
- Unit tests with mocked providers plus feature-unavailable tests.
- Documentation of local/remote mode, hardware/model downloads, provider cost, license and known limitations.
- CI passes before merge. No automatic merge of code generated or modified by an agent.

## Current scope note

This manifest is the plan for adoption. It does not mean all repositories are embedded in TARA or that optional features have been implemented. Implementation should proceed batch by batch after tests and upstream review, keeping the current local-first app functional throughout.

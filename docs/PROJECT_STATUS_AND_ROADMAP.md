# TARA-App: Project History, Current Status & Roadmap

> **Purpose:** This is the handover document and working source of truth for anyone joining TARA-App—including a new developer, a reviewer, or the daily scheduled development task.
>
> **Last reviewed:** 2026-11-12  
> **Repository:** [deathkernel/TARA-App](https://github.com/deathkernel/TARA-App)  
> **Default branch:** `main`  
> **Status rule:** “Implemented in code/docs” is not the same as “verified on a real machine.” Do not claim tests, runtime checks, UI QA, or integrations passed unless there is current evidence for the exact commit.
>
> **Feature status table:** See [REMAINING_FEATURES.md](REMAINING_FEATURES.md) for the numbered remaining-features list with accurate Implemented / Foundation / Pending verification / Pending / Blocked labels against current `main`.

## 0. Current stabilization batches (2026-11-12)

### Batch 1 — MCP integration catalogue (merged)

PR [#103](https://github.com/deathkernel/TARA-App/pull/103) merged as
`1d4f63d24ba3082789bafa6e8a58fa264dcafdf5`. It adds the free-first,
read-only integration catalogue, a same-origin metadata endpoint, and the
local Integrations panel. Discovery does not install, launch, enable, or
execute integrations and does not enable writable tools.

**Verification:** PR head `b22694b`, merged as `1d4f63d`, passed workflow
run [#1878](https://github.com/deathkernel/TARA-App/actions/runs/43191279337):
Python tests, source compilation, frontend type-check/build, and Ubuntu +
Windows native Handler build/risk-test jobs.

### Batch 2 — MCP audit and approval security (merged)

PR [#104](https://github.com/deathkernel/TARA-App/pull/104) merged as
`5dd92f12080776174fbc8444aff595863876191f`. It consolidates MCP audit
events onto the existing redacting `JsonlAuditLog`, adds a 1 MiB active log
with one rotated backup and a 4 KiB event bound, and records approval and
tool-dispatch lifecycle metadata using digests rather than raw tokens,
sessions or arguments.

The exact canonical JSON argument snapshot that was approved is the one sent
to the gateway. Approval issuance and pre-dispatch audit failures fail closed;
audit health is marked degraded on sink failure. No HTTP MCP execution
endpoint was introduced, and writable tools remain blocked.

**Verification:** workflow
[#1911](https://github.com/deathkernel/TARA-App/actions/runs/43192869106)
passed 441 Python tests, frontend build, Windows native Handler and Ubuntu
native Handler.

### Batch 3 — Premium developer workspace (active)

The active branch is `codex/premium-workspace-ui-bulk`. It replaces the
minimal React chat prototype with a premium three-pane developer workspace
inspired by modern coding-agent desktop layouts:

- Left session sidebar with search, recent sessions and specialist task starters.
- Main conversation workspace with Markdown/code rendering, attachment chips,
  drag-and-drop uploads, selected skills, edit/regenerate/copy, approval cards
  and local read-aloud.
- Session search plus explicit JSON export and confirmed local deletion.
- Right inspector for specialist health, OmniRoute routes and read-only MCP
  integration metadata.
- Session activity panel and a visibly locked terminal state.
- Premium graphite/champagne visual system, animated primary buttons, subtle
  hover elevation, status breathing, message/panel entry motion, and a
  reduced-motion override.
- Responsive layout, keyboard shortcuts, focus styling and polite live updates.

The React workspace is selected by default when compiled assets exist. The
Windows and Unix launchers attempt to build it when Node.js/npm is available;
the static UI remains a fallback and can be forced with
`TARA_ENABLE_REACT_UI=0`.

**Safety boundary:** the terminal is not an executable shell. No file editor,
diff apply, Git mutation, live preview or parallel worktree controls are
exposed until their backend contracts and security prerequisites exist. Code
execution remains blocked pending a real OS/container sandbox.

**Verification still required:** latest branch CI, Windows target-machine
launch, and desktop/mobile browser visual and accessibility QA. Motion has
been limited to transform/opacity and short transitions, but real-device
performance and screen-reader behavior still require browser validation.

### Next dependency-ordered work

1. Finish the React workspace regression checks and confirm all CI jobs pass.
2. Run browser QA at desktop and mobile widths; verify launchers build the React
   assets and the static fallback still works without Node.js.
3. Add a reviewed code-diff presentation contract before building any editor,
   patch-apply or Git controls.
4. Trace runtime, orchestrator, application-service and facade ownership before
   consolidating live paths.
5. Add bounded cancellation/output tests at external adapter and gateway
   boundaries.

## 1. Start here

### Repository boundary

`deathkernel/TARA-App` is the only active development repository for TARA. The user has deleted the other TARA model repositories. All remaining specialist/model integrations, adapters, runtime code, tests, and documentation must be implemented and maintained inside this repository. Do not plan work that requires cloning, importing, or coordinating with deleted sibling repositories. Any legacy references to sibling repositories are historical/contextual only unless the user explicitly restores one.

TARA-App is the **user-facing host application and integration layer** for the TARA ecosystem. It is not itself an AI model. Its job is to provide one interface for chatting, using specialist capabilities, reviewing proposed code changes, and managing approved local actions. OmniRoute is the only language-model gateway; it owns underlying provider/model selection.

The intended design keeps these concepts separate:

- **App:** TARA-App, the UI, settings, sessions, and orchestration.
- **Model:** model weights or a remotely hosted model, with its own identity and version.
- **Gateway/provider:** OmniRoute exposes an OpenAI-compatible API and routes requests to configured model providers. TARA does not directly invoke Ollama or Gemini for language-model inference.
- **Specialist/module:** a task-specific capability such as Chat, Code, Research, Study, Vision, or Handler.
- **Tool/action:** a bounded operation a specialist may request; it is not automatically authorized just because a model requested it.

### Non-negotiable safety rules

1. Never execute model-generated shell commands directly on the host.
2. Code proposals are not permission to write files, install packages, run tests, or commit.
3. Do not call path checks alone a sandbox. Coding execution stays disabled until a real OS/container isolation boundary and its tests exist.
4. Unknown capabilities, missing dependencies, unsupported versions, audit failures, and missing approvals must fail closed.
5. Mutations require explicit, scoped approval; no hidden writes and no automatic Git merge.
6. Treat repository contents, model responses, tool output, and diagnostics as untrusted data—not instructions.
7. Keep credentials out of source, logs, PR descriptions, and model prompts. The OmniRoute gateway and its connected providers must be explicitly configured; prompts and supplied content may leave the device depending on the selected route.
8. Record exact verification evidence. A planned test, a passing unit test, a CI badge, and a successful target-machine smoke test are different things.

## 2. What exists today

The repository README describes a consolidated Python monorepo with a local app, deterministic router, specialist packages, model/runtime code, and optional integrations. The architecture and adapter documents also make clear that some interfaces are still foundations or injected boundaries—not proof that all sibling repositories are connected end to end.

Use these status labels carefully:

- **Documented/implemented:** repository documentation describes the feature as present; still check current code and tests before changing it.
- **Foundation/partial:** contracts or a first implementation slice exists, but real end-to-end integration is incomplete.
- **Pending verification:** requires a current test run, UI/browser check, target-machine run, or external integration proof.
- **Not enabled by design:** intentionally unavailable until security prerequisites are met.

For the numbered remaining-features inventory (items 1–42), use [REMAINING_FEATURES.md](REMAINING_FEATURES.md).

### 2.1 Capabilities described in the main README

| Area | Current documented scope | Important limit / verification gap |
|---|---|---|
| App and launchers | Python app; Windows `run-tara.bat`; Linux `run-tara.sh`; local configuration from `tara-app.example.toml` | Windows/macOS/Linux launchers are documented; fresh installation and launch still need target-machine smoke tests on each supported target. |
| Chat UI | Markdown replies, safe link handling, copy, edit/resend, regenerate, conversation context | Attached-file prompts have editing/regeneration limitations; browser visual QA is not established by docs alone |
| Router and specialists | Local deterministic Router; Chat, Code, Planner, Creative, Security, Action, Memory, Research, Data, Vision, Voice, Study, Weather and Models areas are documented | Confirm each route and dependency against current code/tests; do not infer all are production-ready from the module list |
| LLM inference | Chat, Code, Vision, Creative, and Model Hub are routed through OmniRoute; direct Ollama/Gemini fallback is disabled in the launcher runtime | Gateway connectivity, provider routing, quotas, model IDs, and first responses need end-to-end verification |
| Model Hub | Catalogue and generation use OmniRoute `GET /v1/models` and `POST /v1/chat/completions` | Model availability, cost, quotas, and data handling depend on providers configured inside OmniRoute |
| Research | Crossref and Wikipedia public APIs, returning source links/excerpts | Network-dependent; sources and output still need user review |
| Memory | Local SQLite memory with Security review/approval for writes/deletes | Re-check persistence, migration, retention and approval behavior in tests |
| Code | Review-first plans/proposals and adapter contracts | **No generated-code execution or workspace mutation** until real sandboxing and approval enforcement are implemented and tested |
| Handler/actions | Native C++17 Handler source; read-only environment diagnostics; optional Python diagnostic fallback; approved fixed desktop/browser actions documented | Verify native build/fallback on Windows, macOS and Linux; GitHub issue creation requires credentials, allowlist and approval |
| Data / Study / Weather | Read-only CSV summaries; source-grounded study notes, quizzes, flashcards, bounded plans; Open-Meteo weather | Study OCR, semantic retrieval, spaced repetition and progress tracking are described as future work; weather is network/rate-limit dependent |
| Voice / Vision | Optional faster-whisper transcription remains local; Vision sends supplied images through OmniRoute | Vision route must support image input; image data may be forwarded to a cloud provider configured in OmniRoute |
| React frontend | `frontend/` uses React, TypeScript and Vite; migration is incremental with existing UI fallback | Build/typecheck and actual browser QA are required; a successful CSS commit is not proof of pixel parity or full frontend migration |

### 2.2 Architecture foundations recorded in the docs

The repository also documents a lower-level integration foundation:

- A versioned capability request/response contract, policy-gated orchestrator, explicit capability allowlist, registered handlers, and redacting JSONL audit sink.
- A headless application service that coordinates runtime/catalogue/session/audit/capability components.
- Injected `TaraChatAdapter` and `TaraCodeAdapter` boundaries.
- A machine-readable AI/tool registry and a standard-library validation path.
- Optional provider SDK, guardrail/MCP, media and sandbox capability boundaries.

**Important caveat:** `docs/APP_SERVICE_AND_ADAPTERS.md` explicitly says the service is headless and does not prove sibling repositories are wired into a runnable app. It lists binding the actual Chat/Code engines, implementing the constrained Handler subprocess adapter, adding cancellation/timeouts/bounded execution, and connecting a UI/API entry point as remaining work. `docs/ARCHITECTURE.md` likewise identifies real sandbox execution, persistent permission UI, real specialist adapters, and full application UI as follow-up work. Resolve these gaps with code and evidence rather than treating contracts as completed integrations.

## 3. Recent history: what happened before

This is a concise history of significant milestones visible in the repository's commit history and existing docs. It is not a claim that every feature has been re-run on the current machine.

| Milestone | What changed | What it means now |
|---|---|---|
| PR #15 — OpenAI repository integration plan | Added a repository integration plan | Useful planning context; verify current implementation separately |
| PR #19 — optional voice/vision adapters | Defined optional media adapter boundaries and tests | Adapter foundations exist; live media behavior still needs environment-aware verification |
| PR #20 — optional provider SDK boundaries | Added opt-in OpenAI Responses adapter/provider boundary | Opt-in provider support must stay explicit; do not require provider SDKs for the local-first base install |
| PR #21 — guardrails/MCP boundaries | Added fail-closed optional guardrail boundary and tests | A boundary is not permission to enable arbitrary tools; preserve least privilege |
| PR #22 — offline evaluation/research boundaries | Added deterministic offline evaluation harness, tests, optional tokenizer extra, and research-only boundaries | Keep offline evaluation deterministic and optional dependencies isolated |
| PR #23 — fail-closed coding sandbox capabilities | Added enforcement for declared sandbox capabilities and tests | Capability gates are valuable, but **not equivalent to a real OS/container sandbox** |
| PR #24 — structured answers and monochrome chat UI | Improved structured responses and chat styling | UI changes need regression and browser verification |
| PR #25 — chat workspace redesign | Redesigned sidebar, conversation area, welcome state, messages, composer and responsive CSS | CSS redesign is merged; visual/browser QA and any remaining parity work are still to be evidenced |
| [PR #26 — living project roadmap](https://github.com/deathkernel/TARA-App/pull/26) | Added newcomer-friendly history, dependency-ordered roadmap, and scheduled-task evidence rules | Merged as `4d4c225aeba422cd30dfc272ca67d32bba942129` |
| [PR #27 — structured TARA answers](https://github.com/deathkernel/TARA-App/pull/27) | Added task-adaptive response guidance and focused answer-style tests; fixed a syntax error found by CI before merge | PR CI passed on head `dd2f87295c6be934f867e96b4976dc592c575447`; merged as `c8b484c977ca31ac4f8396bd20c090fe580299ea` |
| [PR #34 — drop floating pet](https://github.com/deathkernel/TARA-App/pull/34) | Restored the normal browser UI as the default Windows launcher and documented that the floating pet is no longer a product goal | Merged as `1bf4fdff00d748acecbba4e50cda7483f82b9f4f`; all 5 GitHub Actions jobs passed on PR head `0eff1fa8b0e1d4c99f964ccdc08ad600eb153c82` |
| [PR #50 — native command risk](https://github.com/deathkernel/TARA-App/pull/50) | Mutating native commands stay high-risk even with `-v` / `--version` flags | Merged 2026-11-03 |
| [PR #51 — session lifecycle](https://github.com/deathkernel/TARA-App/pull/51) | Atomic chat turns + opt-in session retention | Merged; on `main` as of `c45f4c3` |
| [PR #52 — local repository audit](https://github.com/deathkernel/TARA-App/pull/52) | Added a read-only local repository audit to Chat and CLI; hardened path handling, scan failures, routing and output bounds | Merged as `10c90ab`; all four CI jobs passed on rebased head `d847623` (run #41792860679). Target-machine and browser smoke tests remain pending. |
| [PR #60 — MCP foundation](https://github.com/deathkernel/TARA-App/pull/60) | Added an opt-in MCP registry, allowlisted stdio gateway, bounded tool discovery, error-aware results and operation-bound one-shot approvals | Merged as `4e8bdd8`; all four CI jobs passed on head `d218d0b` (run #41793747500): 320 Python tests, frontend build, Windows and Ubuntu Native Handler. MCP remains disabled by default and is not yet wired into Chat UI/tool-loop. |

PR #40 was closed as superseded by #52; PR #48 was closed because its changes are already present on `main`. PRs #41–#43 were deferred until the active-runtime integration in issue #62; their branch commits are preserved for a later port.

Useful history links:

- [PR #15 commit](https://github.com/deathkernel/TARA-App/commit/c491b5ca29226c8c3a0a176fe1b65ab3a7d84fa5)
- [PR #19 commit](https://github.com/deathkernel/TARA-App/commit/8c95dd8d0e352db57d8daf07aa36218c5192cca6)
- [PR #20 commit](https://github.com/deathkernel/TARA-App/commit/461f68b40070200f84acab757ac216b20c569754)
- [PR #21 commit](https://github.com/deathkernel/TARA-App/commit/df2a5c9fbe1940aad4f7f4ac36e8e453cbab3cd4)
- [PR #22 commit](https://github.com/deathkernel/TARA-App/commit/3a836f16d7f2b6aba8baf2e46f50c7f27b3b07c4)
- [PR #23 merge commit](https://github.com/deathkernel/TARA-App/commit/9b1b1c7a20e2955db0ddffac4bc5939a873b8be7)
- [PR #24 commit](https://github.com/deathkernel/TARA-App/commit/34da3dc38b5b2d7b9fd3bf7d423d42faddcf18d3)
- [PR #25 commit](https://github.com/deathkernel/TARA-App/commit/c65f2ed2c980aa457b847bbb75ce768e002f5f44)
- [PR #26 merge commit](https://github.com/deathkernel/TARA-App/commit/4d4c225aeba422cd30dfc272ca67d32bba942129)
- [PR #27 merge commit](https://github.com/deathkernel/TARA-App/commit/c8b484c977ca31ac4f8396bd20c090fe580299ea)

## 4. What is still left

See **[REMAINING_FEATURES.md](REMAINING_FEATURES.md)** for the full numbered table (items 1–42) with current status labels.

### Product direction decision — floating pet dropped

The floating desktop pet is no longer a product goal. Do not spend future roadmap or scheduled development work on pet animations, pet chat panels, pet toolbars, or pet-specific overlay behavior. PR #32 was closed without merging. The existing pet implementation from PR #31 remains in the repository for now, but the default Windows launcher must open the regular browser UI. Removing the legacy optional pet code entirely is separate cleanup and should only be done in a dedicated reviewed change if requested.

This roadmap is dependency-ordered. The daily development task should deliver a coherent, reviewable batch of multiple eligible items per run, avoid duplicate work, and update this document with evidence after meaningful progress.

### P0 — Establish a trustworthy baseline

- [x] Run the Python test suite and record the exact command, environment, pass/fail counts and failures. **Evidence:** `python -m unittest discover -s tests -v` — 320 tests passed in 2.880s on Python 3.11.17 in run [#41793747500](https://github.com/deathkernel/TARA-App/actions/runs/41793747500), head `d218d0b`; its source tree is identical to current `main` merge commit `4e8bdd8`. Local target-machine run remains pending.
- [x] Run frontend install/typecheck/build where lockfile and package scripts support it; record exact results. **Evidence:** frontend build passed in run [#41793747500](https://github.com/deathkernel/TARA-App/actions/runs/41793747500) on head `d218d0b`, whose source tree matches current `main` commit `4e8bdd8`. Browser QA remains pending.
- [x] Inspect current GitHub Actions/CI status for the current source tree. **Evidence:** run [#41793747500](https://github.com/deathkernel/TARA-App/actions/runs/41793747500) passed all four jobs on PR head `d218d0b`; its tree is identical to current `main` merge commit `4e8bdd8` (Python tests, Windows native Handler, Ubuntu native Handler, frontend build).
- [ ] Do a local launch smoke test: app starts, health/status is truthful, a chat request completes, and failures are surfaced accurately.
- [ ] Perform browser QA on the actual UI at desktop and narrow/mobile widths; compare the ChatGPT-inspired layout without claiming pixel parity in advance.
- [ ] Reconcile README claims with architecture/adapter docs so “implemented,” “partial,” and “pending verification” are consistent.
- [ ] Keep a record of any blocked checks and the specific environment or permission needed to finish them.

### P1 — Finish the application integration path

- [ ] Connect the headless application service to a stable local UI/API entry point.
- [ ] Bind the actual TARA-Chat engine through the versioned Chat adapter and verify a real end-to-end chat request.
- [ ] Bind TARA-Code planning/review through its adapter; keep proposed changes as data until a secure patch-review workflow exists.
- [ ] Specify and implement the narrow TARA-Handler subprocess protocol with fixed arguments, `shell=False`, timeouts, bounded output and an explicit command allowlist.
- [ ] Add request cancellation, timeouts, bounded execution and graceful shutdown for injected engines and provider calls.
- [ ] Verify runtime lifecycle behavior: health checks, load/unload, missing model/provider, download failure, resource limits, concurrent requests and recovery.
- [x] Finish session persistence policy: define retention/deletion defaults, migration strategy, and app-level configuration wiring. **Code:** opt-in SQLite, atomic turns, retention (PR #51). Default remains memory-only; target-machine verification still open.
- [x] Ensure approvals are visible, scoped to one operation, expire/reject reuse, and cannot be bypassed by unknown capability names or audit failures. **Code:** orchestrator pending-approval path; UI verification still open.

### P1 — Coding safety (blocking before execution is enabled)

- [ ] Choose a real OS/container sandbox design with filesystem, network, process, CPU, memory and time limits.
- [ ] Keep the host executor disabled until the sandbox boundary is implemented and tested; path validation alone is insufficient.
- [ ] Add adversarial tests for traversal, symlinks/reparse points, hostile repository instructions, secrets, network access, resource exhaustion, timeout and malformed tool output.
- [ ] Make diff preview, approval, patch application and test execution distinct, auditable operations.
- [ ] Never auto-merge a code change. A green test suite does not replace human review or repository protection.

### P2 — Complete the user experience and release

- [ ] Finish the React + TypeScript migration only after typecheck/build and browser smoke tests pass; retain the existing UI fallback until the migration is verified.
- [ ] Test responsive layout, keyboard navigation, focus states, accessibility, loading/error/empty states, message editing/regeneration and code-copy behavior.
- [ ] Test local Voice/Vision dependencies and graceful fallback on supported Python versions in Windows/macOS/Linux environments.
- [ ] Expand Study Mode only with tests and clear source-grounding: OCR/scanned PDFs, stronger question generation, spaced repetition and progress tracking.
- [ ] Verify Windows/macOS/Linux installation paths, optional native Handler compilation and Python diagnostic fallback.
- [ ] Complete release packaging, versioning, installation notes and a target-machine acceptance checklist.

### P3 — In-repository ecosystem and optional tools (only after core contracts are stable)

- [ ] Inventory the specialist packages and runtime adapters already inside this repository: entry point, dependencies, licence, tests and verification status.
- [ ] Complete versioned adapter contracts between in-repository specialists; avoid private cross-repository imports.
- [ ] Verify each specialist independently with contract tests, a health check and one end-to-end workflow.
- [ ] Evaluate optional AI/developer tools one at a time. Confirm maintenance, licence, platform support, real free-tier terms and security before activation.
- [ ] Verify OmniRoute provider configuration, data-transfer terms, quotas, and model availability before enabling a route for sensitive work.

## 5. Recommended execution order

Use this sequence unless fresh repository evidence shows a more urgent blocker:

1. **Baseline tests and CI** — know what currently passes before making broad changes.
2. **Resolve documentation/status contradictions** — keep the handover accurate.
3. **UI/API entry point and end-to-end smoke test** — turn service foundations into a usable app path.
4. **Real Chat adapter integration** — verify one complete specialist path.
5. **Code adapter and secure sandbox design** — proposals first; execution remains off until proven safe.
6. **Handler subprocess boundary, timeouts and cancellation.**
7. **Runtime lifecycle, persistence and approval UX.**
8. **React/browser QA and Windows/macOS/Linux smoke tests.**
9. **In-repository specialist verification and optional provider/tool evaluation.**
10. **Release readiness and acceptance checklist.**

The order can change if the current CI or code inspection identifies a confirmed blocker. Explain why in the PR and update the checklist here.

## 6. Daily development task: operating contract

The scheduled task should read this file **and** the current source/tests before choosing work. This file is a living status map, not a substitute for inspecting code.

For each daily run:

1. Fetch latest `main`, recent commits, open PRs/issues and current CI/check results.
2. Read this roadmap, [REMAINING_FEATURES.md](REMAINING_FEATURES.md), and relevant implementation/test/docs files. Pick a coherent batch of multiple high-value, dependency-eligible unchecked items or subtasks; keep the batch reviewable and avoid unrelated scope.
3. Check for overlapping branches/PRs first. Do not create duplicate work.
4. Implement production code plus regression tests where appropriate; update user docs/config only as needed for the batch.
5. After merge-ready work, update status labels in REMAINING_FEATURES.md and checklist items here with evidence (commit SHA, CI run, or explicit “not verified on machine”).

## 8. Related documentation

- [Remaining features status table](REMAINING_FEATURES.md)
- [Main README / setup guide](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Integration checklist](INTEGRATION_CHECKLIST.md)
- [Application service and adapters](APP_SERVICE_AND_ADAPTERS.md)
- [Integration contracts](INTEGRATION_CONTRACTS.md)
- [Security policy](SECURITY.md)
- [TARA Code adapter](TARA_CODE_ADAPTER.md)
- [TARA Code adapter test matrix](TARA_CODE_ADAPTER_TEST_MATRIX.md)
- [AI/tool ecosystem inventory](TARA_AI_TOOL_ECOSYSTEM.md)
- [Native Handler integration](native-handler.md)
- [Runtime and development option notes](runtime-evaluation.md)

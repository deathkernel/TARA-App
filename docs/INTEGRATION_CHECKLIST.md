# TARA-App Integration Status

## Consolidated in the draft

- [x] Keep Chat and Code as separate specialists behind one local app and deterministic router.
- [x] Package Router, Chat, Code, Planner, Memory, Security, Research, Action, Creative, Data, Vision, Voice, Study, Weather, and Models in TARA-App.
- [x] Keep inference on local open-weight Ollama models; start the Ollama service and pull a specialist model only when that capability is used.
- [x] Bound Code output to reviewed proposals; do not execute generated commands or modify workspaces.
- [x] Gate Memory writes/deletes, allowlisted desktop/browser actions, and GitHub issue creation behind Security assessment and one-time approval.
- [x] Show one-time approval details and Approve once / Cancel controls in the chat UI; do not persist approval tokens in browser storage.
- [x] Protect against duplicate in-flight requests and support cancellation of active Chat, Code, and Handler process trees.
- [x] Stop new orchestration/approval work during shutdown and cancel active specialist process trees before closing the local server.
- [x] Attach bounded files through the chat composer and route supported media/source files to the matching specialist.
- [x] Display local model-pull progress and prevent conflicting model lifecycle actions while a pull is active.
- [x] Bound concurrent local Ollama inference to one active request by default (configurable to two) across Chat, Code, Creative and Vision.
- [x] Retry local Ollama startup before model ensure, pull, preload, unload and remove operations when the service is unavailable.
- [x] Expose browser-local read-aloud controls for TARA Voice responses.
- [x] Wire opt-in SQLite session persistence through the trusted TOML runtime config, with bounded retention and schema-version checks.
- [x] Enforce Code, Vision, Voice, and Data attachment limits before dispatch; keep Code execution disabled.
- [x] Keep Research on free Crossref/Wikipedia public APIs and disclose when a selected query leaves the device.
- [x] Include native TARA-Handler C++17 source and an explicit pre-launch build step; expose only read-only environment diagnosis.
- [x] Keep a read-only Python diagnostic fallback when a C++ toolchain is unavailable.
- [x] Provide one-command Windows and macOS/Linux launchers.
- [x] Build the Python package, React frontend, and native Handler in GitHub Actions on Windows and Linux. The macOS launcher remains a separate target-machine verification item.

## User-machine/release steps

- [ ] Run the launcher on the target computer and confirm Ollama starts, the selected local model downloads, and a first response completes within the machine's available RAM/VRAM.
- [ ] Verify actual local Chat/Code/Voice/Vision/Study workflows with installed models and real files; CI contract tests use mocked model transports.
- [ ] Perform browser QA for attachments, approval actions, model-pull progress, and read-aloud controls at desktop and narrow widths.
- [ ] If GitHub Actions are enabled, set the local token and explicit repository allowlist; no credential is stored in the repository.
- [ ] Review the bulk feature branch and any resulting PR; merge only with explicit user approval and required checks green.
- [ ] Create a release after the user-machine smoke run.

# TARA-App Integration Status

## Consolidated in the draft

- [x] Keep Chat and Code as separate specialists behind one local app and deterministic router.
- [x] Package Router, Chat, Code, Planner, Memory, Security, Research, Action, Creative, Data, Vision, and Voice in TARA-App.
- [x] Keep inference on local open-weight Ollama models; start the Ollama service and pull a specialist model only when that capability is used.
- [x] Bound Code output to reviewed proposals; do not execute generated commands or modify workspaces.
- [x] Gate Memory writes/deletes and GitHub issue creation behind Security assessment and one-time approval.
- [x] Keep Research on free Crossref/Wikipedia public APIs and disclose when a selected query leaves the device.
- [x] Include native TARA-Handler C++17 source and an explicit pre-launch build step; expose only read-only environment diagnosis.
- [x] Keep a read-only Python diagnostic fallback when a C++ toolchain is unavailable.
- [x] Provide one-command Windows and macOS/Linux launchers.
- [x] Compile the Python package and native Handler in GitHub Actions across Linux, macOS, and Windows.

## User-machine/release steps

- [ ] Run the launcher on the target computer and confirm Ollama starts, the selected local model downloads, and a first response completes within the machine's available RAM/VRAM.
- [ ] If GitHub Actions are enabled, set the local token and explicit repository allowlist; no credential is stored in the repository.
- [ ] Review the draft PR and decide when to mark it ready or merge it.
- [ ] Create a release after the user-machine smoke run.

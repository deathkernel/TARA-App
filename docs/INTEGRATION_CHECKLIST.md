# TARA-App Integration Checklist

## Foundation
- [ ] Confirm engine versions/commits and required Python/C++ runtimes.
- [ ] Finalize versioned request/result contract and capability IDs.
- [ ] Establish configuration loading and secret redaction.
- [ ] Implement structured audit events and request correlation IDs.
- [ ] Add adapter health/capability discovery and fail-closed startup.

## TARA-CHAT
- [ ] Wrap the existing conversation runtime behind a stable Chat adapter.
- [ ] Preserve bounded context and explicit memory controls.
- [ ] Keep Ollama local-only by default.
- [ ] Test provider unavailable, empty reply, timeout, and memory errors.
- [ ] Avoid exposing persistent memory to Code/Handler by default.

## TARA-Code
- [ ] Confirm the engine has moved beyond README-only scaffold before writing imports against it.
- [ ] Integrate planning and review reports through a versioned adapter.
- [ ] Keep code execution disabled until a real OS/container sandbox is selected.
- [ ] Verify workspace containment, resource bounds, controlled networking, no secrets by default, and cleanup.
- [ ] Require human review before promotion; no auto-merge.

## TARA-Handler
- [ ] Reuse the existing TARA-CHAT subprocess bridge design as a reference.
- [ ] Keep native C++ binary separate; never download/build it silently at app runtime.
- [ ] Fix allowlisted arguments; use shell=false and bounded timeouts/output.
- [ ] Begin with diagnostics only.
- [ ] Keep repair/uninstall/cleanup/rollback inaccessible to natural-language dispatch until explicit approval and auditing is complete.

## Cross-module safety/tests
- [ ] Missing adapter/executable and version mismatch fail closed.
- [ ] Timeouts never cause automatic mutation retry.
- [ ] Reject untrusted output as control instructions.
- [ ] Test injection, path traversal, symlinks/reparse points, bad payloads, oversized output, and redacted errors.
- [ ] Test denied, expired, and reused approval tokens.
- [ ] CI: unit tests per adapter plus end-to-end read-only vertical slice.

## Release readiness
- [ ] Clean Windows setup docs and reproducible install/build.
- [ ] Full test runs on supported OS versions.
- [ ] Explain unsupported features and exact limitations.
- [ ] Human-reviewed release tag; no automatic merge.

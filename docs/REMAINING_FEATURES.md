# TARA — Remaining Features Status

> **Source of truth for status labels:** inspect current `main` code and CI evidence.
> **Last reviewed:** 2026-11-03  
> **Against commit:** `c45f4c3` (includes merged PR #51 session lifecycle; PR #50 native risk fix also on main)
>
> Status meanings:
> - **Implemented (code)** — present in repository; still needs target-machine verification where noted
> - **Foundation / partial** — contracts or a first implementation slice exists, but end-to-end incomplete
> - **Pending verification** — code path exists but no current recorded machine/CI evidence for this commit
> - **Pending** — not implemented or not finished
> - **Blocked** — intentionally unavailable until a security prerequisite is met
> - **In progress** — active work; not merge-complete

This table replaces the informal “all pending” list. It does **not** claim target-machine smoke tests, browser QA, or live OmniRoute checks unless evidence is recorded here.

## Status table

| # | Priority | Module / Area | Remaining feature / task | Status | Notes |
| --- | -------- | ------------- | --------------------------------------------------- | -------------------- | ----- |
| 1 | P0 | Testing | Complete Python test suite verification | **Verified (this review)** | `PYTHONPATH=src python3 -m unittest discover -s tests -v` → **Ran 251 tests in 3.483s — OK** on `c45f4c3` (Linux sandbox, 2026-11-03) |
| 2 | P0 | Frontend | Typecheck, build and regression testing | Pending verification | `frontend/` present; npm install timed out in review environment — run locally: `npm install && npm run typecheck && npm run build` |
| 3 | P0 | CI/CD | Latest commit CI verification | Pending verification | Check Actions for current `main` SHA |
| 4 | P0 | Application | Windows launch and Chat smoke test | Pending verification | Launchers exist; live chat needs running OmniRoute + valid `TARA_OMNIROUTE_API_KEY` |
| 5 | P0 | UI | Desktop and mobile browser QA | Pending | Static UI is default; React behind `TARA_ENABLE_REACT_UI=1` |
| 6 | P0 | Documentation | README and implementation reconciliation | Pending | Status table is a first pass |
| 7 | P1 | Application | Connect application service to stable UI/API | Foundation / partial | Headless `application_service` exists; primary UI path still uses orchestrator + webapp |
| 8 | P1 | TARA Chat | Actual Chat engine end-to-end integration | Foundation / partial | `tara_chat` stdio adapter + OmniRoute path present; live E2E pending OmniRoute |
| 9 | P1 | TARA Code | Code adapter integration | Foundation / partial | Review-first `tara_code` + OmniRoute; **no execution** by design until sandbox |
| 10 | P1 | TARA Handler | Secure subprocess protocol | Foundation / partial | `HandlerProcessAdapter` + native binary path; fixed args / shell=False pattern documented |
| 11 | P1 | Runtime | Cancellation and graceful shutdown | Foundation / partial | Timeouts on stdio clients; full cooperative cancel across all providers incomplete |
| 12 | P1 | Runtime | Health checks, load/unload and recovery | Foundation / partial | Adapter `health()` + OmniRoute health helpers; full lifecycle matrix not verified |
| 13 | P1 | Memory | Session retention, deletion and configuration | Implemented (code) | PR #51: atomic turns, opt-in SQLite, `retention_seconds`, schema version fail-closed; default remains memory-only |
| 14 | P1 | Security | Scoped approval, expiry and reuse protection | Implemented (code) | Orchestrator pending approvals are session-bound, single-use, time-limited |
| 15 | P1 | Code Security | Real OS/container sandbox | Blocked | Explicit product rule: path checks alone are not a sandbox |
| 16 | P1 | Code Security | Filesystem, network, CPU and RAM limits | Blocked | Depends on #15 |
| 17 | P1 | Code Security | Malicious code and path traversal protection | Foundation / partial | Policy + workspace containment tests exist; not a substitute for #15 |
| 18 | P1 | Code Workflow | Code diff preview | **Implemented (code)** | `tara_app.code_diff_preview.format_proposed_changes_diff` — data-only unified preview; no apply |
| 19 | P1 | Code Workflow | Approved patch application | Blocked | Must not enable host writes without #15 + explicit approval UX |
| 20 | P1 | Code Workflow | Sandboxed test execution | Blocked | Depends on #15 |
| 21 | P1 | Audit | Complete action audit logging | Foundation / partial | `JsonlAuditLog` with redaction; not every UI path proven to emit full audit trail |
| 22 | P2 | Frontend | React + TypeScript migration | In progress | `frontend/` exists; static UI remains default until parity verified |
| 23 | P2 | UI | Accessibility and keyboard navigation | Pending | |
| 24 | P2 | UI | Loading, error and empty states | Foundation / partial | Some error banners exist (e.g. OmniRoute catalogue failure); systematic coverage pending |
| 25 | P2 | Voice | Local transcription testing | Pending verification | Optional `faster-whisper`; skipped on Python ≥ 3.15 |
| 26 | P2 | Vision | Image analysis and remote gateway testing | Pending verification | OmniRoute vision route; needs live gateway proof |
| 27 | P2 | Study | Scanned PDF OCR | Pending | Text/Markdown/PDF text path exists; OCR not implemented |
| 28 | P2 | Study | Improved MCQ generation | Pending | Deterministic extraction only in first release |
| 29 | P2 | Study | Spaced repetition | Pending | |
| 30 | P2 | Study | Study progress tracking | Pending | |
| 31 | P2 | Platform | Windows/Linux installation testing | Pending verification | Launchers + CI native matrix (Windows/Ubuntu); local install still operator-owned |
| 32 | P2 | Release | Packaging, versioning and installer | Pending | `pyproject.toml` version `0.1.0`; no installer yet |
| 33 | P3 | Specialists | Adapter contract tests for all specialists | Foundation / partial | Many specialist tests under `tests/`; not a full matrix for every module |
| 34 | P3 | Specialists | Independent health checks | Foundation / partial | Adapter health API present |
| 35 | P3 | Specialists | End-to-end workflow testing | Pending verification | |
| 36 | P3 | OmniRoute | Provider, quota and model availability verification | Pending verification | Config and client code present; operator must verify live gateway |
| 37 | P3 | Ecosystem | Optional AI/developer tool evaluation | Pending | Opt-in boundaries only |

## Summary counts (this review)

| Status | Count |
| --- | --- |
| Implemented (code) | 3 (#13, #14, #18) |
| Verified (this review) | 1 (#1) |
| Foundation / partial | 11 |
| In progress | 1 (#22) |
| Pending verification | 10 |
| Pending | 7 |
| Blocked | 4 (#15, #16, #19, #20) |

## Related

- [Project status and roadmap](PROJECT_STATUS_AND_ROADMAP.md)
- [Security model](SECURITY.md)
- [Main README](../README.md)

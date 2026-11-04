# TARA — Remaining Features Status

> **Source of truth for status labels:** inspect current `main` code and CI evidence.
> **Last reviewed:** 2026-11-04  
> **Against commit:** `5aa76ecffdfdcb779084d75c41d8a2b628226cb1` (current `main` at verification time)
>
> Status meanings:
> - **Implemented (code)** — present in repository; still needs target-machine verification where noted
> - **Foundation / partial** — contracts or a first implementation slice exists, but end-to-end incomplete
> - **Pending verification** — code path exists but no current recorded machine/CI evidence for this commit
> - **Pending** — not implemented or not finished
> - **Blocked** — intentionally unavailable until a security prerequisite is met
> - **Verified (CI)** — exact commit completed the relevant GitHub Actions checks; this does not imply local-machine or browser verification
- **In progress** — active work; not merge-complete

This table replaces the informal “all pending” list. It does **not** claim target-machine smoke tests, browser QA, or live OmniRoute checks unless evidence is recorded here.

## Status table

| # | Priority | Module / Area | Remaining feature / task | Status | Notes |
| --- | -------- | ------------- | --------------------------------------------------- | -------------------- | ----- |
| 1 | P0 | Testing | Complete Python test suite verification | Verified (CI) | `python -m unittest discover -s tests -v` → **264 tests in 2.646s — OK** on `5aa76ec` (GitHub Actions, Python 3.11, 2026-11-03); local target-machine run remains unverified |
| 2 | P0 | Frontend | Typecheck, build and regression testing | Verified (CI) | On `5aa76ec`, `npm install --no-audit --no-fund` succeeded and `npm run build` (`tsc -b && vite build`) passed; browser QA and UI parity remain unverified |
| 3 | P0 | CI/CD | Latest commit CI verification | Verified (CI) | Main CI run [#1333](https://github.com/deathkernel/TARA-App/actions/runs/41629104372) passed on exact `main` SHA `5aa76ec`: Python tests, Ubuntu + Windows native Handler, and React frontend build |
| 4 | P0 | Application | Windows launch and Chat smoke test | Pending verification | Launchers exist; live chat needs running OmniRoute + valid `TARA_OMNIROUTE_API_KEY` |
| 5 | P0 | UI | Desktop and mobile browser QA | Pending | Static UI is default; React behind `TARA_ENABLE_REACT_UI=1` |
| 6 | P0 | Documentation | README and implementation reconciliation | Pending | This file is a first pass; README claims still need line-by-line audit |
| 7 | P1 | Application | Connect application service to stable UI/API | Foundation / partial | Headless `application_service` exists; primary UI path still uses orchestrator + webapp |
| 8 | P1 | Testing | Expand adapter and specialist contract tests | Foundation / partial | Growing suite under `tests/` |
| 9 | P1 | Security | Approval UX polish and audit trail completeness | Foundation / partial | Gate exists; not every path proven |
| 10 | P1 | Memory | Session retention policy machine verification | Foundation / partial | Code from PR #51 on main; opt-in retention |
| 11 | P1 | Chat | Longer answers and style guidance verification | Foundation / partial | Token budget + system prompt updates merged; live OmniRoute proof still operator-owned |
| 12 | P1 | Code | Diff preview for proposed changes | Foundation / partial | `code_diff_preview` module + tests on main; UI wiring partial |
| 13 | P1 | Native | Command risk classification regression | Implemented (code) | PR #50 on main |
| 14 | P1 | Sessions | Atomic chat-turn persistence | Implemented (code) | PR #51 on main |
| 15 | P0 | Security | Real OS/container sandbox for code execution | Blocked | Path checks alone are not a sandbox |
| 16 | P0 | Code | Apply patches only inside sandbox after approval | Blocked | Depends on #15 |
| 17 | P1 | Action | Expand desktop automation allowlist carefully | Foundation / partial | Calculator/Notepad/Paint/browser |
| 18 | P1 | GitHub | Issue creation allowlist + credentials flow | Foundation / partial | Gated; needs local config |
| 19 | P0 | Security | No model-driven host shell | Blocked | Policy; do not relax |
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
| 38 | P1 | MCP / Tools | MCP Python SDK client + scoped reference servers (filesystem/git/fetch) | Pending | See README “Planned integrations: Anthropic ecosystem & MCP”; approval gate required |
| 39 | P1 | Agents | Structured multi-step tool loop patterns (claude-agent-sdk reference) | Pending | Proposals remain data-only; no host shell from model text |
| 40 | P2 | Skills | Agent Skills pack loader (Study/Code/Planner templates) | Pending | Inspired by anthropics/skills format |
| 41 | P2 | Ecosystem | Optional anthropic-sdk-python helpers via OmniRoute Claude path | Pending | Never bypass OmniRoute or allow_remote |
| 42 | P3 | Computer use | Computer-use / toolset only inside real OS sandbox | Blocked | Depends on #15; host desktop control is a non-goal |

## Summary counts (2026-11-04 review)

| Status | Count |
| --- | --- |
| Implemented (code) | 2 (#13, #14) |
| Verified (CI) | 3 (#1, #2, #3) |
| Foundation / partial | 12 |
| In progress | 1 (#22) |
| Pending verification | 6 |
| Pending | 13 |
| Blocked | 5 (#15, #16, #19, #20, #42) |

## Related

- [Project status and roadmap](PROJECT_STATUS_AND_ROADMAP.md)
- [Security model](SECURITY.md)
- [Main README](../README.md) (includes Anthropic/MCP integration plan)

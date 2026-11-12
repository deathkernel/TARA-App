# TARA — Remaining Features Status

> **Source of truth for status labels:** inspect current `main` code and CI evidence.
> **Last reviewed:** 2026-11-12
>
> Status meanings:
> - **Implemented (code)** — present in repository; still needs target-machine verification where noted
> - **Foundation / partial** — contracts or a first implementation slice exists, but end-to-end incomplete
> - **Pending verification** — code path exists but no current recorded machine/CI evidence for this commit
> - **Pending** — not implemented or not finished
> - **Blocked** — intentionally unavailable until a security prerequisite is met
> - **Verified (CI)** — exact commit completed the relevant GitHub Actions checks; this does not imply local-machine or browser verification
> - **In progress** — active work; not merge-complete

This table replaces the informal “all pending” list. It does **not** claim target-machine smoke tests, browser QA, or live OmniRoute checks unless evidence is recorded here.

## Status table

| # | Priority | Module / Area | Remaining feature / task | Status | Notes |
| --- | -------- | ------------- | --------------------------------------------------- | -------------------- | ----- |
| 1 | P0 | Testing | Complete Python test suite verification | Verified (CI) | See CI history on main |
| 2 | P0 | Frontend | Typecheck, build and regression testing | Verified (CI) | |
| 3 | P0 | CI/CD | Latest commit CI verification | Verified (CI) | |
| 4 | P0 | Application | Windows launch and Chat smoke test | Pending verification | |
| 5 | P0 | UI | Desktop and mobile browser QA | Pending | |
| 6 | P0 | Documentation | README and implementation reconciliation | Pending | |
| 7 | P1 | Application | Connect application service to stable UI/API | Foundation / partial | |
| 8 | P1 | Testing | Expand adapter and specialist contract tests | Foundation / partial | |
| 9 | P1 | Security | Approval UX polish and audit trail completeness | Foundation / partial | MCP lifecycle audit is durable; visible approval UX remains pending |
| 10 | P1 | Memory | Session retention policy machine verification | Foundation / partial | |
| 11 | P1 | Chat | Longer answers and style guidance verification | Foundation / partial | |
| 12 | P1 | Code | Diff preview for proposed changes | Foundation / partial | |
| 13 | P1 | Native | Command risk classification regression | Implemented (code) | |
| 14 | P1 | Sessions | Atomic chat-turn persistence | Implemented (code) | |
| 15 | P0 | Security | Real OS/container sandbox for code execution | Blocked | |
| 16 | P0 | Code | Apply patches only inside sandbox after approval | Blocked | |
| 17 | P1 | Action | Expand desktop automation allowlist carefully | Foundation / partial | |
| 18 | P1 | GitHub | Issue creation allowlist + credentials flow | Foundation / partial | |
| 19 | P0 | Security | No model-driven host shell | Blocked | |
| 20 | P1 | Code Workflow | Sandboxed test execution | Blocked | |
| 21 | P1 | Audit | Complete action audit logging | Foundation / partial | MCP approval and tool-dispatch lifecycle audited; broader action coverage remains pending |
| 22 | P2 | Frontend | React + TypeScript migration | In progress | |
| 23 | P2 | UI | Accessibility and keyboard navigation | Pending | |
| 24 | P2 | UI | Loading, error and empty states | Foundation / partial | |
| 25 | P2 | Voice | Local transcription testing | Pending verification | |
| 26 | P2 | Vision | Image analysis and remote gateway testing | Pending verification | |
| 27 | P2 | Study | Scanned PDF OCR | Pending | |
| 28 | P2 | Study | Improved MCQ generation | Pending | |
| 29 | P2 | Study | Spaced repetition | Pending | |
| 30 | P2 | Study | Study progress tracking | Pending | |
| 31 | P2 | Platform | Windows/Linux installation testing | Pending verification | |
| 32 | P2 | Release | Packaging, versioning and installer | Pending | |
| 33 | P3 | Specialists | Adapter contract tests for all specialists | Foundation / partial | |
| 34 | P3 | Specialists | Independent health checks | Implemented (code) | Facade checks each registered specialist independently; CI and live provider verification remain required. |
| 35 | P3 | Specialists | End-to-end workflow testing | Pending verification | |
| 36 | P3 | OmniRoute | Provider, quota and model availability verification | Pending verification | |
| 37 | P3 | Ecosystem | Optional AI/developer tool evaluation | Pending | |
| 38 | P1 | MCP / Tools | MCP SDK client, allowlisted registry and tool gateway | Foundation / partial | |
| 39 | P1 | Agents | Structured multi-step tool loop patterns (claude-agent-sdk reference) | Pending | |
| 40 | P2 | Skills | Agent Skills pack loader (Study/Code/Planner templates) | Foundation / partial | Loader + sample packs; Chat/Code UI integration pending |
| 41 | P2 | Ecosystem | Optional anthropic-sdk-python helpers via OmniRoute Claude path | Pending | |
| 42 | P3 | Computer use | Computer-use / toolset only inside real OS sandbox | Blocked | |
| 43 | P1 | MCP Manager | Read-only free-first integration catalogue and local UI | Verified (CI) | PR #103 merged as 1d4f63d; run #1878 passed all four jobs |
| 44 | P1 | MCP Manager | Bounded catalogue fetch timeout and recoverable UI error | Verified (CI) | PR #103 merged as 1d4f63d; 10-second browser abort and recoverable refresh path included |
| 45 | P1 | MCP Audit | Consolidate competing audit implementations | In progress | Branch: codex/mcp-audit-security-bulk; reuse JsonlAuditLog; PRs #95/#96 remain unmerged |
| 46 | P0 | Verification | Current-main baseline and target-machine smoke tests | Pending verification | Historical CI evidence is not current-commit evidence |

## Related

- [Project status and roadmap](PROJECT_STATUS_AND_ROADMAP.md)
- [Skills packs](SKILLS.md)
- [Security model](SECURITY.md)
- [Main README](../README.md)

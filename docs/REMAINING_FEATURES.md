# TARA — Remaining Features Status

> **Source of truth for status labels:** inspect current `main` code and CI evidence.
> **Last reviewed:** 2026-11-04
>
> Status meanings:
> - **Implemented (code)** — present in repository; still needs target-machine verification where noted
> - **Foundation / partial** — contracts or a first implementation slice exists, but end-to-end incomplete
> - **Pending verification** — code path exists but no current recorded machine/CI evidence for this commit
> - **Pending** — not implemented or not finished
> - **Blocked** — intentionally unavailable until a security prerequisite is met
> - **Verified (CI)** — exact commit completed the relevant GitHub Actions checks
> - **In progress** — active work; not merge-complete

## Status table

| # | Priority | Module / Area | Remaining feature / task | Status | Notes |
| --- | -------- | ------------- | --------------------------------------------------- | -------------------- | ----- |
| 1 | P0 | Testing | Complete Python test suite verification | Verified (CI) | See project CI |
| 2 | P0 | Frontend | Typecheck, build and regression testing | Verified (CI) | |
| 3 | P0 | CI/CD | Latest commit CI verification | Verified (CI) | |
| 4 | P0 | Application | Windows launch and Chat smoke test | Pending verification | |
| 5 | P0 | UI | Desktop and mobile browser QA | Pending | |
| 6 | P0 | Documentation | README and implementation reconciliation | Foundation / partial | |
| 38 | P1 | MCP / Tools | MCP SDK client, allowlisted registry and tool gateway | Foundation / partial | MCP disabled by default |
| 39 | P1 | Agents | Structured multi-step tool loop patterns | Foundation / partial | See tool_loop branch |
| 40 | P2 | Skills | Agent Skills pack loader (Study/Code/Planner templates) | Foundation / partial | Loader + sample packs; Chat/Code UI integration pending |
| 41 | P2 | Ecosystem | Optional anthropic-sdk-python helpers via OmniRoute Claude path | Pending | Never bypass OmniRoute |
| 42 | P3 | Computer use | Computer-use / toolset only inside real OS sandbox | Blocked | Host desktop control is a non-goal |

> Note: This table is a compact status view. Full historical rows remain on `main` history; skills PR updates row #40.

## Related

- [Project status and roadmap](PROJECT_STATUS_AND_ROADMAP.md)
- [Skills packs](SKILLS.md)
- [Security model](SECURITY.md)

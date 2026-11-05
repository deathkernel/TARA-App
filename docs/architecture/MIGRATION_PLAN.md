# TARA Architecture Migration Plan

**Status:** Proposed sequence — no source files moved by this document  
**Rule:** Preserve behavior first; consolidate boundaries second; restructure folders last.

## Phase 0 — Freeze the baseline

Deliverables:
- Record the exact base commit and current branch.
- Capture the current full test and CI state.
- Inventory every source file, entry point, package, dependency, subprocess, endpoint, and persistent store.
- Map import dependencies and runtime call paths.
- Record which integrations are live, mocked, disabled, or unverified.

Exit criteria:
- Reproducible baseline.
- No claimed test result without commit-specific evidence.
- File ownership and unknowns documented.

## Phase 1 — Trace the real request lifecycle

Trace at least these paths end-to-end:
1. HTTP chat request.
2. Desktop launch and pet lifecycle.
3. CLI startup and command dispatch.
4. Capability routing and adapter invocation.
5. Approval request, approval decision and protected execution.
6. MCP discovery and tool invocation.
7. Session persistence and audit write.
8. OmniRoute inference and provider failure.

For each path, record entry point, function calls, data structures, state owner, side effects, error paths, and tests.

Exit criteria:
- One call graph per path.
- Duplicated or bypassed paths identified with code references.
- No assumptions based only on filenames.

## Phase 2 — Choose one application composition path

Target:
- A single bootstrap/composition root builds the application.
- Interfaces receive an application facade, not a raw orchestrator, registry, provider, or adapter.
- The application facade owns use-case boundaries and calls one coordination engine.
- Remove the competing runtime construction path only after parity tests exist.

Priority issue:
- The current launcher path creates an Orchestrator in runtime.py and passes it to webapp.serve().
- A separate TARAApplicationService exists with sessions, audit, model catalogue and a legacy runtime manager, but is not the current launcher path.
- Design and implement one path that retains active OmniRoute gateway and capability policy behavior. Do not reactivate legacy direct Ollama inference accidentally.

Exit criteria:
- HTTP, desktop and CLI use the same application entry points.
- No interface accesses registry or adapter internals.
- One authoritative request/approval/execution flow.

## Phase 3 — Define canonical contracts and state ownership

Implement or consolidate:
- request, workflow, step, result, event and artifact-reference contracts;
- schema versioning and payload limits;
- correlation and causation identifiers;
- workflow state transitions and durable step results;
- session state and retention;
- approval records scoped to one operation;
- audit event references.

Exit criteria:
- Every step result can be traced to its request and workflow.
- No shared mutable global context.
- State transitions have explicit tests.
- Large data is passed by bounded artifact reference.

## Phase 4 — Unify coordination and execution

- Decide which responsibilities remain in orchestrator.py and orchestration.py; merge or retire duplicate abstractions only with tests.
- Keep routing as a plan/proposal mechanism, not an authorization decision.
- Make policy evaluation authoritative and independent from model output.
- Dispatch through one execution boundary.
- Add deadlines, cancellation, idempotency and bounded resource controls.
- Make retries explicit and forbid automatic retries for ambiguous mutations.

Exit criteria:
- One coordinator owns workflow state.
- One security gate protects every side effect.
- Every operation returns a validated normalized result.

## Phase 5 — Consolidate integrations

Create stable ports for:
- inference gateway (OmniRoute);
- persistence;
- filesystem and workspace access;
- network access;
- MCP;
- GitHub actions;
- Windows/native operations;
- local speech processing where supported.

No operation or workflow imports a concrete provider or native implementation. Keep language-model inference on the documented OmniRoute route unless the product owner explicitly changes that policy.

Exit criteria:
- Fake adapters can test application/workflow logic.
- Provider/network failures are normalized.
- No integration bypasses security and audit.

## Phase 6 — Move code by responsibility

Only after Phases 0–5:
- Move composition code to bootstrap.
- Move HTTP/CLI/desktop transport code to interfaces.
- Move user-facing use cases and session coordination to application.
- Move workflow state and dependency logic to coordination.
- Move stable rules and invariants to domain.
- Move process/job dispatch to execution.
- Move schemas and ports to contracts.
- Move provider, storage and protocol implementations to infrastructure.
- Move OS/native code to platform.
- Move telemetry and audit sinks to observability.

Do not create a new file merely to preserve an old package name. Do not move code if it would create a meaningless wrapper. Merge only when ownership is genuinely the same.

Exit criteria:
- Every source file has one documented responsibility and owner.
- Import direction checks pass.
- Public interfaces remain stable or are versioned.
- No duplicate runtime or orchestration path remains.

## Phase 7 — Verification and rollout

Run in order:
1. Formatting, lint and static type checks.
2. Unit tests.
3. Contract tests.
4. Workflow and security integration tests.
5. Adapter tests with fakes.
6. Windows-specific process/native tests.
7. Loopback API and UI end-to-end tests.
8. OmniRoute live smoke test with an explicitly configured route.
9. Regression test of existing features.
10. Packaging and clean-install test.

Keep the previous launcher path available during transition only if isolated and explicitly marked legacy. Remove it after the replacement passes the same acceptance suite.

## Phase 8 — Documentation and release

Update:
- architecture and dependency diagrams;
- setup/configuration guide;
- API and integration contracts;
- security and data-handling documentation;
- troubleshooting and operational health;
- feature status and test evidence.

A design document or passing unit suite is not proof of production readiness. Report exactly which checks ran and on which commit.

## Stop conditions

Stop migration and investigate if:
- a feature's behavior is not understood;
- a data store or configuration format would be lost;
- a permission/approval check is bypassed;
- the new path changes provider routing or remote data handling;
- Windows-specific behavior cannot be verified;
- a test baseline is unavailable or materially regresses.

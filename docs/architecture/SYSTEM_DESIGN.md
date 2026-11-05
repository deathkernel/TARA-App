# TARA Wide System Architecture

**Status:** Proposed target architecture — design only, not yet implemented  
**Scope:** TARA-App consolidated repository  
**Architecture style:** Responsibility-oriented modular monolith, workflow-coordinated, ports-and-adapters at external boundaries

## 1. Objective

TARA must behave as one connected Windows application, not as a collection of isolated AI packages. The repository is organized around the lifecycle and responsibilities of the whole system. Models, providers, and user-facing capabilities are implementation details behind stable interfaces; they do not define the top-level folder structure.

The target is intentionally a **modular monolith**:
- one application composition root and one authoritative request lifecycle;
- internal boundaries enforced by contracts and dependency rules;
- direct in-process calls for normal work;
- bounded subprocesses only where process isolation or a separate native executable is justified;
- no distributed microservices or message broker until measured requirements demand them.

## 2. Non-negotiable principles

1. **Responsibility-first organization.** Top-level packages represent system responsibilities, not model names or individual features.
2. **One request lifecycle.** Every request enters through an interface and passes through the same application, workflow, policy, execution, result, and audit path.
3. **Explicit data flow.** Data moves through typed, versioned inputs and outputs. No hidden global context or arbitrary cross-module imports.
4. **Single ownership.** Every durable entity, policy, configuration value, and side effect has one authoritative owner.
5. **Dependency inversion.** Core rules depend on ports/contracts, not HTTP servers, SQLite, OmniRoute, Windows APIs, or subprocess implementations.
6. **Policy before execution.** Authorization and approval are enforced at the execution boundary, not merely in the UI or router.
7. **Fail closed.** Missing dependencies, invalid contracts, audit failure before a protected action, unsupported versions, or missing approval prevent execution.
8. **Local-first control plane.** Sessions, workflow state, permissions, approvals, and audit remain under TARA's control. Inference may use the configured OmniRoute route and its selected provider.
9. **No model ownership in feature logic.** Application operations request inference through a common gateway port. They do not load weights, select providers, or manage provider lifecycle.
10. **Evidence-based migration.** Existing behavior is mapped and tested before moving or removing code.

## 3. System context

~~~mermaid
flowchart TB
    USER[User]
    subgraph TARA["TARA Windows Application"]
      UI[Interaction Interfaces]
      APP[Application Services]
      WF[Workflow and Coordination]
      DOMAIN[System Rules and Policies]
      EXEC[Execution Control]
      STATE[(Local State)]
      AUDIT[(Audit Trail)]
    end
    subgraph EXT["Controlled External Boundaries"]
      AI[OmniRoute Gateway]
      MCP[MCP Servers]
      OS[Windows and Native APIs]
      WEB[Approved Network Services]
      FS[Scoped Filesystem]
    end
    USER <--> UI
    UI <--> APP
    APP <--> WF
    WF <--> DOMAIN
    WF <--> EXEC
    APP <--> STATE
    WF <--> STATE
    APP --> AUDIT
    WF --> AUDIT
    EXEC --> AUDIT
    EXEC <--> AI
    EXEC <--> MCP
    EXEC <--> OS
    EXEC <--> WEB
    EXEC <--> FS
~~~

The diagram is logical. It does not imply that every boundary must run in a separate process.

## 4. Responsibility-oriented source layout

This is the **target layout**, not a claim about the current source tree.

~~~text
src/tara_app/
│
├── bootstrap/             # Composition root; build and wire the application
│
├── interfaces/            # HTTP, desktop, CLI and presentation adapters
│   ├── http/
│   ├── desktop/
│   └── cli/
│
├── application/           # Use-case entry points and application lifecycle
│   ├── commands/
│   ├── queries/
│   ├── sessions/
│   └── lifecycle/
│
├── coordination/          # Workflow planning, state transitions and result joining
│   ├── workflows/
│   ├── planning/
│   ├── state/
│   └── context/
│
├── domain/                # Invariants, entities, value objects and domain policies
│   ├── entities/
│   ├── values/
│   ├── policies/
│   └── services/
│
├── execution/             # Controlled execution, process and job lifecycle
│   ├── dispatch/
│   ├── processes/
│   ├── jobs/
│   ├── cancellation/
│   └── sandbox/
│
├── contracts/             # Versioned requests, results, events and port definitions
│   ├── requests/
│   ├── results/
│   ├── events/
│   └── ports/
│
├── security/              # Authorization, approvals, scope and redaction
│   ├── authorization/
│   ├── approvals/
│   ├── boundaries/
│   └── redaction/
│
├── infrastructure/        # Concrete technical adapters
│   ├── persistence/
│   ├── inference/
│   ├── networking/
│   ├── filesystem/
│   └── integrations/
│
├── platform/              # Operating-system and native implementation details
│   ├── windows/
│   └── native/
│
├── observability/         # Structured logs, metrics, traces and audit sinks
│
└── configuration/         # Typed settings, validation and configuration sources
~~~

The layout deliberately has no top-level models, chat, code, research, or other feature-name packages. A workflow may have a descriptive file such as repository_review.py, but it remains a workflow definition, not a separate architectural subsystem.

### Current responsibilities mapped conceptually

| Current responsibility | Target ownership |
|---|---|
| runtime composition and wiring | bootstrap |
| webapp, CLI and desktop entry points | interfaces |
| application_service and session-facing use cases | application |
| orchestrator, orchestration and route coordination | coordination after one authoritative flow is selected |
| contracts and adapter protocols | contracts |
| permission and approval rules | security and domain policies |
| process adapters and bounded dispatch | execution |
| OmniRoute, MCP, HTTP and storage adapters | infrastructure |
| Windows pet and native Handler integration | platform plus execution ports |
| audit and health instrumentation | observability |

This is a responsibility map, not an instruction to move files mechanically. Each file must be inspected for mixed responsibilities before migration.

## 5. Layer ownership

### Bootstrap
Owns application construction only: load validated settings, instantiate implementations, wire ports, register workflows, and start interfaces. It must not contain business logic.

### Interfaces
Translate external input into application requests and application results into protocol responses. Interfaces must not call providers, databases, native APIs, or specialist implementations directly.

### Application
Owns user-visible use cases and transaction boundaries: create/close session, submit request, inspect status, cancel operation, approve/deny a proposal, and retrieve history. It coordinates but does not implement infrastructure.

### Coordination
Owns workflow lifecycle: plan, dependency graph, step scheduling, context propagation, state transitions, result aggregation, retry eligibility, and cancellation propagation. It is the sole owner of workflow state transitions.

### Domain
Owns stable rules and invariants independent of UI, providers, storage, and OS. Domain code must remain deterministic where possible and must not perform network, filesystem, process, or model calls.

### Execution
Owns the controlled invocation of operations: dispatch, bounded process management, timeouts, cancellation, resource limits, sandbox integration, and normalized execution outcomes. It cannot authorize itself.

### Contracts
Owns versioned schemas and ports shared across boundaries. Contracts describe data and behavior; they do not contain provider-specific implementation.

### Security
Owns policy evaluation, scope checks, approval grants, one-time tokens, secret redaction, and trust-boundary decisions. The execution boundary must re-check authorization immediately before side effects.

### Infrastructure
Implements ports for persistence, inference gateway, networking, filesystem access, MCP transport, and external services. It must not decide application workflows or user permissions.

### Platform
Contains OS-specific implementations and native bindings. Platform details are exposed through ports so application and domain layers remain portable.

### Observability
Owns structured operational telemetry and audit sinks. Security-sensitive operations must durably record the policy decision before execution. Audit payloads must be minimized and redacted.

## 6. Dependency direction

~~~mermaid
flowchart BT
    DOMAIN[Domain]
    CONTRACTS[Contracts and Ports]
    APPLICATION[Application]
    COORDINATION[Coordination]
    EXECUTION[Execution]
    SECURITY[Security]
    INFRA[Infrastructure Adapters]
    PLATFORM[Platform Adapters]
    INTERFACES[Interfaces]
    BOOTSTRAP[Bootstrap]

    DOMAIN --> CONTRACTS
    APPLICATION --> DOMAIN
    APPLICATION --> CONTRACTS
    COORDINATION --> APPLICATION
    COORDINATION --> DOMAIN
    COORDINATION --> CONTRACTS
    EXECUTION --> CONTRACTS
    SECURITY --> DOMAIN
    SECURITY --> CONTRACTS
    INFRA --> CONTRACTS
    PLATFORM --> CONTRACTS
    INTERFACES --> APPLICATION
    BOOTSTRAP --> INTERFACES
    BOOTSTRAP --> INFRA
    BOOTSTRAP --> PLATFORM
    BOOTSTRAP --> EXECUTION
    BOOTSTRAP --> SECURITY
~~~

Rules:
- Domain never imports application, coordination, execution, infrastructure, platform, or interfaces.
- Infrastructure and platform implement contracts; they do not become dependencies of domain logic.
- Interfaces depend on application entry points only.
- Cross-boundary calls use typed contracts or explicit ports.
- No circular imports.
- No arbitrary access to another layer's private state.
- Bootstrap is the only place allowed to know concrete implementations of all major ports.

## 7. Canonical request and workflow data

Every request receives:
- request_id: unique request identifier;
- session_id: conversation/session scope;
- workflow_id: workflow instance identifier;
- correlation_id and optional causation_id: end-to-end trace lineage;
- schema_version: contract version;
- principal: local user/application identity;
- created_at, deadline and cancellation reference;
- bounded, typed input and explicit attachment references.

A workflow context is **not** a shared mutable dictionary available to every component. It is a controlled execution envelope:
- immutable request metadata;
- explicit input references;
- typed step outputs;
- artifact references for large data;
- policy/approval references;
- deadline and cancellation state;
- provenance and trust labels.

Each step declares input schema, output schema, required permissions, resource budget, timeout, and whether it can cause side effects. A step can read only the inputs declared for it.

### Result envelope

~~~json
{
  "schema_version": "1.0",
  "request_id": "request-id",
  "workflow_id": "workflow-id",
  "step_id": "step-id",
  "status": "success",
  "data": {},
  "artifacts": [],
  "provenance": [],
  "error": null,
  "duration_ms": 0,
  "audit_ref": "event-id"
}
~~~

All operations return a normalized result. Statuses distinguish success, partial, unavailable, invalid, denied, approval_required, cancelled, timeout, and failed. The exact enum belongs in the versioned contract package.

Raw model output, external page content, repository content, and tool output are untrusted data. They never become executable instructions or policy grants.

## 8. Canonical data flow

1. An interface validates transport-level input and calls an application use case.
2. The application establishes identity, session, request IDs, deadline and attachment references.
3. The coordination layer selects or builds a workflow using registered operation metadata.
4. Security evaluates the requested operations, scope, data classification and approval requirements.
5. The workflow engine persists the initial state and policy decision before protected execution.
6. Execution dispatches only authorized steps through registered ports/adapters.
7. Each step returns a contract-validated result; the workflow stores it and makes only declared outputs available to dependent steps.
8. Failures, cancellation and timeouts propagate to dependent steps according to explicit policy.
9. The coordinator aggregates results and records final state.
10. The application persists session-visible output and returns a normalized response to the interface.

An operation never silently invokes another operation by importing its private implementation. It returns a result; the workflow engine decides whether that result satisfies a downstream dependency and dispatches the next step.

## 9. State and persistence ownership

Use SQLite initially for durable application state where transactional consistency is needed:
- sessions and bounded conversation history;
- workflow records and step state;
- approval records and expiry/consumption state;
- artifact metadata and retention metadata;
- configuration metadata where appropriate.

Use an append-only audit stream for security and operational events. Audit is not a substitute for workflow state. Store large attachments/artifacts as files or content-addressed blobs with metadata in SQLite; do not put large binary payloads into workflow context.

Define migrations, retention, backup, corruption recovery, and file-permission policy before enabling durable storage by default. Avoid introducing Redis, Kafka, or a distributed database in the initial desktop architecture.

## 10. AI and external execution boundary

TARA owns workflow planning, permissions, context selection, local state, tool dispatch, and result validation. OmniRoute remains the configured inference gateway and owns model/provider routing. Inference is a port implemented under infrastructure/inference/.

Consequences:
- no model-specific source folders;
- no model weight loading in application/domain code;
- no feature-specific provider clients;
- no direct provider bypass around the gateway;
- model/route identity is metadata attached to an inference operation, not an architectural boundary;
- local deterministic operations do not require a model;
- provider failure returns an explicit unavailable/failed result; it does not silently switch providers.

MCP, filesystem, network, GitHub, and native OS actions are integrations behind explicit ports and the same execution/security path.

## 11. Security and side-effect model

- Default deny for unknown operations.
- Separate read-only, remote-data-transfer, and mutating permissions.
- Approval is scoped to one operation, exact arguments or argument digest, session, resource scope, and short expiry.
- Approval is revalidated at execution time and cannot be replayed.
- No arbitrary host shell from model output.
- Code execution stays disabled until a real OS/container isolation boundary and tests exist.
- Workspace containment checks are defense-in-depth, not a sandbox.
- Never automatically install packages, alter system settings, commit, push, or merge.
- If the audit sink cannot persist a required pre-execution decision, do not execute the protected operation.
- Remote transfer is disclosed and minimized; secrets are excluded by default.

## 12. Reliability and concurrency

- Every long-running operation has a deadline and cancellation path.
- Retries are permitted only for explicitly idempotent operations.
- Mutating operations are never automatically retried after an ambiguous timeout.
- Use bounded queues and resource budgets; do not spawn unbounded workers.
- Prevent duplicate task execution using idempotency keys and persisted operation state.
- A cancelled parent workflow cancels cancellable child steps and records any non-cancellable side effect already completed.
- Partial results are represented explicitly; do not silently convert partial success to success.

## 13. Test architecture

- Domain tests: deterministic rules and invariants.
- Contract tests: schema compatibility, size limits, malformed and hostile payloads.
- Application tests: use-case behavior with fake ports.
- Workflow tests: dependencies, state transitions, partial failure, cancellation and retry rules.
- Security tests: default deny, approval scope, expiry, replay, path escape, audit failure.
- Infrastructure contract tests: SQLite, OmniRoute, MCP, filesystem and network adapters.
- Platform tests: Windows process and native integration.
- End-to-end tests: real launcher, loopback API, UI, session lifecycle and representative workflows.

A unit test passing does not prove Windows runtime integration. CI, local tests, live gateway tests, and target-machine smoke tests must be reported separately.

## 14. Current-state gaps motivating redesign

The inspected main-branch source shows several competing paths that should be reconciled before moving files:

1. runtime.py:create_application() builds a router, registry, subprocess adapters and Orchestrator directly.
2. webapp.py receives the Orchestrator directly and accesses its registry and MCP methods, so the HTTP interface is coupled to the coordinator implementation.
3. application_service.py is a separate headless facade that owns sessions, audit, a model catalogue and an optional CapabilityOrchestrator; it is not the same path used by the current launcher.
4. application_service.py and runtime_manager.py retain a legacy local-provider/Ollama-oriented abstraction, while current runtime documentation says active language-model inference goes through OmniRoute.
5. orchestrator.py and orchestration.py represent separate orchestration abstractions; their responsibilities and active call paths need to be consolidated.
6. Routing, capability registration, execution adapters, MCP, sessions and audit have useful foundations, but workflow state and result propagation are not yet owned by one application-wide lifecycle.
7. Source packages are split into tara_app and many tara_* packages. This package layout mirrors capability names more than the full system lifecycle.

These are architectural findings from source inspection, not proof that every feature is broken. The migration plan must add call-graph and test evidence before any component is removed.

## 15. Explicit non-goals

- No wholesale rewrite of all specialist logic.
- No immediate move to microservices.
- No mandatory message broker or distributed event bus.
- No model catalogue as the root architecture.
- No feature-per-top-level-package organization.
- No new AI provider added as part of the structural redesign.
- No change to safety policy merely to make workflows easier.
- No claim that the proposed layout is implemented until code and tests prove it.

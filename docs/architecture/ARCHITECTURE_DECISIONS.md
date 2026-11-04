# TARA Architecture Decision Records

**Status:** Proposed decisions for architecture review

## ADR-001 — Use a responsibility-oriented modular monolith

**Decision:** Keep one deployable TARA application with explicit internal boundaries.  
**Reason:** The current desktop product benefits from simple local deployment and direct calls, while still needing clear ownership and testable boundaries.  
**Consequences:** No distributed message broker or microservice fleet in the initial redesign. Separate processes are used only for native components or a justified isolation boundary.

## ADR-002 — Do not organize source around models or feature names

**Decision:** Top-level packages represent application/system responsibilities: interfaces, application, coordination, domain, execution, contracts, security, infrastructure, platform, observability and bootstrap.  
**Reason:** Model-centric or feature-per-package organization can split the request lifecycle and encourage duplicated state and adapters.  
**Consequences:** A feature is expressed as a use case or workflow definition inside the system architecture, not as an independent top-level subsystem. Provider/model identity remains runtime metadata.

## ADR-003 — One application facade and one request lifecycle

**Decision:** HTTP, desktop and CLI interfaces call the same application entry points; those entry points use one workflow coordinator and one execution/security boundary.  
**Reason:** The current source has a launcher path that passes an Orchestrator directly to the web app and a separate headless application service with its own runtime/orchestration abstractions.  
**Consequences:** Consolidation must preserve current behavior and OmniRoute routing; the two paths are not merged by simply choosing one file.

## ADR-004 — Typed workflow contracts, not shared mutable context

**Decision:** Use versioned request, step-input, step-result, event and artifact-reference contracts.  
**Reason:** Explicit contracts make data ownership, validation, provenance and failure handling visible.  
**Consequences:** No arbitrary global context dictionary. Large content is referenced by bounded artifact handles.

## ADR-005 — Central workflow state ownership

**Decision:** The coordinator owns workflow and step state transitions; durable state is persisted through a storage port.  
**Reason:** Independent modules must not maintain conflicting copies of task status or silently pass state through side channels.  
**Consequences:** Session state, workflow state and audit records have separate schemas and clear relationships.

## ADR-006 — Authorization is enforced at execution time

**Decision:** Routing may propose an operation, but cannot grant permission. The security layer evaluates scope and approval, and execution revalidates immediately before side effects.  
**Reason:** Model output, router output and tool output are untrusted.  
**Consequences:** Unknown operations are denied; approval is one-operation, scoped, expiring and non-replayable.

## ADR-007 — Keep inference behind one gateway port

**Decision:** Application/workflow code calls an inference port; the production adapter uses the configured OmniRoute gateway.  
**Reason:** TARA should not couple its architecture to model families, weight formats or provider lifecycle.  
**Consequences:** No direct provider client in domain or use-case code. No silent local/cloud fallback. Model catalogue and route selection are not top-level architectural concerns.

## ADR-008 — Use synchronous in-process coordination first

**Decision:** Start with direct calls and a persisted workflow state machine. Add background workers or an event bus only when latency, concurrency, or reliability requirements justify them.  
**Reason:** A desktop application does not need distributed infrastructure by default.  
**Consequences:** Events are useful as typed domain/application notifications, but do not imply Kafka, Redis Streams or a distributed event system.

## ADR-009 — Separate audit from business state

**Decision:** Keep workflow/session persistence and append-only audit as distinct concerns with linked identifiers.  
**Reason:** Audit records explain decisions and side effects; they are not the authoritative mutable workflow state.  
**Consequences:** Sensitive operations require durable pre-execution audit; all audit data is minimized and redacted.

## ADR-010 — Treat development tools as optional tooling, not runtime architecture

**Decision:** Amp and GitHub Copilot sandboxing may be used as development environments; neither is a TARA runtime dependency. GitHub Package Firewall is an optional Enterprise-only supply-chain control, not a baseline requirement. AWS TorchNeuron is a possible future inference infrastructure adapter only for an AWS Trainium deployment and remains behind the inference gateway boundary.  
**Reason:** These tools solve different development, supply-chain and hardware-backend problems; none should define TARA's source architecture.  
**Consequences:** TARA remains buildable and runnable without those optional services unless a future deployment explicitly adopts them.

# TN-86 Implementation Roadmap

**Status:** Phase 3 implementation committed; execution and integration validation pending  
**Repository:** TARA-App  
**Working branch:** `tn-86/architecture-alignment`

## Engineering objective

Build a measurable, brain-inspired cognitive runtime inside TARA while preserving
the existing Windows application, interfaces, security boundaries, approval
workflow, specialist capabilities, and OmniRoute inference gateway.

TN-86 is a project name inspired by the approximate 86-billion-neuron scale
often cited for the human brain. It is not a claim that this application will
simulate 86 billion biological neurons.

## Implementation phases

| Phase | System | Completion evidence |
|---|---|---|
| 1 | Neural processing foundation | LIF neuron, sparse synapse and deterministic network primitives with focused tests |
| 2 | Memory architecture | Working, episodic and semantic memory with explicit storage and retrieval contracts |
| 3 | Learning mechanisms | Bounded, testable Hebbian/STDP plasticity with approved state persistence |
| 4 | Cognitive engine | Attention, context integration, reasoning coordination and decision contracts |
| 5 | Mathematical intelligence | Deterministic linear algebra, calculus, probability, statistics and optimization services |
| 6 | Multimodal integration | Voice and vision observations enter the same typed cognitive request lifecycle |
| 7 | Unified neural runtime | One composition path with bounded scheduling, cancellation and observability |
| 8 | Verification | Regression, correctness, resource and latency benchmarks on supported hardware |

## Phase 1 — Neural processing foundation

- Added LIF neuron dynamics with exact passive membrane integration.
- Added signed directed synapse definitions.
- Added sparse deterministic spiking network with one-step event delivery.
- Added focused unit tests.
- Test execution and full repository regression remain pending in a Python environment.

## Phase 2 — Memory architecture

- Added typed memory records and explicit WORKING, EPISODIC and SEMANTIC categories.
- Added bounded recency-based working memory that remains session-local.
- Added SQLite persistence for episodic and semantic records, using a separate TN-86 table in the existing TARA memory database.
- Added deterministic lexical retrieval with transparent scores and filters by memory kind.
- Added explicit consolidation from working memory into long-term memory.
- Persistent writes and deletes are denied by default and require an injected authorization callback. The existing TARA approval layer must supply that callback; TN-86 does not mint or validate approval tokens.
- Added focused tests for capacity, retrieval, persistence, consolidation and denied writes.
- The new engine is not yet wired into the live Orchestrator. Automated test execution remains pending.

## Phase 3 — Learning mechanisms

- Added bounded rate-based Hebbian learning and pair-based STDP.
- Preserved excitatory/inhibitory synapse polarity and capped weight magnitude.
- Added snapshots and explicit rollback/restore.
- Added atomic JSON persistence gated by an injected approval callback; load validates exact topology and weight limits.
- Added a bridge to apply learned weights to the sparse spiking network without changing topology.
- Learning is explicit; it does not automatically train on user conversations or run in the live Orchestrator.
- Focused tests were added; execution and numerical validation remain pending.

## Constraints

- Preserve OmniRoute as the single configured LLM gateway.
- Do not remove or silently replace existing specialist modules.
- Keep security, approval and execution policy outside neural model code.
- Avoid mandatory heavyweight numerical or deep-learning dependencies until a measured implementation requirement justifies them.
- Do not claim learning, cognition, biological equivalence or performance gains without implementation and benchmark evidence.
- Keep each phase independently reviewable and regression-tested.

## Definition of done

A subsystem is complete only when its contracts and assumptions are documented,
its implementation is connected to the real TARA runtime, tests pass, security
behavior is verified, and reproducible benchmarks are recorded.

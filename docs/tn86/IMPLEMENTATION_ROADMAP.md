# TN-86 Implementation Roadmap

**Status:** Phase 4 initial implementation committed; execution and integration validation pending  
**Repository:** TARA-App  
**Working branch:** tn-86/architecture-alignment

## Engineering objective
Build a measurable, brain-inspired cognitive runtime inside TARA while preserving the existing Windows application, interfaces, security boundaries, approval workflow, specialist capabilities, and OmniRoute inference gateway.

TN-86 is a project name inspired by the approximate 86-billion-neuron scale often cited for the human brain. It is not a claim that this application will simulate 86 billion biological neurons.

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
- Added focused unit tests. Test execution and full repository regression remain pending.

## Phase 2 — Memory architecture
- Added typed WORKING, EPISODIC and SEMANTIC memory.
- Added bounded recency-based session-local working memory.
- Added SQLite persistence for episodic and semantic records in a separate TN-86 table.
- Added deterministic lexical retrieval and explicit consolidation.
- Persistent writes and deletes are denied by default and require an injected authorization callback; TN-86 does not mint or validate approval tokens.
- Added focused tests. The engine is not yet wired into the live Orchestrator; automated test execution remains pending.

## Phase 3 — Learning mechanisms
- Added bounded rate-based Hebbian learning and pair-based STDP.
- Preserved synapse polarity and capped weight magnitude.
- Added snapshots, rollback/restore and atomic approved JSON persistence.
- Added a bridge to apply learned weights to the sparse network without changing topology.
- Learning is explicit; it does not automatically train on user conversations or run in the live Orchestrator.
- Focused tests were added; execution and numerical validation remain pending.

## Phase 4 — Cognitive engine
- Added immutable cognitive request, context, attention, goal and decision contracts.
- Added deterministic attention scoring over relevance, importance, recency, salience and confidence; per-feature contributions are exposed.
- Added exponential recency decay and bounded context assembly from working, episodic and semantic memory.
- Added bounded goal scheduling with deadline pressure and dependency gating.
- Added evidence-adjusted action scoring and explicit abstention for weak scores or close alternatives.
- Added a staged coordinator requiring an injected proposal provider. It can be adapted to the existing OmniRoute gateway; no second LLM gateway is introduced.
- The coordinator does not execute tools or actions. Existing TARA approval and security controls remain authoritative.
- Neural-to-symbolic activation mapping and automatic learning from conversation data are not claimed; they require validated mappings and controlled experiments.
- Added focused tests in tests/test_tn86_cognition.py. They have been authored but not executed in this environment.
- Research review and original technical note are stored under research/literature_reviews and research/original_papers; BibTeX metadata is stored under research/references.

## Research integrity
- Research informs design choices; it does not prove biological equivalence.
- Distinguish peer-reviewed papers, reviews, conference papers and preprints.
- Project technical notes are not described as peer-reviewed publications.
- Record hypotheses and evaluation protocols before claiming improvements.
- Preserve exact citations and source metadata in research records.

## Constraints
- Preserve OmniRoute as the single configured LLM gateway.
- Do not remove or silently replace existing specialist modules.
- Keep security, approval and execution policy outside neural model code.
- Avoid mandatory heavyweight numerical or deep-learning dependencies until measured need justifies them.
- Do not claim learning, cognition, biological equivalence or performance gains without implementation and benchmark evidence.
- Keep each phase independently reviewable and regression-tested.

## Definition of done
A subsystem is complete only when its contracts and assumptions are documented, its implementation is connected to the real TARA runtime, tests pass, security behavior is verified, and reproducible benchmarks are recorded.

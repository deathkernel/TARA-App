# TN-86 Implementation Roadmap

**Status:** Phase 1 implementation started  
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
| 1 | Neural processing foundation | Tested LIF neuron, sparse synapse and deterministic network primitives |
| 2 | Memory architecture | Working, episodic and semantic memory with explicit storage and retrieval contracts |
| 3 | Learning mechanisms | Bounded, testable plasticity rules; learning changes measured and persisted safely |
| 4 | Cognitive engine | Attention, context integration, reasoning coordination and decision contracts |
| 5 | Mathematical intelligence | Deterministic linear algebra, calculus, probability, statistics and optimization services |
| 6 | Multimodal integration | Voice and vision observations enter the same typed cognitive request lifecycle |
| 7 | Unified neural runtime | One composition path with bounded scheduling, cancellation and observability |
| 8 | Verification | Regression, correctness, resource and latency benchmarks on supported hardware |

## Phase 1 scope

The first implementation adds a dependency-free, small-scale spiking foundation:

- Leaky integrate-and-fire (LIF) neuron with exact passive membrane integration.
- Directed synapse definitions with signed weights.
- Sparse event-driven network simulation.
- Deterministic step ordering and explicit input validation.
- Unit tests for membrane behavior, threshold crossing, refractory timing and
  synaptic event propagation.

This is a computational model, not a detailed biological neuron, and is not
connected to the live TARA request path yet. Runtime integration is gated on
separate profiling and contract tests.

## Constraints

- Preserve OmniRoute as the single configured LLM gateway.
- Do not remove or silently replace existing specialist modules.
- Keep security, approval and execution policy outside neural model code.
- Avoid mandatory heavyweight numerical or deep-learning dependencies until a
  measured implementation requirement justifies them.
- Do not claim learning, cognition, biological equivalence or performance gains
  without implementation and benchmark evidence.
- Keep each phase independently reviewable and regression-tested.

## Progress log

### Phase 1 — Neural processing foundation

- Added LIF neuron dynamics with exact passive membrane integration.
- Added signed directed synapse definitions.
- Added sparse deterministic spiking network with one-step event delivery.
- Added focused unit tests.
- Automated test execution and full repository regression remain to be run in
  a Python environment with the repository dependencies installed.

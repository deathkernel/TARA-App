# TN-86 — TARA Neural & Cognitive Architecture

> **Status:** Vision and architecture proposal — not an implementation claim.  
> **Repository:** [deathkernel/TARA-App](https://github.com/deathkernel/TARA-App)  
> **Core constraint:** OmniRoute remains the single gateway for all language-model inference.

TN-86 is the proposed brain-inspired intelligence architecture for TARA. Its goal is to make TARA more than a user interface that forwards prompts to an AI model: TARA should own a structured cognitive runtime for processing information, maintaining context, retrieving and consolidating memory, coordinating reasoning, learning from approved experience, and making decisions.

The name **TN-86** is inspired by the commonly cited estimate of roughly 86 billion neurons in the human brain. It is a design reference, not a claim that TARA will simulate 86 billion biological neurons.

---

## 1. Vision

Build a high-performance, modular, brain-inspired cognitive system inside the existing TARA-App repository.

TN-86 should aim to provide:

- **Neural processing:** configurable artificial-neuron and connection abstractions, signal/event processing, and measurable neural computation.
- **Cognition:** attention, context integration, reasoning coordination, executive control, and decision support.
- **Memory:** working, episodic, semantic, and associative memory with controlled retrieval and consolidation.
- **Learning:** measurable, bounded adaptation from approved feedback and experience.
- **Mathematical intelligence:** deterministic numerical and scientific computation through verified algorithms and suitable libraries.
- **Multimodal input:** a consistent path for text, images, and voice into TARA's cognitive workflow.
- **Performance:** bounded resource use, cancellation, observability, and repeatable benchmarks.

These are target capabilities. Each must be designed, implemented, tested, and documented before it is described as available.

## 2. OmniRoute is the only language-model gateway

All language-model requests made by TARA must go through **OmniRoute**.

~~~text
TARA Cognitive Runtime
        |
        +--> Cognitive modules, memory, policies and deterministic tools
        |
        +--> Model adapter
                 |
              OmniRoute
                 |
        Configured model/provider
~~~

Rules:

1. TARA must not call model providers directly for language-model inference.
2. TARA must not introduce a second LLM gateway or silently fall back to a direct provider API.
3. Model selection, provider routing, credentials, quotas, and provider fallback remain under OmniRoute's configuration and contract.
4. TARA owns its cognitive state, memory policies, neural-processing logic, orchestration, permissions, and local deterministic computation.
5. If OmniRoute is unavailable, TARA must report the model-service failure clearly. Any non-LLM deterministic capability that can safely operate independently may continue.
6. All model calls must use bounded timeouts, cancellation, input/output limits, and redacted audit metadata.

### Important technical boundary

OmniRoute is a **model gateway**, not by itself a general-purpose neural-network simulator or training framework. Routing LLM inference through OmniRoute does not mean custom spiking-neural-network calculations, synaptic updates, or model training execute inside OmniRoute.

Therefore, the intended separation is:

- **TN-86 cognitive/neural runtime:** implemented and executed within TARA's own application/runtime boundary.
- **Language-model inference:** accessed exclusively through OmniRoute.
- **Mathematical and deterministic computation:** performed by verified local algorithms/libraries where appropriate.

If a future OmniRoute deployment explicitly exposes a compatible neural-computation service, it can be evaluated through a documented adapter. It must not be assumed to exist.

## 3. Proposed architecture

| Subsystem | Responsibility | Target state |
|---|---|---|
| Neural Processing Engine | Neuron/synapse abstractions, signal/event flow, neural computation | Planned |
| Cognitive Engine | Attention, context integration, reasoning coordination, executive control | Planned |
| Memory Engine | Working, episodic, semantic and associative memory | Planned |
| Learning Engine | Feedback evaluation and bounded adaptive updates | Planned |
| Mathematical Engine | Linear algebra, calculus, probability, statistics and optimization | Planned |
| Multimodal Input Layer | Text, image and voice input normalization | Integration to be designed |
| Neural Runtime | Lifecycle, scheduling, resource limits, observability and cancellation | Planned |
| OmniRoute Adapter | The only route for LLM inference | Existing gateway boundary; verify current implementation before changes |

The subsystems must have explicit interfaces and testable responsibilities. Avoid creating empty modules or naming ordinary routing logic a neural network.

## 4. High-level processing flow

~~~text
User input
    |
Input normalization
    |
Cognitive context assembly
    |
Attention and task selection
    |
Memory retrieval <------> Memory consolidation
    |
Reasoning coordination <------> Mathematical Engine
    |
    +---- deterministic computation
    |
    +---- model request, when needed
              |
          OmniRoute
              |
       Configured LLM
              |
       Model response
    |
Evidence / policy / output validation
    |
Response or approval-gated action
    |
Approved feedback and experience record
    |
Bounded learning update
~~~

Not every request should require an LLM call. Deterministic tasks should use verified local computation when that is more accurate, faster, and safer. Model use should be explicit and observable.

## 5. Scientific and engineering principles

TN-86 must distinguish biological inspiration from biological equivalence.

- A software neuron abstraction is not automatically a biologically realistic neuron.
- A graph of nodes and edges is not automatically a functioning neural network.
- Memory storage is not automatically learning.
- Prompt history is not automatically episodic or semantic memory.
- Calling an LLM is not the same as training or adapting its weights.
- A successful demo is not evidence of accuracy, scalability, or speed.

Where scientifically justified, the design may evaluate spiking neural networks (SNNs), event-driven processing, Hebbian-style updates, spike-timing-dependent plasticity (STDP), and reinforcement-based learning. Each technique requires a defined mathematical model, bounded implementation, tests, and a clear statement of limitations. Do not claim these mechanisms are implemented until source code and tests demonstrate them.

## 6. Performance and hardware strategy

The target is efficient cognitive capability, not a literal simulation of the human brain.

- Never set 86 billion simulated neurons as a hardware requirement.
- Begin with small, measurable workloads and scale based on profiling.
- Keep memory, CPU, GPU, concurrency, and queue limits configurable.
- Support graceful operation when optional acceleration is unavailable.
- Benchmark latency, throughput, memory use, CPU/GPU use, retrieval quality, numerical correctness, and task success.
- Compare each optimization against a reproducible baseline.
- Do not claim that TN-86 is faster or more intelligent without benchmark evidence.

## 7. Safety, permissions, and data boundaries

TN-86 must preserve TARA's existing security and approval model.

- Neural or model output must never grant itself permission to execute an action.
- External actions remain subject to TARA-Security and explicit approval.
- Learning from user data or action outcomes must follow explicit data-retention and consent rules.
- Memory writes, edits, and forgetting must be auditable and policy-controlled.
- Secrets, credentials, raw approval tokens, and private user content must not be written to diagnostic logs.
- Model-generated plans and code remain proposals until separately validated and approved.

## 8. Integration rules for the existing TARA-App

This is an architectural evolution of the existing application, not permission to discard working features or perform an unrelated rewrite.

1. Keep the existing TARA-App repository as the single source of implementation.
2. Preserve the existing UI, specialist capabilities, OmniRoute integration, and security boundaries unless a reviewed change proves a modification is necessary.
3. Inspect current modules and their actual runtime connections before designing replacements.
4. Consolidate overlapping orchestration paths only after tracing callers, contracts, and tests.
5. Introduce interfaces incrementally; do not add placeholder implementations.
6. Keep backward compatibility where practical and document any intentional migration.
7. Do not add direct Ollama, Gemini, or other provider inference paths outside OmniRoute.

## 9. Proposed implementation sequence

This sequence is a plan, not a statement that work has started.

1. **Repository and scientific audit** — map existing code, runtime paths, dependencies, data flows, tests, and scientific gaps.
2. **Architecture specification** — define mathematical models, interfaces, data contracts, resource budgets, and acceptance tests.
3. **Neural Processing Engine** — implement the smallest useful, testable neural-processing foundation.
4. **Memory and Learning integration** — define retrieval, consolidation, feedback, and controlled adaptation.
5. **Cognitive Engine** — connect attention, context, reasoning coordination, and decision support.
6. **Mathematical Engine** — add verified numerical/scientific computation and correctness tests.
7. **Multimodal integration** — connect text, vision, and voice through the cognitive input contracts.
8. **Unified runtime and benchmarks** — add scheduling, cancellation, observability, resource controls, and reproducible evaluations.

Each phase must have acceptance criteria and tests before the next phase is treated as complete.

## 10. Definition of done

A subsystem is complete only when:

- its design and mathematical assumptions are documented;
- its implementation is connected to the real TARA runtime;
- unit, integration, failure-path, and resource-bound tests pass;
- security and approval behavior is verified;
- performance and correctness benchmarks are recorded;
- documentation accurately labels implemented, partial, and pending capabilities.

## 11. Current status

This document records the TN-86 vision and proposed architecture only. It does **not** mean that a new neural engine, SNN, STDP learning system, independent model, or biological-scale simulation currently exists in TARA.

The existing project documentation remains authoritative for the current implementation status. Update this document as architecture decisions are approved and implementation evidence becomes available.

---

**Guiding principle:** TARA owns the cognitive system. OmniRoute remains the single gateway for language-model inference. TN-86 should be scientifically grounded, resource-aware, testable, secure, and built incrementally.

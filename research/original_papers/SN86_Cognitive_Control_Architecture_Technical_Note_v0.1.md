# SN-86: A Bounded Cognitive Control Architecture for a Local-First Agent

**Technical research note v0.1 — 14 November 2026**  
**Status:** Proposed architecture and initial software realization; not peer-reviewed  
**Authors:** SN-86 Project Contributors

## Abstract
This note specifies a small deterministic cognitive-control layer for a local-first agent. It combines bounded memory retrieval, transparent attention allocation, deadline- and dependency-aware goal scheduling, evidence-adjusted action scoring with abstention, and a staged coordinator. The design is informed by cognitive-architecture research, working-memory and attention theory, executive-control literature, and computational work on episodic/semantic integration. It does not claim biological equivalence, human-level cognition, calibrated probabilities, or autonomous action authority. Language-model inference remains behind SITA's existing OmniRoute gateway; tool execution and approval remain in existing security controls.

**Keywords:** cognitive architecture, attention, working memory, episodic memory, semantic memory, executive control, abstention, local-first agents

## 1. Motivation
Cognitive-architecture surveys describe cognition as coordinated capabilities including perception, attention, memory, learning, reasoning and action selection, rather than one undifferentiated component [1]. ACT-R provides a modular precedent: specialized modules communicate through buffers, and production rules select responses to the current state [2]. SN-86 Phase 4 translates a subset of these ideas into a bounded Python control layer; it is not a complete theory of mind.

## 2. Evidence and design implications

### 2.1 Cognitive architecture
Kotseruba and Tsotsos survey a broad range of cognitive architectures and identify recurring components and open gaps in attention, grounding and cognitive control [1]. Anderson et al.'s ACT-R account uses modules, buffers and production-rule selection to coordinate behavior [2].  
**Implication:** keep memory, attention, goals and decisions as typed modules with explicit contracts.

### 2.2 Attention and working memory
Oberauer distinguishes attention as a limited resource from attention as selective information processing, and reviews evidence for filtering and selecting working-memory contents [3]. Lindsay reviews attention across psychology, neuroscience and machine learning, cautioning against treating machine-learning attention as automatically equivalent to biological attention [4]. Executive-control reviews describe reciprocal but partially dissociable relationships between attention, working memory and control [5].  
**Implication:** enforce a finite context budget and use transparent selection. The weights below are engineering heuristics, not biological parameters.

### 2.3 Executive control
Egner describes cognitive stability (protecting a task from distraction) and flexibility (switching when circumstances change), discussing recency and episodic recognition as control signals [6].  
**Implication:** maintain explicit goal state, urgency, dependencies and deadline pressure; recency alone is insufficient.

### 2.4 Episodic and semantic integration
The EGO framework models rapid episodic learning, slower semantic learning and recurrent task context that biases retrieval and processing [7]. Long-horizon agent research has also explored coupling memory retrieval with reasoning and policy generation [8].  
**Implication:** keep event-specific memory distinct from generalized knowledge while allowing current context to influence retrieval. These papers motivate design choices; they do not prove SN-86 will generalize.

## 3. Proposed architecture
1. Validate a typed request and explicit context budget.
2. Retrieve a bounded candidate set from memory.
3. Convert candidate metadata into normalized attention features.
4. Rank candidates and construct compact active context.
5. Obtain candidate actions from an explicitly injected reasoning provider.
6. Score candidates and abstain when evidence or score separation is inadequate.
7. Return a traceable result; do not execute the selected action.

A provider adapter may delegate proposal generation to OmniRoute. SN-86 does not introduce a second model gateway.

## 4. Mathematical specification

### 4.1 Attention
For candidate i, let R be query relevance, I importance, T recency, S salience and C source confidence. Each feature lies in [0,1].

A(i) = 0.35R(i) + 0.20I(i) + 0.15T(i) + 0.15S(i) + 0.15C(i)

The coefficients sum to one. Candidates are ordered by descending score, with stable IDs breaking ties. This is a deterministic prioritization heuristic, not a neural attention softmax or a validated model of human attention.

### 4.2 Temporal decay
For elapsed age delta-t >= 0 and half-life h > 0:

T(i) = exp(-ln(2) * delta-t / h)

At delta-t = h, recency is one half. Future timestamps are treated as age zero.

### 4.3 Goal priority
For pending goal g:

P(g) = 0.35I(g) + 0.30U(g) + 0.20R(g) + 0.15D(g)

I, U and R are normalized importance, urgency and relevance. Deadline pressure D is 1 if overdue; otherwise it is 1 / (1 + remaining_seconds / 3600) when a deadline exists, and 0 when none exists. Goals with incomplete dependencies are withheld from the ready queue.

### 4.4 Decision and abstention
For candidate action a:

Q(a) = clip[0,1](U(a) * C(a) * E(a) - lambda * Risk(a))

Select the highest-scoring action only if Q(max) >= minimum_score and, when a runner-up exists, Q(max) - Q(second) >= minimum_margin. Otherwise abstain. These are policy values, not calibrated probabilities; calibration requires task-specific labeled data and separate evaluation.

## 5. Software realization
The initial package adds:
- cognition/models.py: immutable request, feature, context, goal and decision contracts.
- cognition/attention.py: deterministic weighted scoring and stable ranking.
- cognition/context.py: memory recall adapter, exponential recency and bounded context.
- cognition/goals.py: bounded goal registry, dependency gating and deadline-aware prioritization.
- cognition/decision.py: evidence-adjusted ranking and explicit abstention.
- cognition/coordinator.py: staged orchestration with an injected proposal provider.
- tests/test_sn86_cognition.py: focused tests for ranking, context, recency, goals, decisions and coordinator behavior.

The coordinator does not call tools or execute actions. Persistent memory changes and sensitive operations remain subject to SITA's approval layer. Neural and plasticity primitives remain lower-level capabilities; this phase does not assert a validated mapping from spiking activity to symbolic attention or automatically train on conversations.

## 6. Falsifiable hypotheses and evaluation
These are hypotheses, not results:
- H1: bounded attention context reduces irrelevant context items versus recency-only selection on a labeled retrieval set.
- H2: dependency gating reduces invalid task-order proposals versus urgency-only sorting.
- H3: score and margin thresholds reduce unsupported selections at the cost of increased abstentions.
- H4: explicit stage traces and feature contributions improve decision audit reproducibility.

Proposed experiments: build a versioned evaluation set; compare attention against recency-only, relevance-only and uniform baselines; compare goal scheduling against urgency-only and importance-only baselines; sweep decision thresholds and report coverage, selective accuracy, risk-weighted error and abstention rate; run feature ablations; record latency, peak memory and repeatability. Keep tuning and test splits separate. No experiment results are claimed. Tests are authored but have not yet been executed.

## 7. Limitations and safety
- Retrieval quality depends on the existing memory engine; semantic embeddings are not added here.
- Attention and goal weights are manual defaults requiring empirical tuning.
- Confidence and evidence strength are upstream inputs and are not automatically calibrated.
- Selected options are advisory; authorization and execution remain outside this package.
- Without an injected proposal provider the coordinator abstains rather than fabricating reasoning.
- The design does not simulate 86 billion neurons, reproduce consciousness or establish human-level intelligence.
- Neural-to-symbolic integration remains an open research and engineering task.

## 8. Conclusion
Phase 4 establishes an inspectable cognitive-control layer around the earlier memory, neural and learning foundations. Its contribution at this stage is a concrete, bounded and testable software architecture with explicit uncertainty handling and safety boundaries. Whether it improves SITA task performance remains an empirical question.

## References
[1] I. Kotseruba and J. K. Tsotsos, “40 years of cognitive architectures: core cognitive abilities and practical applications,” Artificial Intelligence Review, 2018. https://doi.org/10.1007/s10462-018-9646-y

[2] J. R. Anderson, D. Bothell, M. D. Byrne, S. Douglass, C. J. Lebiere and Y. Qin, “An Integrated Theory of the Mind,” Psychological Review, 111, 1036–1060, 2004. https://doi.org/10.1037/0033-295X.111.4.1036

[3] K. Oberauer, “Working Memory and Attention – A Conceptual Analysis and Review,” Journal of Cognition, 2, 36, 2019. https://doi.org/10.5334/joc.58

[4] G. W. Lindsay, “Attention in Psychology, Neuroscience, and Machine Learning,” Frontiers in Computational Neuroscience, 14, 29, 2020. https://doi.org/10.3389/fncom.2020.00029

[5] M. N. Toba, T. S. Malkinson, H. Howells, M.-A. Mackie and A. Spagna, “Same, Same but Different? A Multi-Method Review of the Processes Underlying Executive Control,” Neuropsychology Review, 34, 418–454, 2023. https://doi.org/10.1007/s11065-023-09577-4

[6] T. Egner, “Principles of cognitive control over task focus and task switching,” Nature Reviews Psychology, 2, 702–714, 2023. https://doi.org/10.1038/s44159-023-00234-4

[7] T. Giallanza, D. I. Campbell and J. D. Cohen, “Toward the Emergence of Intelligent Control: Episodic Generalization and Optimization,” Open Mind, 8, 688–722, 2024. https://doi.org/10.1162/opmi_a_00143

[8] L. Yang, T. Guan, Y. Ma, Z. Li, Z. Fang and F. Wang, “Cognitive Modeling for Long-Horizon Agent Learning via Integrated Long-Term Memory and Reasoning,” International Conference on Communication Networks and Machine Learning, 2026. https://doi.org/10.1109/CNML68938.2026.11452287

**Research integrity:** This project technical note describes a proposed design and initial code realization. It is not represented as a peer-reviewed publication or as evidence that the hypotheses have been confirmed.

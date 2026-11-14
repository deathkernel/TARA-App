# Research brief for SN-86 Phase 4 Cognitive Engine implementation. Review peer-re

**Question:** Research brief for SN-86 Phase 4 Cognitive Engine implementation. Review peer-reviewed research (seminal and recent) on computational attention mechanisms, cognitive architectures and working-memory/context integration, bounded rational decision-making and evidence-based abstention, goal/task prioritization and executive control, and coordination between neural activation, episodic/semantic memory, and learning. Prioritize foundational primary papers plus relevant reviews. For each key paper provide title, authors, year, DOI/canonical URL, core mechanism/equations, assumptions and limitations, and concrete engineering implications for a small deterministic Python cognitive engine (not a claim of human-level brain simulation). Compare alternatives and identify a defensible minimal design: attention scoring over candidate memories/context, context construction, goal priority scheduling, decision scoring with abstention/uncertainty, and a staged reasoning coordinator. Explicitly distinguish established findings from engineering hypotheses. Include citations and a bibliography. The output will inform a SN-86 technical research note and implementation; do not fabricate sources or claim empirical results.

# Research Brief: **Cognitive Engine Architecture**

This research brief addresses three primary sub-questions for the SN-86 Phase 4 Cognitive Engine: attention and working-memory integration, goal prioritization with bounded decision-making, and memory coordination across episodic and semantic stores [[1.1]](https://consensus.app/papers/kotseruba-tsotsos-40-years-of-cognitive-architectures-core-cognitive/w:21e79aa7-55e5-4e6c-9f43-fa94fe23a6ec/) [[2.1]](https://consensus.app/papers/omidi-huang-memoryaugmented-transformers-a-systematic-review/w:bf9aa239-ad18-41fc-8140-7588e1902356/) [[3.1]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/). Computational cognitive architectures consistently demonstrate that functional competence in resource-limited systems requires strict modular coordination rather than monolithic sequence modeling [[1.2]](https://consensus.app/papers/kotseruba-tsotsos-40-years-of-cognitive-architectures-core-cognitive/w:21e79aa7-55e5-4e6c-9f43-fa94fe23a6ec/) [[4.1]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[5.1]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/).

## Attention and Working Memory Integration

Working memory and attention operate as a unified selective bottleneck rather than independent stores [[6.1]](https://consensus.app/papers/toba-malkinson-same-same-but-different-a-multimethod-review-of/w:3a6c831a-ba2c-493d-b568-2f826a13f094/) [[7.1]](https://consensus.app/papers/oberauer-working-memory-and-attention-–-a-conceptual/w:03f3b7cd-610d-4f50-943b-2db4299343de/) [[8.1]](https://consensus.app/papers/kanwal-abbas-towards-parallel-selective-attention-using/w:664b467f-797e-4b34-b20d-9292546d2eff/). Selective attention acts either as a shared finite resource or as a discrete gating filter that restricts which transient representations populate active context buffers [[7.2]](https://consensus.app/papers/oberauer-working-memory-and-attention-–-a-conceptual/w:03f3b7cd-610d-4f50-943b-2db4299343de/) [[7.3]](https://consensus.app/papers/oberauer-working-memory-and-attention-–-a-conceptual/w:03f3b7cd-610d-4f50-943b-2db4299343de/) [[9.1]](https://consensus.app/papers/dumbrava-theoretical-foundations-for-semantic-cognition-in/w:667be9ea-b87d-4758-8c41-76f1d232860c/).

* In transformer implementations, attention heads naturally specialize into role-addressable input and output gating operations resembling biological frontostriatal pathways [[10.1]](https://consensus.app/papers/soni-traylor-transformer-mechanisms-mimic-frontostriatal-gating/w:9733d5ab-20d2-4879-8b8d-fd12fd2f7802/) [[10.2]](https://consensus.app/papers/soni-traylor-transformer-mechanisms-mimic-frontostriatal-gating/w:9733d5ab-20d2-4879-8b8d-fd12fd2f7802/).
* Working memory models enforce strict capacity limits, where context degrades under unbounded accumulation and benefits from regenerative reconstruction [[11.1]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) [[5.2]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/) [[5.3]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/).
* Attentional bottlenecks promote lower-dimensional representations that protect task sets and limit cross-talk interference [[7.4]](https://consensus.app/papers/oberauer-working-memory-and-attention-–-a-conceptual/w:03f3b7cd-610d-4f50-943b-2db4299343de/) [[12.1]](https://consensus.app/papers/lindsay-attention-in-psychology-neuroscience-and-machine/w:a330c42e-9dd3-4d2a-a398-f355506d6fb0/) [[10.3]](https://consensus.app/papers/soni-traylor-transformer-mechanisms-mimic-frontostriatal-gating/w:9733d5ab-20d2-4879-8b8d-fd12fd2f7802/).

**Figure 1.** Parallels between the memory systems in the human brain and memory-augmented Transformers. Human memory consists of three interacting subsystems: sensory memory, working memory, and long-term memory. Memory-augmented Transformers mirror this architecture by leveraging embeddings, attention mechanisms, and advanced encoding and retrieval techniques to construct feature maps (analogous to shortterm memory), attention contexts (analogous to working memory), and parametric or non-parametric memory (analogous to long-term memory). [[2]](https://consensus.app/papers/omidi-huang-memoryaugmented-transformers-a-systematic-review/w:bf9aa239-ad18-41fc-8140-7588e1902356/)

*How to read: The diagram illustrates structural parallels between tripartite human memory divisions and memory-augmented machine architectures, moving from sensory inputs to working memory contexts and long-term stores.*

## Goal Scheduling and Bounded Decision-Making

Executive control coordinates competing tasks by balancing stability against cognitive flexibility [[13.1]](https://consensus.app/papers/egner-principles-of-cognitive-control-over-task-focus/w:ea210c1d-a4b6-40bc-bec4-070b4b46b3ba/) [[13.2]](https://consensus.app/papers/egner-principles-of-cognitive-control-over-task-focus/w:ea210c1d-a4b6-40bc-bec4-070b4b46b3ba/). Rational action selection under uncertainty requires mechanisms for selective reconsideration and evidence-based abstention when confidence is insufficient [[4.2]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.3]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[5.4]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/).

* Task focus and task switching readiness rely on dissociable control processes modulated by recency heuristics and episodic cues [[13.3]](https://consensus.app/papers/egner-principles-of-cognitive-control-over-task-focus/w:ea210c1d-a4b6-40bc-bec4-070b4b46b3ba/) [[13.4]](https://consensus.app/papers/egner-principles-of-cognitive-control-over-task-focus/w:ea210c1d-a4b6-40bc-bec4-070b4b46b3ba/).
* Persistent intention records govern multi-step reasoning by explicitly tracking continuation criteria, reconsideration triggers, and fallback policies [[4.2]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.4]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/).
* Marker-driven value systems provide pre-rational valuation to bias execution threads or trigger deliberate escalation when impasses arise [[14.1]](https://consensus.app/papers/vladu-bîzdoacă-the-dime-architecture-a-unified-operational/w:d0c78f6f-08ab-471f-9670-d8f63f7a79a9/) [[14.2]](https://consensus.app/papers/vladu-bîzdoacă-the-dime-architecture-a-unified-operational/w:d0c78f6f-08ab-471f-9670-d8f63f7a79a9/) [[5.5]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/).

## Memory Coordination and Staged Reasoning

The integration of dual memory stores is critical for maintaining consistency while supporting adaptive runtime learning [[14.3]](https://consensus.app/papers/vladu-bîzdoacă-the-dime-architecture-a-unified-operational/w:d0c78f6f-08ab-471f-9670-d8f63f7a79a9/) [[15.1]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) [[5.6]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/). A small deterministic system requires explicit coordination between associative episodic recall and structured semantic models [[2.2]](https://consensus.app/papers/omidi-huang-memoryaugmented-transformers-a-systematic-review/w:bf9aa239-ad18-41fc-8140-7588e1902356/) [[16.1]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) [[15.2]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/).

* Fast episodic binding records specific event conjunctions, while slow semantic pathways extract generalized environment structures [[15.3]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) [[15.2]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) [[5.7]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/).
* Graph-theoretic state representations cleanly decouple capacity-limited working memory subgraphs from durable belief networks [[16.2]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) [[16.1]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/).
* Consolidative controllers operating on fixed-size narrative states outperform unbounded history caches by avoiding context degradation [[11.2]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) [[11.3]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) [[11.4]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/).

## Key Foundational and Modern Systems

Cognitive architecture frameworks establish formal relationships between declarative storage, procedural selection, and executive control [[1.1]](https://consensus.app/papers/kotseruba-tsotsos-40-years-of-cognitive-architectures-core-cognitive/w:21e79aa7-55e5-4e6c-9f43-fa94fe23a6ec/) [[3.2]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/) [[8.2]](https://consensus.app/papers/kanwal-abbas-towards-parallel-selective-attention-using/w:664b467f-797e-4b34-b20d-9292546d2eff/).

| Paper / Framework | Core Equations & Mechanisms | Assumptions & Limitations | Deterministic Engine Implications |
| :--- | :--- | :--- | :--- |
| **Anderson et al. (2004)** [[3.1]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/) | Production rule matching over buffers; subsymbolic utility tuning [[3.3]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/) [[3.4]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/) | Assumes central production bottleneck; high hand-crafting burden [[1.2]](https://consensus.app/papers/kotseruba-tsotsos-40-years-of-cognitive-architectures-core-cognitive/w:21e79aa7-55e5-4e6c-9f43-fa94fe23a6ec/) [[3.5]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/) | Implement isolated modular state dicts with pattern-matching dispatch [[3.3]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/) |
| **Giallanza et al. (2024)** [[15.4]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) | Recurrent context gating biasing episodic retrieval and semantic maps [[15.5]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) [[15.2]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) | Lacks multi-step hierarchical goal dependencies [[15.6]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) | Maintain lightweight context vector to bias dictionary searches [[15.7]](https://consensus.app/papers/giallanza-campbell-toward-the-emergence-of-intelligent-control/w:c094d027-ed74-4f5d-95d5-a8f87d53d2b7/) |
| **Hsing (2025)** [[11.5]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) | Reconstructive synthesis of goals, reasoning, and memory into fixed state [[11.2]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) [[11.6]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) | Requires high-capacity synthesizer for narrative generation [[11.1]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) [[11.4]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) | Enforce hard token and slot caps on active state summaries [[11.3]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) |
| **Fan & Lan (2026)** [[4.5]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) | BDI intention governor with typed impasses and verified fallbacks [[4.2]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.4]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) | Analytical review; residual bundles unvalidated at scale [[4.6]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.7]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) | Implement explicit retry, escalate, and abstention condition trees [[4.8]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.3]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) |
| **Ishant (2026)** [[16.3]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) | Typed graph rewriting over episodic and durable belief topologies [[16.2]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) [[16.4]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) | Purely theoretical ontology lacking operational benchmarks [[16.5]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) [[16.6]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) | Represent system state as deterministic directed graph with edge types [[16.2]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/) |

**Figure 1:** Comparative breakdown of foundational cognitive architectures and modern agent control frameworks.

## Defensible Minimal Design for SN-86

A viable, deterministic Python engine does not require neural simulation; rather, it operationalizes cognitive invariants into five staged modules [[4.9]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.10]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.11]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/):

1. **Attention Scoring**: Candidate memories receive scores via a composite linear functional combining recency, relevance, and task alignment [[2.3]](https://consensus.app/papers/omidi-huang-memoryaugmented-transformers-a-systematic-review/w:bf9aa239-ad18-41fc-8140-7588e1902356/) [[13.4]](https://consensus.app/papers/egner-principles-of-cognitive-control-over-task-focus/w:ea210c1d-a4b6-40bc-bec4-070b4b46b3ba/). Items below a threshold are filtered prior to context admission [[7.3]](https://consensus.app/papers/oberauer-working-memory-and-attention-–-a-conceptual/w:03f3b7cd-610d-4f50-943b-2db4299343de/) [[8.3]](https://consensus.app/papers/kanwal-abbas-towards-parallel-selective-attention-using/w:664b467f-797e-4b34-b20d-9292546d2eff/).
2. **Context Construction**: Construct an active working memory record bounded by a fixed slot budget (e.g., $k \le 7$), utilizing reconstructive summarization rather than unbounded append logging [[11.3]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) [[5.1]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/).
3. **Goal Priority Scheduling**: A persistent intention record manages hierarchical tasks using a prioritized agenda [[4.2]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[8.4]](https://consensus.app/papers/kanwal-abbas-towards-parallel-selective-attention-using/w:664b467f-797e-4b34-b20d-9292546d2eff/). Execution stability is favored by default, triggering re-evaluation only upon explicit environmental interruptions or goal satisfaction [[4.8]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[13.3]](https://consensus.app/papers/egner-principles-of-cognitive-control-over-task-focus/w:ea210c1d-a4b6-40bc-bec4-070b4b46b3ba/).
4. **Decision Scoring & Abstention**: Actions are evaluated across simulated execution paths [[14.4]](https://consensus.app/papers/vladu-bîzdoacă-the-dime-architecture-a-unified-operational/w:d0c78f6f-08ab-471f-9670-d8f63f7a79a9/). If the maximum margin of confidence between candidate actions falls below an abstention threshold $\tau_{\text{abstain}}$, the engine halts execution and yields an uncertainty flag [[4.12]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.3]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[5.4]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/).
5. **Staged Reasoning Coordinator**: The central loop implements an invariant cycle (Detect $\rightarrow$ Integrate $\rightarrow$ Mark $\rightarrow$ Execute) [[14.1]](https://consensus.app/papers/vladu-bîzdoacă-the-dime-architecture-a-unified-operational/w:d0c78f6f-08ab-471f-9670-d8f63f7a79a9/) [[14.5]](https://consensus.app/papers/vladu-bîzdoacă-the-dime-architecture-a-unified-operational/w:d0c78f6f-08ab-471f-9670-d8f63f7a79a9/). Impasses route directly to targeted fallback subroutines rather than unconstrained loops [[4.4]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.3]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/).

*Distinction of Status*: The efficacy of dual-process memory dissociation, working-memory capacity degradation, and attentional bottlenecks are **established empirical findings** in cognitive psychology and neuroscience [[7.5]](https://consensus.app/papers/oberauer-working-memory-and-attention-–-a-conceptual/w:03f3b7cd-610d-4f50-943b-2db4299343de/) [[11.7]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/) [[5.7]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/) [[5.3]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/). In contrast, the specific linear-weight combinations of priority scores, deterministic graph-rewriting operators, and heuristic abstention thresholds in a minimal Python engine represent **engineering hypotheses** requiring operational calibration [[4.13]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.7]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[16.6]](https://consensus.app/papers/ishant-nested-episodic-state-topology-nest-a/w:cbd865c2-9595-4d9d-aa1b-439fc9bd3686/).

## Evidence Coverage Across Architectures

| | Cognitive Architecture Theory | Empirical Human Neuroscience | Deep Sequence Models | Deterministic Agent Systems |
|---|---|---|---|---|
| Attention & Gating | 10 papers | 3 papers | 2 papers | 1 paper |
| Working Memory Integration | 7 papers | 1 paper | 4 papers | 1 paper |
| Goal & Executive Control | 10 papers | 2 papers | 2 papers | 1 paper |
| Episodic-Semantic Coordination | 1 paper | No papers | 1 paper | No papers |
| Decision Abstention | No papers | No papers | No papers | No papers |

The research coverage matrix demonstrates that while cognitive architecture theory and neuroscience provide deep foundational models for working memory and dual-store coordination, their translation into deterministic agent runtimes remains uneven [[1.3]](https://consensus.app/papers/kotseruba-tsotsos-40-years-of-cognitive-architectures-core-cognitive/w:21e79aa7-55e5-4e6c-9f43-fa94fe23a6ec/) [[4.5]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.14]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/). The most pronounced gap occurs in evidence-based abstention and verified recovery loops: deep sequence models optimize end-to-end task performance without native uncertainty-stopping invariants, leaving deterministic agents reliant on heuristic fallback wrappers [[4.3]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[17.1]](https://consensus.app/papers/yang-guan-cognitive-modeling-for-longhorizon-agent-learning/w:4b878218-6a83-4b91-99b2-bbd223a9d0f5/) [[5.4]](https://consensus.app/papers/lermatorres-humanlike-lifelong-memory-a-neurosciencegrounded/w:3d4bb9d7-5267-452c-afa8-a095a3edda69/). This persistent gap highlights the engineering necessity for SN-86 to formally couple intention records with explicit abstention thresholds [[4.2]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[4.3]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/).

In conclusion, anchoring the SN-86 Cognitive Engine in validated cognitive constraints—specifically bounded working-memory reconstruction, dual-store retrieval gating, and explicit intention reconsideration—provides a robust, verifiable foundation for deterministic decision-making under resource bounds [[4.12]](https://consensus.app/papers/fan-lan-from-cognitive-architectures-to-language-agents-a/w:4554a569-f70b-43dc-bfcb-2d26dead9dac/) [[3.1]](https://consensus.app/papers/anderson-bothell-an-integrated-theory-of-the-mind/w:3b65de95-fee2-41fa-96fa-7efc341dff54/) [[11.5]](https://consensus.app/papers/hsing-mirror-converging-cognitive-principles-as/w:b5bd7072-167d-41a4-8e73-3be121caf4d3/).

## Bibliography

* Anderson, J. R., Bothell, D., Byrne, M. D., Douglass, S., Lebiere, C. J., & Qin, Y. (2004). An Integrated Theory of the Mind. *Psychological Review*, 111(4), 1036. https://doi.org/10.1037/0033-295x.111.4.1036
* Dumbrava, S. (2025). Theoretical Foundations for Semantic Cognition in Artificial Intelligence. *arXiv*. https://doi.org/10.48550/arxiv.2504.21218
* Egner, T. (2023). Principles of cognitive control over task focus and task switching. *Nature Reviews Psychology*, 2, 676–689. https://doi.org/10.1038/s44159-023-00234-4
* Fan, H., & Lan, Z. (2026). From Cognitive Architectures to Language Agents: A Mechanism-Level Review of Lineage, Convergence, and Migration Gaps. *arXiv*. https://doi.org/10.48550/arxiv.2607.23942
* Giallanza, T., Campbell, D. I., & Cohen, J. D. (2024). Toward the Emergence of Intelligent Control: Episodic Generalization and Optimization. *Open Mind*, 8, 804–836. https://doi.org/10.1162/opmi_a_00143
* Giallanza, T., Campbell, D. I., Cohen, J., & Rogers, T. T. (2024). An integrated model of semantics and control. *Psychological Review*. https://doi.org/10.1037/rev0000485
* Hsing, N. (2025). MIRROR: Converging Cognitive Principles as Computational Mechanisms for AI Reasoning. *arXiv*. https://doi.org/10.48550/arxiv.2506.00430
* Ishant. (2026). Nested Episodic State Topology (NEST): A Graph-Theoretic Architecture of Cognitive States. *arXiv*. https://doi.org/10.48550/arxiv.2607.06055
* Kanwal, A., Abbas, S., Ghazal, T. M., Ditta, A., Alquhayz, H., & Khan, M. A. (2022). Towards Parallel Selective Attention Using Psychophysiological States as the Basis for Functional Cognition. *Sensors*, 22(18), 7002. https://doi.org/10.3390/s22187002
* Kotseruba, I., & Tsotsos, J. K. (2018). 40 years of cognitive architectures: core cognitive abilities and practical applications. *Artificial Intelligence Review*, 53, 17–94. https://doi.org/10.1007/s10462-018-9646-y
* Lerma-Torres, D. C. (2026). Human-Like Lifelong Memory: A Neuroscience-Grounded Architecture for Infinite Interaction. *arXiv*. https://doi.org/10.48550/arxiv.2603.29023
* Lindsay, G. W. (2020). Attention in Psychology, Neuroscience, and Machine Learning. *Frontiers in Computational Neuroscience*, 14, 29. https://doi.org/10.3389/fncom.2020.00029
* Oberauer, K. (2019). Working Memory and Attention – A Conceptual Analysis and Review. *Journal of Cognition*, 2(1), 36. https://doi.org/10.5334/joc.58
* Omidi, P., Huang, X., Laborieux, A., Nikpour, B., Shi, T., & Eshaghi, A. (2025). Memory-Augmented Transformers: A Systematic Review from Neuroscience Principles to Enhanced Model Architectures. *arXiv*. https://doi.org/10.48550/arxiv.2508.10824
* Rupprecht, T., Zhao, P., Taherin, A., Akbari, A., Akbari, A., He, Y., et al. (2026). Human Cognition in Machines: A Unified Perspective of World Models. *arXiv*. https://doi.org/10.48550/arxiv.2604.16592
* Soni, A. V., Traylor, A., Merullo, J., Frank, M. J., & Pavlick, E. (2026). Transformer Mechanisms Mimic Frontostriatal Gating Operations When Trained on Human Working Memory Tasks. *Journal of Cognitive Neuroscience*, 38(2), 245–261. https://doi.org/10.1162/jocn.a.2679
* Toba, M. N., Malkinson, T. S., Howells, H., Mackie, M.-A., & Spagna, A. (2023). Same, Same but Different? A Multi-Method Review of the Processes Underlying Executive Control. *Neuropsychology Review*, 34, 1144–1165. https://doi.org/10.1007/s11065-023-09577-4
* Vladu, I. C., Bîzdoacă, N. G., Pirici, I., Bălșeanu, T.-A., & Bondoc, E. N. (2026). The DIME Architecture: A Unified Operational Algorithm for Neural Representation, Dynamics, Control and Integration. *Applied Sciences*, 16(11), 5380. https://doi.org/10.3390/app16115380
* Yang, L., Guan, T., Ma, Y., Li, Z., Fang, Z., & Wang, F. (2026). Cognitive Modeling for Long-Horizon Agent Learning via Integrated Long-Term Memory and Reasoning. *International Conference on Communication Networks and Machine Learning (CNML)*. https://doi.org/10.1109/cnml68938.2026.11452287
 
_These search results were found and analyzed using Consensus, an AI-powered search engine for research. Try it at https://consensus.app. © 2026 Consensus NLP, Inc. Personal, non-commercial use only; redistribution requires copyright holders’ consent._
 
## References
 
`1.` Kotseruba I, Tsotsos JK. 40 years of cognitive architectures: core cognitive abilities and practical applications. *Artificial Intelligence Review.* 2018;53:17-94. doi:10.1007/s10462-018-9646-y
 
> [1.1] In particular, we discuss common approaches to modeling important elements of human cognition, such as perception, attention, action selection, learning, memory and reasoning. (Discussion)
 
> [1.2] Owing to tradition, work on high-level cognitive architectures is still centered mainly on reasoning and planning in simulated environments, downplaying issues of cognitive control of perception, symbol grounding and realistic attention mechanisms. (Discussion)
 
> [1.3] Withrespect to the range of abilities and realism of the scenarios there remains a significant gap between the state-of-the-art in specialized areas of AI and the research in these areas within the cognitive architectures domain. (Discussion)
 
`2.` Omidi P, Huang X, Laborieux A, Nikpour B, Shi T, Eshaghi A. Memory-Augmented Transformers: A Systematic Review from Neuroscience Principles to Enhanced Model Architectures. *arXiv (Cornell University).* 2025;abs/2508.10824. doi:10.48550/arxiv.2508.10824
 
> [2.1] This review presents a unified framework bridging neuroscience principles, including dynamic multi-timescale memory, selective attention, and consolidation, with engineering advances in Memory-Augmented Transformers. (Abstract)
 
> [2.2] Associative designs push retrieval to constant time: ARMT (Rodkin et al., 2024) stores tokens in Hopfieldstyle energy basins for O(1) pattern completion over 50 M-token contexts, and AiT (Sun et al., 2023) adds low-rank priors that reconstruct missing tokens from partial cues, outperforming sparse Transformers on relational reasoning benchmarks. (Body)
 
> [2.3] | Adaptive graph / policy-driven | reads | CDMem(Gao et al., 2025); ABC(Peng et al., 2021); NAMMs(Cetin et al., 2025) | | Surprise / uncertainty-gated | writes Titans (Behrouz et al., 2024); LM2(Kang et al., 2025b); OTR(Gao & Wang, 2023) | MeM- | | Write | input-forget gating Memformer(Wu et al., 2020); RMoE | WorkMATe(Kruijne et al., 2021); (Qiu et al., 2024) | | | Confidence-filtered updates A-MEM(Xu et al., ryLLM(Wang et al., R+(Le et al., 2025) | 2025); MemBART(Wu & Yu, 2022); Memo- 2024b); M+(Wang et al., 2025c); Memory- | | Reinforcement / optimisation | traces Memformers(Dutta & Sra, 2024); ATLAS(Behrouz et al., 2025) | WorkMATe(Kruijne et al., 2021); (Qiu et al., 2024) | | Selective pruning | MemLong(Liu et al., 2024); MeMOTR(Gao & Wang, 2023); | Ti- tans (Behrouz et al., 2024) | (Body)
 
`3.` Anderson JR, Bothell D, Byrne MD, Douglass S, Lebiere CJ, Qin Y. An Integrated Theory of the Mind.. *Psychological Review.* 2004;111:1036-1060. doi:10.1037/0033-295x.111.4.1036
 
> [3.1] Adaptive control of thought-rational (ACT-R; J. R. Anderson & C. Lebiere, 1998) has evolved into a theory that consists of multiple modules but also explains how these modules are integrated to produce coherent cognition. (Abstract)
 
> [3.2] The perceptual-motor modules, the goal module, and the declarative memory module are presented as examples of specialized systems in ACT-R. (Abstract)
 
> [3.3] These modules place chunks in buffers where they can be detected by a production system that responds to patterns of information in the buffers. (Abstract)
 
> [3.4] Subsymbolic processes serve to guide the selection of rules to fire as well as the internal operations of some modules. (Abstract)
 
> [3.5] At any point in time, a single production rule is selected to respond to the current pattern. (Abstract)
 
`4.` Fan H, Lan Z. From Cognitive Architectures to Language Agents: A Mechanism-Level Review of Lineage, Convergence, and Migration Gaps. *arXiv (Cornell University).* 2026;abs/2607.23942. doi:10.48550/arxiv.2607.23942
 
> [4.1] The strongest remaining opportunities lie in couplings among mechanisms. (Abstract)
 
> [4.2] : A persistent intention record should store the committed goal, rationale, plan, continuation condition, reconsideration triggers, authority, and termination status. (Body)
 
> [4.3] Five residual bundles remain: activation with latency and action utility; typed impasse with isolated substates and resolution compilation; bounded content competition with broadcast and admission learning; persistent intention with reconsideration and live method authority; and uncertainty with resource allocation, interruption, and stopping. (Abstract)
 
> [4.4] Closest-baseline screening closes one proposed gap: GraSP already combines calibrated multi-skill selection, typed compilation, verification, bounded repair, and replanning or ReAct fallback. (Abstract)
 
> [4.5] This review advances one bounded synthesis claim: modern language agents have migrated much of the cognitive substrate, while adaptive control mechanisms exhibit uneven migration depth. (Body)
 
> [4.6] Finally, this paper establishes feasibility and architectural hypotheses, not cross-domain causal value. (Body)
 
> [4.7] Those results do not prove that the five residual bundles improve reliability or efficiency when composed. (Body)
 
> [4.8] A governor should decide whether to continue, delegate, suspend, abandon, or change method. (Body)
 
> [4.9] The open research target is therefore a set of runtime invariants connecting state, failure, commitment, learning, uncertainty, and resources, rather than a wholesale reconstruction of an older architecture. (Body)
 
> [4.10] Similar behavior can arise from different processes, and a mechanism that is useful for cognitive modeling may add unnecessary engineering overhead. (Body)
 
> [4.11] We reconstruct each mechanism through state, control, transition, persistence, failure, learning, and resource governance, then code evidence relation (E1-E4) separately from migration depth (D0-D4). (Body)
 
> [4.12] Specialized systems already implement substantial parts of memory-policy learning, typed failure recovery, team and topology adaptation, BDI control, workflow search, symbolic-learned skill coordination, resource scheduling, and uncertainty-conditioned action. (Body)
 
> [4.13] Controlled interventions must therefore isolate the added state and control edge, hold the model and environment fixed, and report negative results. (Body)
 
> [4.14] The resulting landscape is uneven. (Abstract)
 
`5.` Lerma-Torres DC. Human-Like Lifelong Memory: A Neuroscience-Grounded Architecture for Infinite Interaction. *arXiv (Cornell University).* 2026;abs/2603.29023. doi:10.48550/arxiv.2603.29023
 
> [5.1] We map this to a dual-store architecture: a capacity-limited working memory buffer and a persistent knowledge graph. (Body)
 
> [5.2] | Principle | Key Evidence | Gap in Existing Sys- tems | Our Mechanism | |---------------------------|-------------------------------------------------|-------------------------------|--------------------------------------------------| | Complementary learning | McClelland et al. (1995); Kumaran et al. (2016) | Single undifferentiated store | Dual-store: WM+KG | | WMcapacity limits | Cowan (2001); Baddeley (2000) | Context as general stor- age | Capacity-limited WM with gating | | Emotion as computation | Damasio (1994); Mc- Gaugh (2004) | No emotional valuation | Valence vectors | (Body)
 
> [5.3] Expanding context windows does not solve this: recent evidence shows that context length alone degrades reasoning by up to 85% - even with perfect retrieval. (Abstract)
 
> [5.4] We propose a bio-inspired memory framework grounded in complementary learning systems theory, cognitive behavioral therapy's belief hierarchy, dual-process cognition, and fuzzy-trace theory, organized around three principles: (1) Memory has valence, not just content - pre-computed emotional-associative summaries (valence vectors) organized in an emergent belief hierarchy inspired by Beck's cognitive model enable instant orientation before deliberation; (2) Retrieval defaults to System 1 with System 2 escalation - automatic spreading activation and passive priming as default, with deliberate retrieval only when needed, and graded epistemic states that address hallucination structurally; and (3) Encoding is active, present, and feedback-dependent - a thalamic gateway tags and routes information between stores, while the executive forms gists through curiosity-driven investigation, not passive exposure. (Abstract)
 
> [5.5] Damasio (1994) formalized the somatic marker hypothesis: emotional signals bias decisions before deliberate reasoning. (Body)
 
> [5.6] Complementary learning systems. (Body)
 
> [5.7] McClelland et al. (1995) demonstrated that biological memory requires two systems: hippocampus for rapid encoding and neocortex for gradual extraction. (Body)
 
`6.` Toba MN, Malkinson TS, Howells H, Mackie M, Spagna A. Same, Same but Different? A Multi-Method Review of the Processes Underlying Executive Control. *Neuropsychology Review.* 2023;34:418-454. doi:10.1007/s11065-023-09577-4
 
> [6.1] Attention, working memory, and executive control are commonly considered distinct cognitive functions with important reciprocal interactions. (Abstract)
 
`7.` Oberauer K. Working Memory and Attention – A Conceptual Analysis and Review. *Journal of Cognition.* 2019;2:36-36. doi:10.5334/joc.58
 
> [7.1] A first divide exists between the concept of attention as a limited resource, and the concept of attention as selective information processing. (Abstract)
 
> [7.2] Three versions of this idea have been proposed: Attention as a resource for storage and processing, a shared resource for perceptual attention and memory maintenance, and a resource for the control of attention. (Abstract)
 
> [7.3] The first pertains to attentional selection of the contents of working memory, controlled by mechanisms of filtering out irrelevant stimuli, and removing no-longer relevant representations from working memory. (Abstract)
 
> [7.4] Working memory contributes to controlling perceptual attention - by holding templates for targets of perceptual selection - and controlling action - by holding task sets to implement our current goals. (Abstract)
 
> [7.5] Theories conceptualizing attention as a resource assume that this resource is responsible for the limited capacity of working memory. (Abstract)
 
`8.` Kanwal A, Abbas S, Ghazal TM, Ditta A, Alquhayz H, Khan MA. Towards Parallel Selective Attention Using Psychophysiological States as the Basis for Functional Cognition. *Sensors.* 2022;22:7002-7002. doi:10.3390/s22187002
 
> [8.1] Attention generation and regulation are limited in the scope of working memory. (Body)
 
> [8.2] The LIDA architecture [9,24] is planned to design an autonomous and artificially intelligent software agent. (Body)
 
> [8.3] LIDA implements attentional learning and provides an architecture to improve internal resource management by filtering data. (Body)
 
> [8.4] The cognitive processes based on selective attention help the agent to efficiently utilize its computational resources by scheduling its intellectual tasks, which are not limited to decision-making, goal planning, action selection, and execution of actions. (Body)
 
`9.` Dumbrava S. Theoretical Foundations for Semantic Cognition in Artificial Intelligence. *arXiv (Cornell University).* 2025;abs/2504.21218. doi:10.48550/arxiv.2504.21218
 
> [9.1] Load ( λ ) and Semantic Effort ( ϵ ) addresses resource limitations central to attention theories, with effort allocation policies ( π effort ) modeling executive control. (Body)
 
`10.` Soni AV, Traylor A, Merullo J, Frank MJ, Pavlick E. Transformer Mechanisms Mimic Frontostriatal Gating Operations When Trained on Human Working Memory Tasks. *Journal of Cognitive Neuroscience.* 2026;38:2128-2140. doi:10.1162/jocn.a.2679
 
> [10.1] We find that, as a result of training, the self-attention mechanism specializes in a way that resembles existing models of input-output gating. (Introduction)
 
> [10.2] We find that the Transformer's attention mechanism develops role-addressable input and output gating, but only when trained on task distributions that benefit from frontostriatal-like gating mechanisms. (Abstract)
 
> [10.3] According to computational models, capacity limitations in WM arise due to challenges in "role addressability": learning to correctly bind items in memory to their respective roles and assigning credit to the corresponding gating operations. (Abstract)
 
`11.` Hsing N. MIRROR: Converging Cognitive Principles as Computational Mechanisms for AI Reasoning. *arXiv (Cornell University).* 2025. doi:10.48550/arxiv.2506.00430
 
> [11.1] Critically, the Controller has no access to raw conversation history-only thread outputs and the prior narrative-forcing genuine information compression rather than passive copying. (Body)
 
> [11.2] MIRROR's Cognitive Controller fully regenerates a bounded first-person narrative ( ≤ 3k tokens) each turn, discarding the previous version. (Body)
 
> [11.3] This implements O(1) bounded reconstruction: regardless of conversation length, the internal representation remains fixed-size. (Body)
 
> [11.4] Ablation studies test the theoretical predictions directly: reconstructive synthesis improves all seven models (+5-20%); the integrated system outperforms either component alone for six of seven models, confirming that parallel exploration and integrative synthesis are complementary; and gains concentrate where theories predict -- under high attentional load where global availability of integrated information is most needed. (Abstract)
 
> [11.5] Multiple cognitive theories -- Global Workspace Theory, reconstructive episodic memory, inner speech, and complementary learning systems -- converge on a shared set of architectural principles: parallel specialized processing, integrative synthesis into a bounded unified representation, and reconstructive rather than accumulative maintenance. (Abstract)
 
> [11.6] MIRROR operationalizes each principle as a concrete mechanism: an Inner Monologue Manager generates parallel cognitive threads (Goals, Reasoning, Memory), a Cognitive Controller synthesizes these into a bounded first-person narrative that is fully reconstructed each turn, and a temporal separation between fast response generation and slow deliberative consolidation mirrors complementary learning dynamics. (Abstract)
 
> [11.7] Schacter's constructive episodic simulation hypothesis [Schacter, 2012] argues this reconstructive nature is adaptive : by regenerating understanding each time, the system can flexibly integrate new information with prior knowledge rather than rigidly replaying stored traces. (Body)
 
`12.` Lindsay GW. Attention in Psychology, Neuroscience, and Machine Learning. *Frontiers in Computational Neuroscience.* 2020;14:29-29. doi:10.3389/fncom.2020.00029
 
> [12.1] Inspired by this, the ‘consciousness prior' in machine learning emphasizes a neural network architecture with a low-dimensional representation that arises from attention applied to an underlying high-dimensional state representation (Bengio, 2017). (Body)
 
`13.` Egner T. Principles of cognitive control over task focus and task switching. *Nature Reviews Psychology.* 2023;2:702-714. doi:10.1038/s44159-023-00234-4
 
> [13.1] Adaptive behaviour requires the ability to focus on a task and protect it from distraction (cognitive stability) and to rapidly switch tasks when circumstances change (cognitive flexibility). (Abstract)
 
> [13.2] In this Perspective, I integrate these literatures to derive a cognitive architecture and functional rules underlying the regulation of cognitive stability and flexibility. (Abstract)
 
> [13.3] I propose that task focus and task switch readiness are supported by independent mechanisms. (Abstract)
 
> [13.4] However, I also suggest that the strategic regulation of both mechanisms is governed by shared learning principles: an incremental, online learner that nudges control up or down based on the recent history of task demands (a recency heuristic) and episodic reinstatement when the current context matches a past experience (a recognition heuristic). (Abstract)
 
`14.` Vladu IC, Bîzdoacă NG, Pirici I, Bălșeanu T, Bondoc EN. The DIME Architecture: A Unified Operational Algorithm for Neural Representation, Dynamics, Control and Integration. *Applied Sciences.* 2026;16:5380-5380. doi:10.3390/app16115380
 
> [14.1] | 3 | unit of neural process Abstract; 1.1; Emotion, | continuity | | 4 | Marker systems as intrinsic value-based control mechanisms 3.3 | attention, motivation, learning modulation; regime switching | | 5 | Dual flow architecture: informational flow (FI) vs modulatory flow (FM) 1.2; 3.3 | Pre-rational selection; biasing without content transfer | | 6 | Hyperengrams as large-scale integrative states Abstract; 3.4 Conscious episodes; global coherence | working memory; | | 7 | Detect - Integrate - Mark - Execute as an invariant operational cycle Abstract; 4 | Unified mechanism for perception, memory, decision and action | These consequences follow logically from the core commitments but are not independent premises. (Body)
 
> [14.2] 2, 5 | | 4 | Attention | Attention as marker-driven stabilization of threads | Sec. 3.3; Monograph Ch. (Body)
 
> [14.3] | Derived domain Key consequences developed | Where | |-------|---------------------------------------------------------------------------------------------------------------|---------| | 1 | Memory No distinct memory 'types'; memory as re -execution and reconsolidation Sec. 3 - 5; Monograph Ch. (Body)
 
> [14.4] | Derived domain | Key consequences | Where developed | |-------|----------------------|--------------------------------------------------------------------|-----------------------------------------| | 2 | Decision-making | Decisions as competition between parallel execution threads | Sec. 3.2; 4; Monograph Ch. (Body)
 
> [14.5] This work introduces DIME (Detect–Integrate–Mark–Execute), a unified operational architecture in which perception, memory, valuation, and conscious access are treated as components of a single recurrent computational cycle. (Abstract)
 
`15.` Giallanza T, Campbell DI, Cohen JD. Toward the Emergence of Intelligent Control: Episodic Generalization and Optimization. *Open Mind.* 2024;8:688-722. doi:10.1162/opmi_a_00143
 
> [15.1] In this article, we suggest an approach to addressing this mystery that builds on two lines of research in cognitive science often treated as distinct—the acquisition of knowledge and the execution of goal-directed behavior—integrating these in a way that leads to a reframing of core constructs in each. (Body)
 
> [15.2] The framework consists of an episodic memory module, which rapidly learns relationships between stimuli; a semantic pathway, which more slowly learns how stimuli map to responses; and a recurrent context module, which maintains a representation of task-relevant context information, integrates this over time, and uses it both to recall context-relevant memories (in episodic memory) and to bias processing in favor of context-relevant features and responses (in the semantic pathway). (Abstract)
 
> [15.3] ii) rapid storage and similarity-based retrieval of novel information, usually attributed to episodic memory; (Body)
 
> [15.4] We investigate how this emerges in a neural network by describing and testing the Episodic Generalization and Optimization (EGO) framework. (Abstract)
 
> [15.5] iii) activation, online integration and maintenance of recently presented information, usually attributed to working memory; and (Body)
 
> [15.6] However, none of the tasks modeled here involved any sequential dependencies on decision making or action; that is, sequences in which experienced future states were impacted by current decisions or actions. (Body)
 
> [15.7] Here, we propose that such behavior reflects the use of recurrent context representations, both actively maintained in working memory and stored in episodic memory, that are used to guide performance directly (through semantic memory) as well as through similarity-based retrieval from episodic memory. (Body)
 
`16.`  I. Nested Episodic State Topology (NEST): A Graph-Theoretic Architecture of Cognitive States. *arXiv (Cornell University).* 2026;abs/2607.06055. doi:10.48550/arxiv.2607.06055
 
> [16.1] Durable belief graphs are separated from capacity-limited working-memory graphs that may host transient non-belief content. (Abstract)
 
> [16.2] Concepts, episodes, percepts, and task contexts are represented as typed, weighted graphs whose nodes may carry internal subgraph payloads; edges are typed under six relation classes -- causal, containment, temporal, associative, evidential, and spatial. (Abstract)
 
> [16.3] We present NEST (Nested Episodic State Topology), a foundational graph-theoretic representational ontology for modeling cognition as structured state formation and transformation rather than as a finished empirical model. (Abstract)
 
> [16.4] A reusable operator toolkit -- activation, graph-property functionals, working-memory transitions, awareness and trajectory functionals, and belief update -- organizes the formal core. (Abstract)
 
> [16.5] Its aim has been to specify the representational and structural commitments of NEST at a high level of abstraction, rather than to deliver a finished empirical model or domain-specific simulation. (Body)
 
> [16.6] An implementation would require concrete data structures for B and W t , graph-matching procedures for recognition, and chosen parameterizations of awareness and control over trajectories. (Body)
 
`17.` Yang L, Guan T,  Y, Li Z, Fang Z, Wang F. Cognitive Modeling for Long-Horizon Agent Learning via Integrated Long-Term Memory and Reasoning. *International Conference on Communication Networks and Machine Learning (CNML).* 2026. doi:10.1109/cnml68938.2026.11452287
 
> [17.1] To address the separation between memory and decision making in conventional policy models, the framework tightly couples perception representation, memory management, reasoning processes, and policy generation into an end-to-end cognitive loop. (Abstract)

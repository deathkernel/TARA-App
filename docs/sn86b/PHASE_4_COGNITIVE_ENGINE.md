# SN-86B Phase 4 — Cognitive Engine

**Status:** Initial implementation committed; empirical validation pending.

## Scope
Phase 4 adds deterministic cognitive control primitives: attention allocation,
context assembly, goal prioritization, evidence-adjusted decision scoring with
abstention, and a staged coordinator. It does not reproduce human cognition.

## Attention
For item i, attention is a transparent weighted sum:
A(i) = 0.35R + 0.20I + 0.15T + 0.15S + 0.15C
where relevance, importance, recency, salience and confidence are normalized
to [0,1]. These are engineering defaults, not neuroscientific constants.
Stable item IDs break ties.

## Recency
For age delta-t and configured half-life h:
T = exp(-ln(2) * delta-t / h)
This makes decay interpretable. Future timestamps are clamped to zero age.
Default half-life is one day.

## Context
The context builder reads the existing MemoryEngine recall interface,
converts working/episodic/semantic results into typed candidates, adds
transient observations supplied by a caller, then applies bounded attention.
It never consolidates, persists or forgets memories.

## Goal scheduling
Pending goals receive:
P = 0.35I + 0.30U + 0.20R + 0.15D
where importance, urgency and relevance are normalized and deadline pressure
D approaches one as the deadline approaches. Goals with incomplete
dependencies are withheld. This is a lightweight deterministic scheduler.

## Decision and abstention
Each candidate action receives:
Q = clip[0,1](utility * confidence * evidence_strength - risk_penalty * risk)
The engine selects only when the best score clears a configured threshold and,
when competing options exist, clears a minimum margin over the runner-up.
Otherwise it abstains. Scores are policy values, not calibrated probabilities.

## Reasoning coordination
The coordinator performs request validation, context retrieval, attention
allocation, candidate proposal (only with an injected provider), and decision
scoring. A provider adapter may delegate to SITA's existing OmniRoute gateway.
The coordinator does not replace OmniRoute, fabricate reasoning, invoke tools,
execute actions, or bypass approval controls.

## Integration boundaries
- Memory reads use the existing SN-86B MemoryEngine recall interface.
- Neural and learning primitives remain lower-level capabilities. No
  unvalidated neural-to-symbolic mapping or automatic conversation training
  is introduced.
- Tool execution, persistent writes and sensitive actions remain controlled
  by SITA's existing authorization and approval system.
- No mandatory runtime dependency is introduced.

## Tests
tests/test_sn86b_cognition.py covers attention ranking, memory/context
composition, recency half-life, decision selection and abstention, goal
dependencies/deadlines/capacity, and coordinator behavior with/without an
injected proposal provider. Tests are authored but have not yet been executed.
No performance or cognitive-capability claim is made.

# TARA Token-Efficient Intelligence Architecture

**Status:** Proposed target architecture for staged implementation; not a claim that these optimizations already exist.

## 1. Objective

Maximize useful work and answer quality per unit of paid inference usage. Minimize unnecessary input/output tokens, not necessary detail. TARA remains local-first and uses OmniRoute as its only language-model gateway. TARA owns intent routing, context assembly, memory, caching policy, local usage accounting, and permissions. OmniRoute owns provider/model lifecycle and provider-side routing.

Success means fewer repeated prompt/history tokens, fewer avoidable model calls, less irrelevant context, safe reuse, and measured savings without quality regression.

## 2. Target request path

```text
User request
  -> deterministic local intent/capability router
  -> policy and privacy checks
  -> context planner (recent turns + compact summary + relevant memory + needed excerpts)
  -> token budget planner (estimate input, reserve output, enforce context limits)
  -> inference route policy (economical / standard / complex)
  -> OmniRoute (single inference boundary)
  -> response validation and optional bounded completion
  -> local usage ledger, session update, audit
```

A cache lookup may happen after context normalization and policy checks, but can never bypass authorization, privacy, approvals, or audit.

## 3. Core components

### 3.1 Local intent and complexity router

Use deterministic rules and existing specialist routing before asking a model to classify a request. Exact commands, simple calculations, status lookups, and deterministic formatting should use local code when reliable. For model-required tasks, assign explainable classes: routine, standard, complex, high-risk. Complexity is a routing hint, never an authorization decision. High-risk work always uses the existing permission/approval boundary.

Do not add a second LLM call solely to choose a model. A model-based classifier is an experiment only if measured savings exceed its extra cost.

### 3.2 Context planner and compactor

Build bounded, explicit context sections: stable system instructions; current request; a few relevant recent turns; compact session summary when older turns matter; relevant saved memories; only necessary file/attachment excerpts; only selected skill/tool instructions.

Do not resend the entire transcript by default. Retrieve memory by relevance and recency, then enforce a token budget instead of unconditionally adding a fixed number of memories. Keep user-provided facts distinct from generated summaries.

When history crosses a configurable threshold, incrementally summarize older turns. Preserve decisions, constraints, unresolved questions, corrections, entities, and references. Keep the original local transcript; summaries are derived indexes, not replacements. If summary creation fails, fall back to a bounded recent window and do not claim perfect recall.

Never summarize away safety constraints, approval state, user corrections, citations, or exact code/error excerpts needed for the active task.

### 3.3 Token budget planner

Create per-request budgets for system instructions, history/summary, memory, files/tools, and completion. Use a compatible tokenizer when available; otherwise use a conservative estimator and label it approximate.

The planner must reserve output capacity first, prioritize the current request and safety instructions, trim low-relevance context before touching the current request, reject/request narrower scope if required context cannot fit, respect route context limits, and record estimated and actual usage separately.

Do not hard-code tiny output limits to make metrics look good. Keep TARA-Chat's existing 1536-token default until task-based measurements justify a change.

### 3.4 Inference and model-tier policy

TARA keeps OmniRoute as its only inference gateway. TARA may select configured route aliases by task class but must not call provider APIs directly or silently fall back to Ollama/Gemini.

- Deterministic/local path for work that does not need inference.
- Economical configured route for routine extraction, summaries, and straightforward questions.
- Standard route for normal conversation and coding explanation.
- Stronger configured route for difficult reasoning, code review, and research synthesis.

Explicit user model selection takes precedence. If unavailable or disallowed, explain the failure rather than silently switching. Tier labels are policy labels, not assumptions about real price/capability; use verified OmniRoute catalogue/configuration data.

### 3.5 Safe caching

Use explicit cache scope, keys, expiry, and invalidation:

- Stable prompt prefixes should remain byte-for-byte stable where possible so compatible providers may reuse prefix caches; provider discounts are not guaranteed.
- Cache pure deterministic local operations by normalized inputs and implementation version.
- Inference response caching is opt-in and only for explicitly reusable task classes. Keys include normalized request, relevant context hash, system prompt version, route/model, output settings, and capability version.
- Cache derived retrieval/embedding data with source version and invalidation metadata.

Never share cached answers across users, sessions, workspaces, authorization scopes, or changing data. Do not cache actions, approvals, secrets, personal/medical/financial content, live facts, or outputs dependent on current state. Similarity cache is disabled by default; allow only for explicitly safe classes with conservative thresholds. Cache hits remain auditable and never grant permissions.

### 3.6 Tool and specialist efficiency

Prefer one specialist over default fan-out. Fetch only schemas needed for the selected task. Bound tool output by relevance and size while retaining exact source references. Deduplicate identical read-only calls within one request. Never automatically retry non-idempotent actions. Reuse validated intermediate results only with provenance and expiry. Existing approval gates remain mandatory.

### 3.7 Answer quality controller

Use task-aware output budgets. Remove repeated preambles, duplicated conclusions, and irrelevant details, but retain all necessary explanation, code, citations, and safety instructions. A second model call to critique/rewrite is disabled by default; consider only when measured quality gain justifies the added cost.

## 4. Initial implementation status

The first implementation slice now exists in the runtime:

- `tara_chat.token_budget` provides deterministic UTF-8 token estimation and priority-based context packing. The estimate is explicitly approximate and is not reported as provider usage.
- `TARABrain` preserves the current user request and system prompt, budgets relevant saved memories, and includes a bounded recent-turn window only when it fits. It reports omitted context and estimated input tokens in `BrainResponse`.
- `OmniRouteProvider` captures provider-reported prompt/completion/total usage when present; missing usage remains unknown.
- `McpToolGateway` caches read-only tool metadata briefly per server configuration, exposes explicit invalidation, and bounds descriptions, schemas, and tool result text. Tool calls and approvals are never cached.

Not yet implemented: model-specific tokenizer integration, persistent incremental conversation summaries, model-tier routing, response caching, and a persistent usage dashboard/ledger. These remain separate phases and must not be described as shipped.

## 5. Local usage ledger

Record request ID, time, capability/task class, route/model when available, estimated input/output tokens, provider-reported usage when available, cache/compaction outcomes, latency, status, and retry count. Calculate cost only from verified configured rates. If the gateway omits usage, actual usage is unknown; never present an estimate as actual.

Do not store raw prompts or secrets in the ledger. Track cost per useful task, median input/output tokens, cache hit rate, context trimming, latency, task success, and quality regressions. Token savings alone are not success.

## 6. Configuration

Introduce typed validated settings such as:

- context.max_input_tokens
- context.recent_turns
- context.summary_trigger_tokens
- context.memory_token_budget
- context.attachment_excerpt_budget
- inference.routine_route
- inference.standard_route
- inference.complex_route
- cache.enabled
- cache.ttl_seconds
- cache.max_entries
- usage_ledger.enabled

Choose defaults from verified route capabilities and tests, not guesses. Invalid configuration must not enable remote transfer or new capabilities.

## 7. Privacy and security

Conversation history, summaries, memory, cache, and usage ledger remain under TARA's local data controls. Send only minimum required context through OmniRoute and preserve existing remote-transfer opt-in. Resolve session/workspace scope before retrieval or cache lookup. Model, cache, memory, file, and tool outputs remain untrusted. Cache never approves or executes actions. Apply redaction before persistence and remote inference where supported. Deletion/retention must include summaries, caches, embeddings, and usage records.

## 8. Implementation phases

1. **Baseline:** measure current payload size, provider usage when available, latency, and answer quality. No behavior changes.
2. **Context foundation:** typed context sections, token estimator interface, budget planner, bounded relevant history, tests.
3. **Memory compaction:** versioned incremental summaries, relevance-ranked memory, invalidation, correction/constraint retention tests.
4. **Routing tiers:** deterministic local routes and configurable OmniRoute aliases; preserve explicit user selection and fail-closed behavior.
5. **Cache and ledger:** deterministic cache first, then narrow allowlisted inference cache; separate estimated and actual usage.
6. **Evaluation/rollout:** offline regression tests and opt-in shadow comparisons; measure quality, factuality, completion, latency, and provider-reported tokens; feature flags and independent kill switches.

## 9. Acceptance criteria

- Deterministic tasks avoid model calls.
- Current request and mandatory policy instructions are never dropped.
- Compaction preserves corrections and active constraints.
- Irrelevant memories/attachments are excluded.
- User-selected routes are never silently overridden.
- All inference still passes through OmniRoute.
- Cache keys isolate sessions, workspaces, routes, and policy versions.
- Sensitive/live-state requests bypass response caching.
- Cache never bypasses authorization, approvals, or audit.
- Estimated usage is never presented as actual provider usage.
- Token reduction is measured against a baseline with an agreed quality tolerance.
- Every optimization can be independently disabled.

## 10. Non-goals

No zero-token AI, free inference guarantee, unlimited context, perfect semantic cache, or guaranteed provider prompt-cache discount. No direct provider integrations, hidden remote transfer, autonomous permissions, or always-on LLM critic.

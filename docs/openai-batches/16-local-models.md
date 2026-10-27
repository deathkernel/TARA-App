# Batch 16 — Local model profiles (gpt-oss)

## Status and intent
This PR defines the safe first step for gpt-oss support. It does not download weights, claim hardware compatibility, or make a model the default.

## Scope
- Add a provider-neutral model profile for optional local gpt-oss runtimes.
- Keep model IDs, runtime availability, download size, hardware requirements, and context limits explicit and separately verifiable.
- Treat Ollama as a possible adapter, not a hard-coded assumption across all environments.
- Ensure no model download or network request happens during import, startup, or profile listing.

## Required implementation files in follow-up code change
- Model catalogue/profile data and schema validation.
- Runtime capability probe with timeout and clear unavailable status.
- Tests for missing runtime, malformed profile, unsupported model, and offline startup.

## Acceptance checks
- Core app starts without gpt-oss installed or configured.
- Profile listing never downloads weights.
- UI/CLI does not label weights as free-to-run: hardware, power, storage, and hosting costs are disclosed.
- Model selection is explicit and local-first; no API key is required for local inference.
- Tests use mocked runtime responses and never pull large weights in CI.

## Safety / non-goals
No automatic downloads, no hardware claims without probing, no hosted API fallback without explicit user selection, and no new mandatory dependency.
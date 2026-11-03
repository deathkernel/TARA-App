# Batch 17 — Agent orchestration adapters

## Scope
Evaluate `openai/openai-agents-python` first. Treat `openai/openai-agents-js` as a separate optional boundary and `openai/swarm` as educational/reference material, not a production dependency by default.

## Architecture
- Adapt agent tool requests to TARA's versioned capability contracts.
- Use the existing capability registry and Security approval flow; SDK tools must not bypass policy.
- Keep Python orchestration as the first implementation to avoid duplicate agent runtimes.
- Add JS orchestration only when an actual Node service and ownership boundary are demonstrated.

## Implementation files expected
- Optional adapter module and dependency extra.
- Contract mapping and typed request/result objects.
- Mocked unit tests for tool allowlist, denied approval, timeout, cancellation, malformed output, and unavailable provider.

## Acceptance checks
- Importing TARA without the extra succeeds.
- No tools are exposed unless explicitly registered and allowlisted.
- No direct shell, filesystem mutation, or network tool is granted by default.
- Local/custom provider use is supported only where the SDK's actual transport permits it; otherwise clearly report the limitation.
- Provider calls are opt-in and can incur costs; no silent hosted fallback.

## Non-goals
Do not copy an upstream repository into the app, make Swarm a runtime dependency, or create two competing orchestration paths without evidence.
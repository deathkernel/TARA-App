# Batch 21 — Guardrails and MCP integrations

## Scope
Evaluate `openai/openai-guardrails-python`, `openai/openai-guardrails-js`, and `openai/mcp-extensions` as optional integrations. Existing TARA Security remains authoritative; external guardrails provide signals, not an automatic policy override.

## Security model
- MCP tools are disabled until individually reviewed and allowlisted.
- Apply least privilege, bounded input/output, timeouts, cancellation, and per-tool audit records.
- External tools cannot silently gain filesystem, shell, account, or network permissions.
- Deny on policy uncertainty for privileged actions; surface a clear reason to the user.
- Keep Python and JS integrations separate; add JS only when a real JS execution boundary exists.

## Implementation files expected
- Guardrail result normalizer and optional adapter.
- MCP extension inventory with per-extension permission manifest.
- Tests for policy conflicts, unavailable guardrail, denied capability, malformed response, and timeout.

## Acceptance checks
- App runs with no optional safety/MCP packages installed.
- No tool becomes enabled just because an extension is installed.
- Secrets and sensitive prompt content are redacted from audit logs.
- Security decisions are deterministic where possible and independently tested.
- Docs identify network/data-flow implications for each integration.

## Non-goals
Do not treat a model judgement as a substitute for deterministic permission enforcement.
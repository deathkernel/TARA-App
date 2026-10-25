# TARA-App Architecture

## Purpose

TARA-App is the composition layer. It must not absorb the internal implementation of the three engines or assume that cross-repository private implementation details are stable APIs.

## Runtime flow

1. UI/CLI creates a request with request and session IDs.
2. The orchestrator validates the schema and requested capability.
3. Policy checks module availability, permissions, workspace scope, timeout, and approval requirements.
4. A versioned adapter invokes the selected engine.
5. Adapter normalizes the response into the shared result contract.
6. Audit records the request, decision, outcome, and redacted error.
7. UI presents results and any proposed change for human review.

## Component ownership

| Component | Owns | Does not own |
|---|---|---|
| TARA-App | UX, sessions, orchestration, config, permission prompts, adapter registry, audit correlation | LLM inference internals, native Handler repair logic, arbitrary host shell |
| TARA-CHAT | Conversation, Ollama/provider access, bounded context, explicit saved memory | Coding execution, autonomous actions |
| TARA-Code | Coding task model, plan, workspace boundary, review/test reports, sandbox runner contract | Chat UI, global OS repair, automatic Git merge |
| TARA-Handler | Deterministic environment inspection and guarded maintenance/repair through native CLI | Natural-language intent understanding or LLM reasoning |

## Failure strategy

- Missing module or executable: report unavailable and do not silently install it.
- Timeout: cancel/wait for process termination where supported, record timeout, and do not automatically retry mutations.
- Invalid response: reject it, record a schema error, and avoid passing it to another module as trusted instructions.
- Denied permission: return `permission_denied` without invoking the adapter.
- Adapter version mismatch: stop dispatch unless an explicit compatibility mapping exists.
- Test failure: present report; never auto-promote or merge changes.

## Data boundaries

Only pass the minimum context necessary to each module. Do not forward persistent chat memory, secrets, full environment dumps, or unrelated repository files automatically. Tool output and project content are untrusted. A model-generated plan can request a capability but cannot grant itself permission.

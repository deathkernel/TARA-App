# TARA-App Architecture

## Purpose

TARA-App is the central application and runtime manager for TARA's AI models and specialist systems. It is not itself an AI model. It provides one UI, model catalogue, configuration surface, lifecycle/resource management, and orchestrator.

Keep these concepts distinct:
- **Model:** learned weights/artifact that performs inference.
- **Runtime/provider:** software that loads and serves a model (for example, a configured local inference server).
- **Specialist engine/tool:** a system that provides a capability, such as conversation management, code-task workflows, or deterministic environment maintenance.
- **TARA-App:** the application that brings them together.

## Target runtime layout

```text
TARA-App
  +-- UI, sessions, settings, model catalogue
  +-- Model Runtime Manager
  |     +-- configured TARA models
  |     +-- configured local/remote providers
  |     +-- load/unload, health, cancellation, resource limits
  +-- Orchestrator / Capability Registry
        +-- TARA-Chat adapter
        +-- TARA-Code adapter
        +-- TARA-Handler adapter
        +-- future TARA models and tools
```

The exact TARA model inventory and artifact formats are not established by the current repositories. They must be specified before implementing download/loading behavior.

## Runtime flow

1. UI creates a request with request/session IDs and selects or requests a capability.
2. The orchestrator validates the request and resolves the needed model/provider or specialist engine.
3. Policy checks availability, permissions, resource limits, workspace scope, timeout, and approval requirements.
4. The runtime manager ensures the requested model is loaded and healthy, or returns an actionable unavailable/resource-limit status.
5. A versioned adapter invokes the selected engine or model runtime.
6. The adapter normalizes output and records model/provider/version when inference was used.
7. Audit records the request, policy decision, outcome, resource use, and redacted error.
8. UI presents the response or proposed change for human review.

## Component ownership

| Component | Owns | Does not own |
|---|---|---|
| TARA-App | UX, model catalogue, runtime lifecycle, resource management, sessions, orchestration, config, permissions, audit | Model weights or the internal implementation of every engine |
| TARA-CHAT | Conversation, provider access, bounded context, explicit saved memory | Coding execution or global OS repair |
| TARA-Code | Coding task model, plan, workspace boundary, review/test reports, sandbox runner contract | Chat UI, global OS repair, automatic Git merge |
| TARA-Handler | Deterministic environment inspection and guarded maintenance/repair through native CLI | LLM inference or natural-language intent understanding |
| Model runtime/provider | Load/inference lifecycle for supported model artifacts | Application UI and cross-engine policy |

## Failure strategy

- Missing model/runtime/executable: report unavailable; do not silently download or install.
- Insufficient resources: refuse or queue according to explicit policy; never silently kill unrelated processes.
- Timeout/cancellation: stop the supported request and record its status; do not automatically retry mutations.
- Invalid response: reject it and do not pass it to another module as trusted instructions.
- Denied permission: return `permission_denied` without invoking the adapter.
- Adapter/runtime version mismatch: stop dispatch unless an explicit compatibility mapping exists.
- Test failure: present report; never auto-promote or merge changes.

## Data boundaries

Only pass the minimum context necessary to each module/model. Do not forward persistent chat memory, secrets, full environment dumps, or unrelated repository files automatically. Model output, tool output, and project content are untrusted. A model-generated plan can request a capability but cannot grant itself permission.

## Implemented foundation: policy-gated dispatch

The current head now includes `PermissionPolicy`, versioned `CapabilityRequest`/`CapabilityResponse` contracts, `CapabilityOrchestrator`, and a redacting JSONL audit sink. Dispatch requires both an explicitly allowlisted capability and a registered handler. Approval-gated capabilities return `approval_required` until the request carries explicit approval. Unknown capabilities and dangerous default-deny capabilities do not invoke handlers. The policy decision must be persisted before dispatch; if that audit write fails, dispatch stops.

This does not yet implement sandboxed execution, persistent permission UI, real TARA-Chat/TARA-Code/TARA-Handler adapters, or a full application UI. Those remain separate follow-up work.

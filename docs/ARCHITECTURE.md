# SITA Architecture

## Purpose

SITA is the user-facing AI assistant and specialist orchestrator. It is not itself an AI model. OmniRoute is its only language-model gateway; it owns underlying provider/model selection and lifecycle. SITA owns the UI, sessions, local memory, permissions, specialist routing, and desktop tools.

Keep these concepts distinct:
- **Model:** learned weights/artifact that performs inference.
- **Gateway/provider:** OmniRoute exposes an OpenAI-compatible API and routes requests to configured model providers. SITA does not directly invoke model runtimes.
- **Specialist engine/tool:** a system that provides a capability, such as conversation management, code-task workflows, or deterministic environment maintenance.
- **SITA:** the application that brings them together.

## Target runtime layout

```text
SITA
  +-- UI, sessions, settings, model catalogue
  +-- OmniRoute Gateway / Model Router
  |     +-- only language-model inference path
  |     +-- model/route catalogue via GET /v1/models
  |     +-- provider selection, fallback, quotas and lifecycle managed by OmniRoute
  +-- Orchestrator / Capability Registry
        +-- SITA Chat adapter
        +-- SITA Code adapter
        +-- SITA Handler adapter
        +-- future SITA models and tools
```

OmniRoute exposes the available model IDs and route aliases. Underlying model weights and provider lifecycle remain outside SITA; the current SITA launcher does not download or load LLM weights.

## Runtime flow

1. UI creates a request with request/session IDs and selects or requests a capability.
2. The orchestrator validates the request and selects the needed SITA specialist; OmniRoute later selects the underlying model/provider.
3. Policy checks availability, permissions, resource limits, workspace scope, timeout, and approval requirements.
4. For language-model inference, the specialist sends a bounded OpenAI-compatible request to the loopback OmniRoute gateway; if the gateway is unavailable, the request fails closed.
5. A versioned adapter invokes the selected specialist or local tool; model inference is delegated to OmniRoute.
6. The adapter normalizes output and records model/provider/version when inference was used.
7. Audit records the request, policy decision, outcome, resource use, and redacted error.
8. UI presents the response or proposed change for human review.

## Component ownership

| Component | Owns | Does not own |
|---|---|---|
| SITA | UX, OmniRoute model catalogue, sessions, orchestration, config, permissions, local tools and audit | Underlying model weights/provider lifecycle |
| SITA Chat | Conversation, OmniRoute access, bounded context, explicit saved memory | Coding execution or global OS repair |
| SITA Code | Coding task model, plan, workspace boundary, review/test reports, sandbox runner contract | Chat UI, global OS repair, automatic Git merge |
| SITA Handler | Deterministic environment inspection and guarded maintenance/repair through native CLI | LLM inference or natural-language intent understanding |
| OmniRoute | Provider/model routing, fallback, quotas and model catalogue | SITA's local permissions, memory and desktop actions |

## Failure strategy

- Missing model/runtime/executable: report unavailable; do not silently download or install.
- Insufficient resources: refuse or queue according to explicit policy; never silently kill unrelated processes.
- Timeout/cancellation: stop the supported request and record its status; do not automatically retry mutations.
- Invalid response: reject it and do not pass it to another module as trusted instructions.
- Denied permission: return `permission_denied` without invoking the adapter.
- Adapter/runtime version mismatch: stop dispatch unless an explicit compatibility mapping exists.
- Test failure: present report; never auto-promote or merge changes.

## Data boundaries

Only pass the minimum context necessary to each module. Chat history and relevant memory context, prompts, supplied Code attachments, Creative briefs, and Vision images may be sent through OmniRoute to its configured provider. Do not send secrets or confidential workspace contents unless the user accepts that transfer. Model output, tool output, and project content are untrusted. A model-generated plan can request a capability but cannot grant itself permission.

## Implemented foundation: policy-gated dispatch

The current head now includes `PermissionPolicy`, versioned `CapabilityRequest`/`CapabilityResponse` contracts, `CapabilityOrchestrator`, and a redacting JSONL audit sink. Dispatch requires both an explicitly allowlisted capability and a registered handler. Approval-gated capabilities return `approval_required` until the request carries explicit approval. Unknown capabilities and dangerous default-deny capabilities do not invoke handlers. The policy decision must be persisted before dispatch; if that audit write fails, dispatch stops.

This does not yet implement sandboxed execution, persistent permission UI, real SITA Chat/SITA Code/SITA Handler adapters, or a full application UI. Those remain separate follow-up work.

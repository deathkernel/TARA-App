# Application service and specialist adapter slice

This batch adds a headless facade and narrow adapter boundaries. It is not a GUI and does not claim the sibling repositories are already wired into a runnable app.

## Application service

`src/tara_app/application_service.py` coordinates the existing runtime manager, in-memory session store, model catalogue, JSONL audit log, and optional capability orchestrator. It provides session creation/closure, catalogue refresh, model listing, local chat turns, and capability dispatch for a future UI/API layer.

Session content remains in process memory only. Audit events intentionally record identifiers and model/provider metadata rather than chat message text. A failed audit while creating a session closes the newly created session.

## Specialist adapters

- `TaraChatAdapter` accepts an injected callable and validates a small `chat.reply` payload. It does not import TARA-CHAT internals, launch subprocesses, or install dependencies.
- `TaraCodeAdapter` accepts an injected planning/review callable. It returns proposed changes as data only and has no filesystem write or subprocess capability.
- Both implement the versioned `SpecialistAdapter` contract. The host must register and explicitly enable them before dispatch.

## Remaining integration work

1. Bind the actual TARA-CHAT engine behind the injected chat callable.
2. Bind TARA-Code planning/review behind the injected code callable, preserving workspace constraints and diff review.
3. Implement a separate, constrained TARA-Handler subprocess adapter after documenting its CLI protocol.
4. Add cancellation, request timeouts, and bounded execution for injected callables before running untrusted/long-running engines.
5. Connect these services to a UI/API entry point and then run the expanded test suite.

No shell execution, patch application, model download, provider launch, auto-merge, or third-party installation is added by these adapters.


## Local health endpoint

The loopback web server exposes `GET /api/health` for local liveness checks. It reports the app name and API version, registered capability IDs, and whether a model catalogue is configured. It does not contact model providers or claim that a configured runtime is currently healthy. The endpoint uses the same local-origin validation as the model endpoint and rejects untrusted origins.

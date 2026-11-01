# Application service and specialist adapter slice

This batch adds a headless facade and narrow adapter boundaries. It is not a GUI and does not claim the sibling repositories are already wired into a runnable app.

## Application service

`src/tara_app/application_service.py` coordinates the existing runtime manager, in-memory session store, model catalogue, JSONL audit log, and optional capability orchestrator. It provides session creation/closure, catalogue refresh, model listing, local chat turns, and capability dispatch for a future UI/API layer.

Chat turns are stored as complete user/assistant pairs. The session store checks that two message slots are available before inference and rechecks capacity while committing the pair under its lock. With SQLite persistence enabled, both rows and the session timestamp are written in one database transaction; failures do not leave a partial turn. Existing history is never silently truncated.

Session content remains in process memory by default. `SessionStore(database_path=...)` opts into SQLite persistence for session metadata and bounded message history; it restores sessions after restart and removes persisted rows when a session is closed. Choose the database path explicitly and protect the file with OS permissions because it contains conversation content. An optional `retention_seconds` policy expires sessions by inactivity (`updated_at`), deletes associated messages through the SQLite foreign-key cascade, and runs during persistent-store startup; `None` remains the default and never expires stored conversations. `prune_expired_sessions()` also supports explicit maintenance, and reports how many sessions were removed. The SQLite database uses `PRAGMA user_version = 1`; unknown newer schema versions fail closed rather than being rewritten. The headless application service exposes this as `session_retention_seconds` when it creates its own store. Audit events intentionally record identifiers and model/provider metadata rather than chat message text. A failed audit while creating a session closes the newly created session.

## Specialist adapters

- `TaraChatAdapter` accepts an injected callable and validates a small `chat.reply` payload. It does not import TARA-CHAT internals, launch subprocesses, or install dependencies.
- `TaraCodeAdapter` accepts an injected planning/review callable. It returns proposed changes as data only and has no filesystem write or subprocess capability.
- Both implement the versioned `SpecialistAdapter` contract. The host must register and explicitly enable them before dispatch.

## Remaining integration work

1. Bind the actual TARA-CHAT engine behind the injected chat callable.
2. Bind TARA-Code planning/review behind the injected code callable, preserving workspace constraints and diff review.
3. Implement a separate, constrained TARA-Handler subprocess adapter after documenting its CLI protocol.
4. Provider calls now have a bounded concurrency gate, wall-clock HTTP deadline, response-size cap, and cooperative cancellation for the Ollama adapter. Injected specialist callables still need a separately enforced process boundary; do not treat a Python thread timeout as cancellation.
5. Connect these services to a UI/API entry point and then run the expanded test suite.

No shell execution, patch application, model download, provider launch, auto-merge, or third-party installation is added by these adapters.

## Provider request lifecycle

The runtime manager limits simultaneous provider operations and rejects excess work rather than accumulating an unbounded queue. The Ollama HTTP adapter enforces a wall-clock request deadline, keeps the existing 2 MiB response bound, and supports cooperative cancellation by closing the in-flight loopback connection. Cancellation is exposed through the application chat service; providers that do not implement the cancellation contract fail closed when cancellation is requested.

This does not forcibly terminate arbitrary injected Python callables. Such engines require a separately supervised subprocess boundary with fixed protocol, bounded input/output, timeout, cancellation/termination, and cleanup before they are eligible for untrusted or long-running execution.


## Local health endpoint

The loopback web server exposes `GET /api/health` for local liveness checks. It reports the app name and API version, registered capability IDs, and whether a model catalogue is configured. It does not contact model providers or claim that a configured runtime is currently healthy. The endpoint uses the same local-origin validation as the model endpoint and rejects untrusted origins.

# Architecture Migration Progress

**Branch:** `architecture/workflow-engine-state`  
**Base:** `main` @ `43010144784e6dc2dcd69209fdcec6bed696db60` (includes PR #69 facade + workflow contracts)  
**Status:** In progress — workflow **execution** engine added (not live-wired).

## Completed

### Slice A (PR #69, on main)
- `tara_app.application` package with `ApplicationFacade` and bootstrap.
- CLI / public entry use facade.
- HTTP server no longer reads registry/catalogue directly from coordinator.
- Versioned workflow request/step/plan/result contracts + DAG validation tests.
- Source inventory notes in architecture docs.

### Slice B (this branch)
- **`tara_app.workflow_engine.WorkflowEngine`**: real in-process DAG executor.
  - Sequential deterministic execution of dependency-ready steps.
  - Hard fail stops downstream steps (marks cancelled).
  - Approval-gated steps pause as `WAITING_APPROVAL` until `continue_run(..., approved_step_ids=...)`.
  - Cancellation marks remaining steps cancelled.
  - Result aggregation into `WorkflowResult`.
- **Tests:** `tests/test_workflow_engine.py` (10 cases, including concurrent continuation and cancellation races).
- **Safety:** Engine does **not** authorize side effects; executor + existing Security/Orchestrator remain authoritative.
- **Not connected** to live Orchestrator dispatch (per migration plan Phase 4 gate).

## Baseline verification (this environment)

```text
PYTHONPATH=src python3 -m unittest discover -s tests
# Ran 346 tests — OK (prior suite + 6 workflow engine tests)
```

Windows native Handler and live OmniRoute smoke are **not** claimed by this slice.

## Not completed yet

- Wire workflow engine into Orchestrator / ApplicationFacade with parity tests.
- Durable SQLite workflow state store (in-memory only).
- Parallel step execution (ready steps still run one-at-a-time for determinism).
- Consolidate `orchestrator.py` vs `orchestration.py`.
- Consolidate dual composition paths (`runtime.create_application` vs `TARAApplicationService`).
- Move packages by responsibility (Phase 6).
- Full per-file ownership matrix.

## Next sequence

1. Optional SQLite `WorkflowStore` for durable run state (still offline from live dispatch).
2. Facade methods for inspect/cancel workflow runs (read-only surface).
3. Parity harness comparing approval lifecycle before any live wire-up.
4. Consolidate composition roots behind one bootstrap.

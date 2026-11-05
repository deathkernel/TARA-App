# Architecture Migration Progress

**Branch:** \`architecture/wide-system-blueprint\`  
**Pull request:** [#69 — Wide responsibility-oriented architecture](https://github.com/deathkernel/TARA-App/pull/69)  
**Status:** In progress; first application-boundary slice committed.

## Completed in this slice

- Added \`tara_app.application\` as the application-facing package.
- Added \`ApplicationFacade\` as the single interface boundary for health, model catalogue, model lifecycle requests, chat, approval, cancellation and MCP operations.
- Added \`application.bootstrap.create_application()\` to compose the existing runtime coordinator behind the facade.
- Changed the CLI and public \`tara_app.create_application\` entry point to use the facade.
- Changed the HTTP server so it no longer reads the coordinator's registry or model catalogue directly.
- Preserved the existing coordinator, capability registry, adapter implementations, OmniRoute routing, MCP approval behavior and Windows pet's local HTTP transport.
- Added focused facade tests.
- Restored optional model-catalogue startup and shutdown hooks through the facade, with regression tests.
- Added versioned workflow request, step, DAG plan and result contracts with JSON payload bounds, cycle detection and validation tests.
- Added a source inventory and verified core dependency map; 93 Python source files and 82 native Handler files are recorded in the snapshot.

## Not completed yet

- The existing runtime builder still constructs the current coordinator and specialist adapters.
- Workflow state is not yet durable or centrally persisted.
- The workflow contracts are not yet wired into dispatch; they define the migration target only.
- Conversation history and pending approvals still live inside the current coordinator.
- \`orchestrator.py\` and \`orchestration.py\` have not yet been consolidated.
- Existing \`tara_*\` packages have not been moved or deleted.
- No full repository dependency graph or per-file ownership matrix has been generated yet.
- Windows native Handler and live OmniRoute behavior have not been verified by this documentation/code slice.

## Verification

The GitHub Actions workflow is triggered by branch pushes and the pull request. Do not treat a queued or pending run as a passing result. The full test suite and Windows-specific checks must pass before this slice is considered validated.

## Next implementation sequence

1. Validate this facade slice through CI and repair any regressions.
2. Build a source-level dependency and runtime call graph.
3. Consolidate the duplicate application/runtime composition paths.
4. Introduce typed workflow state and result propagation.
5. Move ownership and source files only after the call graph and tests establish safe boundaries.

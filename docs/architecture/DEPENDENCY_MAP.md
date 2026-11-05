# TARA Source Inventory and Dependency Map

**Snapshot:** \`architecture/wide-system-blueprint\`  
**Purpose:** Evidence-based inventory for the next migration phase. This is a source map, not a claim that all import edges have been exhaustively resolved.

## Repository inventory

The tracked tree contains 280 files at this snapshot:

| Area | Files | Ownership |
|---|---:|---|
| \`src/\` | 178 | Python application, specialist packages, web assets and native Handler |
| Python source under \`src/\` | 93 | Runtime, application, adapters, specialist services and entry points |
| \`src/tara_app/native/\` | 82 | Native Handler implementation, headers, build files and related native assets |
| \`tests/\` | 53 | Python tests and supporting test assets |
| \`frontend/\` | 7 | React/TypeScript/Vite frontend files |
| Other root/docs/config assets | 42 | Packaging, documentation, workflows, scripts and configuration |

Counts are a tree snapshot; generated build output and ignored local files are not included.

## Current runtime path (verified from source)

\`\`\`text
tara_app.cli
  -> tara_app.application.bootstrap.create_application
      -> tara_app.runtime.create_application
          -> TOML validation and environment filtering
          -> StdioRouterClient
          -> CapabilityRegistry
          -> StdioModuleAdapter / HandlerProcessAdapter
          -> optional McpToolGateway
          -> Orchestrator
      -> ApplicationFacade
  -> webapp.serve(ApplicationFacade)
       or windows_pet.run_floating_pet(ApplicationFacade)
\`\`\`

The runtime builder returns the existing \`Orchestrator\`; the facade is currently an interface boundary around it. The coordinator is not yet replaced by the future workflow engine.

## Core dependency edges observed in imports

| Source | Imports / depends on | Current responsibility |
|---|---|---|
| \`runtime.py\` | contracts, handler/module adapters, MCP client/config, orchestrator, registry, router client | Trusted TOML parsing and runtime composition |
| \`orchestrator.py\` | adapters, contracts, legacy Ollama model catalogue type, MCP mixin, registry | Routing validation, capability dispatch, chat history and in-memory pending approvals |
| \`orchestration.py\` | audit, permissions | Separate permission-aware capability dispatcher |
| \`application_service.py\` | audit, model catalogue, orchestration, runtime manager, sessions | Separate headless application service and session workflow |
| \`runtime_manager.py\` | config, contracts, Ollama provider | Legacy standalone local model runtime manager |
| \`application/bootstrap.py\` | application facade, runtime builder | Current composition wrapper |
| \`application/facade.py\` | contracts | Interface-facing use-case facade; delegates to current coordinator |

These edges are direct Python imports observed in the listed files. Runtime calls and dynamically loaded specialist processes are separate edges and require their own tracing.

## Ownership inventory by package

| Package / area | Current role | Migration treatment |
|---|---|---|
| \`tara_app\` | Core contracts, composition, web interface, registry, policy, adapters and native integration | Split by responsibility after call-graph and contract parity |
| \`tara_app/application\` | New application facade and bootstrap wrapper | Grow into canonical use-case boundary |
| \`tara_app/native/handler\` | C++ native Handler and risk-tested process boundary | Keep isolated as platform/execution integration; do not bulk-move without native CI |
| \`tara_chat\` | Chat specialist, provider selection, memory and repository audit | Keep specialist capability; move provider wiring behind infrastructure ports |
| \`tara_code\` | Code specialist entry point | Inspect service and process contracts before relocation |
| \`tara_creative\` | Creative specialist | Preserve capability and transport contracts |
| \`tara_data\` | Data specialist | Preserve bounded-input behavior |
| \`tara_memory\` | Memory specialist | Keep explicit approval around writes/forget operations |
| \`tara_models\` | Model specialist entry point | Treat model catalogue as OmniRoute gateway capability, not direct Ollama lifecycle |
| \`tara_planner\` | Planning specialist | Keep planning separate from authorization/execution |
| \`tara_research\` | Research specialist | Keep remote-data policy and network boundary explicit |
| \`tara_router\` | Router specialist entry point | Keep routing as proposal, never as permission |
| \`tara_security\` | Security specialist | Keep policy decisions authoritative and independent of model output |
| \`tara_study\` | Study specialist | Preserve source-grounding and bounded study workflows |
| \`tara_vision\` | Vision specialist | Preserve attachment and remote-processing consent boundary |
| \`tara_voice\` | Voice specialist | Preserve optional dependency and audio-data boundaries |
| \`tara_weather\` | Weather specialist | Keep external network access behind adapter boundary |
| \`tara_action\` | Action specialist | Side effects remain allowlisted and approval-gated |

Specialist package names describe capabilities that exist today. The target architecture does not require retaining them as top-level architectural layers; they can become use cases/handlers within the responsibility-oriented system once their contracts are mapped.

## Workflow contract groundwork

`workflow_contracts.py` now defines versioned request, step, plan and result shapes. `WorkflowPlan` rejects duplicate step IDs, missing dependencies and dependency cycles. Input/result mappings are checked for JSON compatibility and a 1 MB bound. These contracts are not yet consumed by the live `Orchestrator`; no dispatch or persistence behavior changes until the coordinator integration phase.

## Duplicate / competing ownership to resolve

1. **Composition:** \`runtime.py\` is the live CLI composition path; \`application_service.py\` is a separate headless path with its own session/audit/model dependencies. Do not replace one with the other until feature parity is demonstrated.
2. **Coordination:** \`orchestrator.py\` owns current request routing, chat history and pending approvals. \`orchestration.py\` is a distinct permission dispatcher used by the headless service. They are not drop-in equivalents.
3. **Model lifecycle:** \`runtime.py\` documents OmniRoute as the active inference gateway and returns \`model_catalog=None\`; legacy Ollama classes and environment validation still exist elsewhere. Do not re-enable direct Ollama inference as a side effect of cleanup.
4. **State:** chat history and pending approvals are bounded in-memory structures inside the current orchestrator; sessions/audit in the separate application service are a different state path. Durable workflow state is not implemented by the facade slice.
5. **Native execution:** the C++ Handler is a separate build/test boundary. It must retain its own Windows and Linux build/risk tests throughout Python restructuring.

## Next evidence required before consolidation

- Enumerate imports for all 93 Python files, including dynamic imports and subprocess entry points.
- Trace each specialist's stdin/stdout contract and timeout/error behavior.
- Map every HTTP route to its application method and tests.
- Map desktop pet lifecycle, loopback server, worker cancellation and shutdown.
- Map approval issuance, expiry, session binding, execution-time revalidation and MCP token consumption.
- Record persistence locations, retention behavior and secret/environment sources.
- Establish a passing baseline for Python tests, frontend build and both native Handler CI jobs.

## Stop conditions

Do not delete or relocate a module based only on its filename, package name or apparent duplication. Require call-site evidence, replacement ownership, contract tests and platform CI first.

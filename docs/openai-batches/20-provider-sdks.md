# Batch 20 — Provider SDK boundaries

## Repositories
`openai/openai-python`, `openai/openai-node`, `openai/openai-go`, `openai/openai-dotnet`, and `openai/openai-java`.

## Adoption rule
TARA-App currently has a Python backend and React/TypeScript frontend. Python is the only SDK that may be considered for the current backend. Node is considered only for a real Node service; Go, .NET, and Java remain documentation/reference until a TARA service exists in those languages.

## Implementation files expected
- Provider-neutral interface and Python adapter behind an optional extra.
- Secret-loading helper using environment/local secret configuration; never persist keys in source/config examples.
- Mocked provider contract tests and redaction tests.
- A separate opt-in live test marker, excluded from default CI.

## Acceptance checks
- Default installation remains free of mandatory provider SDK dependencies.
- No API call occurs on import, startup, or model discovery.
- Remote provider selection is explicit and visibly remote.
- Errors, request IDs, and logs are scrubbed of credentials and sensitive payloads.
- Docs distinguish free SDK software from potentially paid hosted inference.

## Non-goals
Do not add multiple language SDKs to the Python runtime, and do not create a second backend just to use a client library.
# OmniRoute integration

TARA-Chat can use OmniRoute as its OpenAI-compatible inference gateway. When
enabled, OmniRoute selects the underlying provider/model; TARA does not add a
second model router. TARA's capability router (Chat vs Code vs Research vs
Security), memory, permissions, and local tool execution remain independent.

## Windows PowerShell setup

Set the backend and key in the current terminal session:

```powershell
$env:TARA_LLM_BACKEND = "omniroute"
$env:TARA_OMNIROUTE_BASE_URL = "http://127.0.0.1:20128/v1"
$env:TARA_OMNIROUTE_MODEL = "auto"
$env:TARA_OMNIROUTE_API_KEY = Read-Host "OmniRoute API key"
```

Then launch TARA using the usual `run-tara.bat` or configured launcher from
that same PowerShell session. The key is passed only to the Chat module process;
it is not written to TOML, browser storage, frontend bundles, prompts, or logs.

To persist the key, use Windows User Environment Variables or PowerShell's
`[Environment]::SetEnvironmentVariable(..., "User")` after considering that
user-level environment variables are readable by processes running as that
user. Do not commit the key or paste it into issue reports.

## Auto Router aliases

The default request model is `auto` (balanced routing). OmniRoute documents
additional profiles such as `auto/coding`, `auto/cheap`, `auto/fast`,
`auto/offline`, `auto/smart`, and `auto/lkgp`. These are OmniRoute routing
profiles, not concrete model IDs. The selected profile can be set with
`TARA_OMNIROUTE_MODEL`; TARA passes it through unchanged. OmniRoute must have
eligible connected providers/models for the chosen profile.

To use only local providers, select `auto/offline` and ensure the Ollama
connection is enabled and healthy in OmniRoute. This does not create or
register TARA's Ollama model catalogue; OmniRoute is responsible for the
underlying model routing.

## Test and troubleshooting

- Confirm OmniRoute is reachable at `http://127.0.0.1:20128`.
- Confirm the API key is active in OmniRoute.
- Check `GET /v1/models` in OmniRoute to confirm its advertised models/routes.
- TARA's Chat module calls `POST /v1/chat/completions` with
  `Authorization: Bearer <key>`, `stream: false`, and the configured route
  alias.
- A 401/403 indicates key or permission configuration; 404 may indicate a
  wrong base URL/API root; 5xx or timeout may indicate provider/routing failure.

The provider currently uses non-streaming Chat Completions because TARA's
conversation adapter expects a complete string from its `complete()`
interface. Streaming UI support is a separate future enhancement.

# OmniRoute-only AI integration

TARA uses OmniRoute as its **only language-model gateway**. TARA's specialist router decides whether a request belongs to Chat, Code, Vision, Creative, or Model Hub. OmniRoute selects the actual model/provider and forwards the request. TARA retains conversation context, local memory, permissions, security policy, and desktop tool execution.

TARA does not directly call Ollama, Gemini, BharatCode, or another model provider for language-model inference. Legacy Ollama adapter/runtime-manager source files remain for compatibility and their isolated tests, but the current TARA-App launcher does not register or instantiate them. There is no silent local-model fallback: if OmniRoute or its API key is unavailable, the inference request fails closed.

## Windows PowerShell setup

Start OmniRoute and confirm the local gateway is reachable at `http://127.0.0.1:20128`.

In the same PowerShell window used to start TARA, set the API key:

```powershell
$env:TARA_OMNIROUTE_API_KEY = Read-Host "OmniRoute API key"
$env:TARA_OMNIROUTE_BASE_URL = "http://127.0.0.1:20128/v1"
```

Then launch TARA using `run-tara.bat` or the configured launcher from that same PowerShell session. The key is passed only to the specialist processes that need it. It is not written to TOML, browser storage, frontend bundles, prompts, or logs.

To persist the key, use Windows User Environment Variables or PowerShell's `[Environment]::SetEnvironmentVariable(..., "User")` after considering that user-level environment variables are readable by processes running as that user. Never commit the key or paste it into issue reports.

## Configuration and routing

The example `tara-app.example.toml` contains:

```toml
[omniroute]
base_url = "http://127.0.0.1:20128/v1"

[omniroute.models]
chat = "auto"
code = "auto/coding:cheap"
vision = "auto"
creative = "auto/cheap"
models = "auto"
```

These are OmniRoute route aliases, not necessarily concrete model IDs. The route can be changed per specialist in the TOML configuration or with its corresponding environment variable:

Each of the Chat, Code, Vision, Creative, and Model Hub entries in `tara-app.toml` must explicitly set `allow_remote = true`. This is the opt-in that allows the specialist to send user content through OmniRoute. If it is false or omitted, TARA leaves that specialist disabled; the app does not silently enable remote transfer.

| Specialist | Environment variable | Default route |
|---|---|---|
| Chat | `TARA_OMNIROUTE_MODEL` | `auto` |
| Code | `TARA_CODE_MODEL` | `auto/coding:cheap` |
| Vision | `TARA_VISION_MODEL` | `auto` |
| Creative | `TARA_CREATIVE_MODEL` | `auto/cheap` |
| Model Hub | `TARA_MODELS_MODEL` | `auto` |

OmniRoute must have eligible connected providers/models for each task type. In particular, the selected Vision route must support image input. TARA passes the route alias through; OmniRoute owns underlying provider/model selection and fallback.

## Data handling and security

- Chat prompts, recent conversation history, and relevant saved-memory snippets are sent to OmniRoute for inference.
- Code questions and any source attachments explicitly supplied to Code are sent to OmniRoute.
- Creative briefs are sent to OmniRoute.
- Images submitted to Vision are encoded as OpenAI-compatible image content and sent through OmniRoute. Successful Vision responses include `images_sent_to_remote: true`.
- Model Hub prompts are sent through OmniRoute. The model catalogue is read from `GET /v1/models`.
- The selected provider behind OmniRoute may be remote/cloud-based. Review provider configuration, data retention, and billing before sending sensitive material. Do not send passwords, API keys, or confidential workspace contents unless you have explicitly accepted that transfer.
- Model output is untrusted data. It cannot directly execute host commands, change files, or bypass TARA's local capability registry, security checks, and approval flow.
- TARA's Windows automation, file operations, memory, and deterministic diagnostics remain local.
- Optional faster-whisper transcription and browser read-aloud are separate speech features; they are not fallback language models.

## API behavior

- Base URL: `http://127.0.0.1:20128/v1`
- Model discovery: `GET /models`
- Inference: `POST /chat/completions`
- Authentication: `Authorization: Bearer <key>`
- Requests are non-streaming where the current specialist adapter expects a complete response.
- Redirects are rejected, requests use the loopback gateway only, and response sizes/timeouts are bounded.
- Provider response bodies and API keys are not copied into TARA's user-facing error messages or logs.

## Verification and troubleshooting

1. Confirm OmniRoute is running at `http://127.0.0.1:20128`.
2. Confirm the API key is active in OmniRoute.
3. Check `GET /v1/models` to confirm the gateway exposes connected models/routes.
4. Test Chat, Code, Vision, Creative, and Model Hub independently.
5. Check TARA /api/health: model_gateway.status is healthy only after an authenticated GET /v1/models succeeds. Otherwise the app reports degraded.
6. Open /api/models to read the live OmniRoute catalogue. It returns HTTP 503 and an unavailable status when the gateway cannot provide a valid catalogue; it no longer presents an empty, successful model list.
7. For Vision, ensure the selected route supports image input. A successful gateway health check verifies authentication and catalogue reachability, not that every configured specialist route is eligible for its task.
8. A 401/403 indicates key or permission configuration; 404 may indicate a wrong API root; 429 indicates quota/rate limiting; 5xx or timeout may indicate provider/routing failure.
9. If the gateway or key is unavailable, TARA reports the inference provider as unavailable. It must not fall back to direct Ollama or Gemini.

The Chat adapter currently uses non-streaming Chat Completions because TARA's conversation adapter expects a complete response string. Streaming UI support is a separate enhancement.

# MCP direct integration

## Branch: `feat/mcp-direct-integration`

### Included modules
- `src/tara_app/mcp_registry.py` — allowlist config
- `src/tara_app/mcp_client.py` — tool gateway
- `src/tara_app/mcp_toml.py` — TOML loader
- `src/tara_app/mcp_app.py` — Orchestrator mixin
- `pyproject.toml` — optional `[mcp]` extra

### Wire-up (required on merge)

**1. Orchestrator** (`src/tara_app/orchestrator.py`):

```python
from tara_app.mcp_app import McpOrchestratorMixin
```

```python
class Orchestrator(McpOrchestratorMixin):
```

In `__init__`, after `self.model_catalog = model_catalog`:

```python
self._init_mcp_state(None)
```

**2. Runtime** (`src/tara_app/runtime.py`):

- Allow top-level key `"mcp"` in the config set.
- After building registry/router, parse MCP and attach:

```python
from tara_app.mcp_client import McpToolGateway
from tara_app.mcp_registry import McpConfigError, parse_mcp_config, require_mcp_ready

mcp_raw = config.get("mcp")
try:
    mcp_config = parse_mcp_config(mcp_raw if isinstance(mcp_raw, dict) else None)
    require_mcp_ready(mcp_config)
except McpConfigError as exc:
    raise RuntimeConfigurationError(str(exc)) from exc
mcp_gateway = McpToolGateway(mcp_config) if mcp_config.enable else None
app = Orchestrator(registry, router, model_catalog=None)
if hasattr(app, "_init_mcp_state"):
    app._init_mcp_state(mcp_gateway)
return app
```

**3. Webapp** — expose `/api/mcp/tools`, `/api/mcp/approve`, `/api/mcp/call` and add `mcp` to `/api/health`.

### Enable

```toml
[mcp]
enable = true

[[mcp.servers]]
name = "time"
command = ["uvx", "mcp-server-time"]
enabled = true
read_only = true
timeout_seconds = 30
```

```bat
python -m pip install -e ".[mcp]"
```

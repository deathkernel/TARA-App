"""Provider-neutral boundary for optional agent orchestration SDKs."""
from __future__ import annotations
from collections.abc import Callable, Mapping
from typing import Any

class AgentAdapterError(RuntimeError):
    pass

class GuardedAgentAdapter:
    """Wrap an explicitly injected runner; tools are denied unless allowlisted."""
    def __init__(self, runner: Callable[[str, Mapping[str, Any]], Any], *, allowed_tools: frozenset[str] = frozenset(), enabled: bool = False) -> None:
        if not callable(runner):
            raise ValueError("runner must be callable")
        if type(enabled) is not bool or any(not isinstance(t, str) or not t.strip() for t in allowed_tools):
            raise ValueError("invalid agent policy")
        self._runner, self._allowed_tools, self._enabled = runner, allowed_tools, enabled

    def run(self, prompt: str, *, requested_tools: tuple[str, ...] = ()) -> Any:
        if not self._enabled:
            raise AgentAdapterError("agent orchestration is disabled")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be non-empty text")
        if any(tool not in self._allowed_tools for tool in requested_tools):
            raise AgentAdapterError("requested tool is not allowlisted")
        # No SDK import, network call, or execution is performed by this wrapper itself.
        return self._runner(prompt, {"allowed_tools": requested_tools})

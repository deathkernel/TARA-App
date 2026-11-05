"""Bridge helpers to run validated tool plans through the application coordinator.

These functions sit beside ApplicationFacade so HTTP/desktop UIs can adopt them
without requiring a large facade rewrite in the same commit.
"""
from __future__ import annotations

from typing import Any, Mapping

from tara_app.tool_loop import (
    ToolLoopResult,
    ToolPlan,
    ToolStepResult,
    ToolStepStatus,
    plan_from_mapping,
    run_tool_plan,
)


def validate_tool_plan(raw: Mapping[str, Any]) -> ToolPlan:
    """Validate a model- or UI-proposed tool plan without executing it."""
    return plan_from_mapping(raw)


def run_validated_tool_plan(
    coordinator: Any,
    plan: ToolPlan,
    *,
    session_id: str = "tool-loop",
    approval_tokens: Mapping[str, str] | None = None,
) -> ToolLoopResult:
    """Run a validated plan via MCP when the coordinator has a gateway."""
    gateway = getattr(coordinator, "mcp_gateway", None)
    if gateway is None:
        raise RuntimeError("MCP is disabled")

    def executor(step, *, approval_token):
        name = step.tool_name
        if "." in name:
            server, tool = name.split(".", 1)
        else:
            config = getattr(gateway, "_config", None)
            enabled = list(config.enabled_servers) if config is not None else []
            if not enabled:
                return ToolStepResult(
                    step.step_id,
                    ToolStepStatus.FAILED,
                    error_code="no_server",
                    error_message="No MCP server is enabled",
                )
            server, tool = enabled[0].name, name
        try:
            # Read-only access may receive an app-scoped token only when the
            # server configuration explicitly allowlists this exact tool.
            # Writable operations always require a token supplied after human approval.
            token = approval_token
            config = getattr(gateway, "_config", None)
            server_spec = next(
                (item for item in getattr(config, "enabled_servers", ()) if item.name == server),
                None,
            )
            is_configured_read_only = (
                server_spec is not None
                and bool(getattr(server_spec, "read_only", False))
                and tool in getattr(server_spec, "read_only_tools", ())
            )
            if token is None and is_configured_read_only:
                issuer = getattr(coordinator, "issue_mcp_approval_token", None)
                if callable(issuer):
                    token = issuer(
                        server, tool, dict(step.arguments), session_id=session_id
                    )
            if token is None:
                return ToolStepResult(
                    step.step_id,
                    ToolStepStatus.WAITING_APPROVAL,
                    error_code="approval_required",
                    error_message="Approval token missing",
                )
            output = coordinator.call_mcp_tool(
                server,
                tool,
                dict(step.arguments),
                approval_token=token,
                session_id=session_id,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolStepResult(
                step.step_id,
                ToolStepStatus.FAILED,
                error_code="mcp_call_failed",
                error_message=str(exc)[:500],
            )
        return ToolStepResult(step.step_id, ToolStepStatus.SUCCEEDED, output=str(output))

    return run_tool_plan(plan, executor, approval_tokens=approval_tokens)

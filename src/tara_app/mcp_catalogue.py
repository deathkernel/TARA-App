"""Curated, free-first MCP integration catalogue for the local manager UI.

Entries describe setup targets only; they never install, enable, or execute a server.
"""
from __future__ import annotations

_INTEGRATIONS = (
    {
        "id": "github", "name": "GitHub", "category": "Developer tools",
        "description": "Inspect repositories, files, issues, and pull requests.",
        "cost": "Free core; service limits apply", "access": "Read-only first",
        "status": "catalogue_only", "local": False,
        "requirements": ["GitHub account", "Fine-grained token with minimum read scopes"],
    },
    {
        "id": "filesystem", "name": "Filesystem", "category": "Local files",
        "description": "List and read files inside explicitly allowed folders.",
        "cost": "Free", "access": "Scoped read-only",
        "status": "implemented", "local": True,
        "requirements": ["TARA_MCP_FS_ROOTS"],
    },
    {
        "id": "google-drive", "name": "Google Drive", "category": "Cloud storage",
        "description": "Search and read files the user explicitly authorizes.",
        "cost": "Free API quota; Google plan limits apply", "access": "Read-only",
        "status": "catalogue_only", "local": False,
        "requirements": ["Google Cloud project", "OAuth consent and restricted Drive scopes"],
    },
    {
        "id": "postgresql", "name": "PostgreSQL", "category": "Databases",
        "description": "Inspect schemas and run read-only queries against a database.",
        "cost": "Free locally; hosting may cost", "access": "SELECT-only database role",
        "status": "catalogue_only", "local": True,
        "requirements": ["PostgreSQL instance", "Dedicated read-only database role"],
    },
    {
        "id": "browser", "name": "Browser (Playwright)", "category": "Browser",
        "description": "Navigate pages and inspect browser-visible content.",
        "cost": "Free open-source package", "access": "Navigation/read-only initially",
        "status": "catalogue_only", "local": True,
        "requirements": ["Node.js", "Playwright browser runtime"],
    },
    {
        "id": "git", "name": "Git", "category": "Developer tools",
        "description": "Read repository status, history, and selected files.",
        "cost": "Free", "access": "Read-only",
        "status": "implemented", "local": True,
        "requirements": ["TARA_MCP_GIT_ROOTS"],
    },
    {
        "id": "fetch", "name": "Fetch", "category": "Web",
        "description": "Fetch public HTTP(S) text with network safety checks.",
        "cost": "Free; public network access required", "access": "Public read-only",
        "status": "implemented", "local": True,
        "requirements": ["No API key"],
    },
    {
        "id": "time", "name": "Time", "category": "Utilities",
        "description": "Get current time and convert IANA timezones.",
        "cost": "Free", "access": "Read-only",
        "status": "implemented", "local": True,
        "requirements": ["Optional tzdata package"],
    },
    {
        "id": "notion", "name": "Notion", "category": "Productivity",
        "description": "Search and read pages shared with an integration.",
        "cost": "Free integration API; plan limits apply", "access": "Read-only",
        "status": "catalogue_only", "local": False,
        "requirements": ["Notion integration token", "Explicit page sharing"],
    },
    {
        "id": "slack", "name": "Slack", "category": "Productivity",
        "description": "Search and read messages in approved workspaces.",
        "cost": "Free API access; workspace limits apply", "access": "Read-only",
        "status": "catalogue_only", "local": False,
        "requirements": ["Slack app", "Minimum OAuth scopes and workspace approval"],
    },
    {
        "id": "linear", "name": "Linear", "category": "Project management",
        "description": "Read issues, projects, and cycles.",
        "cost": "Free API access; plan limits apply", "access": "Read-only",
        "status": "catalogue_only", "local": False,
        "requirements": ["Linear API key with minimum permissions"],
    },
    {
        "id": "google-calendar", "name": "Google Calendar", "category": "Productivity",
        "description": "Read calendar events and availability.",
        "cost": "Free API quota; service limits apply", "access": "Read-only",
        "status": "catalogue_only", "local": False,
        "requirements": ["Google Cloud project", "Read-only Calendar OAuth scope"],
    },
    {
        "id": "sentry", "name": "Sentry", "category": "Monitoring",
        "description": "Inspect project errors, issues, and releases.",
        "cost": "Free tier available; event limits apply", "access": "Read-only",
        "status": "catalogue_only", "local": False,
        "requirements": ["Sentry account", "Project-scoped read token"],
    },
    {
        "id": "docker", "name": "Docker", "category": "Developer tools",
        "description": "Inspect containers, images, and logs.",
        "cost": "MCP server free; Docker licensing may apply", "access": "Read-only metadata",
        "status": "catalogue_only", "local": True,
        "requirements": ["Docker Engine/Desktop", "Restricted daemon access"],
    },
)


def list_mcp_integrations() -> dict[str, object]:
    """Return display-safe metadata; never expose commands, tokens, or secrets."""
    entries = [dict(item, requirements=list(item["requirements"])) for item in _INTEGRATIONS]
    return {
        "status": "available",
        "policy": "free_first",
        "automatic_install": False,
        "write_tools_enabled": False,
        "integrations": entries,
        "summary": {
            "total": len(entries),
            "implemented": sum(item["status"] == "implemented" for item in entries),
            "catalogue_only": sum(item["status"] == "catalogue_only" for item in entries),
        },
    }

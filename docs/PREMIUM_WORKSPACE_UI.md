# TARA Premium Developer Workspace

## Product direction

TARA's React frontend is the primary desktop workspace when its compiled assets
are available. The layout is inspired by the workflow patterns in Claude Code
Desktop—session navigation, a focused task conversation, contextual side
panels, and visible activity—not a copy of its branding or proprietary assets.

Reference: [Claude's April 14, 2026 desktop redesign](https://claude.com/blog/claude-code-desktop-redesign).

## Layout

- **Left sidebar:** create/search/switch local sessions and enter Chat, Code,
  Research, or Study workflows.
- **Main workspace:** session header, conversation, Markdown/code rendering,
  file attachments, skill selection, edit/regenerate, scoped approval cards,
  and a compact composer.
- **Right inspector:** live specialist/gateway health, OmniRoute model routes,
  and the read-only MCP integration catalogue.
- **Activity panel:** local request lifecycle events and status messages.
- **Terminal state:** displayed as locked. It is not a terminal emulator and
  does not accept or execute commands.

The layout collapses the inspector and session navigation on narrow screens.
It uses keyboard-accessible controls, visible focus states, reduced-motion
support, `Ctrl/Cmd+N` for a new session, and `Ctrl/Cmd+K` to focus session
search.

## Working capabilities

The React workspace currently connects to these existing same-origin APIs:

- `GET /api/health`, `GET /api/models`, and `GET /api/skills`
- `GET /api/mcp/status` and `GET /api/mcp/catalogue`
- `POST /api/chat`, `POST /api/approve`, and `POST /api/cancel`

It supports local session history, up to four attachments with a combined
10 MB limit, selected skill metadata, Markdown responses, one-time approval
actions, message editing/regeneration for text-only prompts, and local browser
read-aloud voices. Image, audio, source-code and CSV inputs retain their
specialist-specific 512 KB limits; Study documents can use the larger
attachment allowance. Audio attachments default to a transcription request.
Conversation history and message text are stored in browser local storage;
attachment bytes are not persisted there.

Language-model prompts and supported attachments may be sent through OmniRoute
to providers configured by the user. Local read-aloud uses installed browser
voices and does not send text to OmniRoute.

## Explicitly unavailable until backend and security work exists

- No host shell or integrated command execution.
- No arbitrary workspace file editor or file-write controls.
- No diff-apply, Git commit, push, or merge controls.
- No pretend browser preview or live app server.
- No parallel worktree isolation or independent concurrent agent execution.
- No MCP server installation/enablement from the catalogue UI.

These capabilities need versioned backend contracts, bounded cancellation,
operation-bound approvals, audit coverage, and—where code execution is
involved—a real OS/container sandbox with filesystem, process, network, CPU,
memory, and time limits. UI controls must not imply a capability that the
backend cannot safely perform.

## Build and launch

The Windows and Unix launchers attempt to install frontend dependencies and
build `frontend/` when Node.js/npm is available. If the build is unavailable,
TARA continues to serve the existing static UI. The React UI is selected by
default when compiled assets exist; set `TARA_ENABLE_REACT_UI=0` to force the
static fallback.

CI runs TypeScript type-checking and the Vite production build. A successful
build is not a substitute for browser QA at desktop and mobile widths or a
Windows target-machine launch test.

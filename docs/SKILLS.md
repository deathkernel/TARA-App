# Agent Skills packs

Skill packs are folders with `SKILL.md` (+ optional `skill.toml`). Instructions
are text only; scripts are never auto-executed.

## Chat integration

- `GET /api/skills` — list available packs (`name`, `title`, `description`, `version`)
- `POST /api/chat` body may include `"skill": "study-notes"` (optional)

When set, TARA loads that pack from `TARA_SKILLS_ROOT` or `./skills` and appends
its instructions to the Chat system prompt for that request only. Skills are
**user-selected**, never auto-chosen from model text alone.

## Sample packs

| Pack | Use |
|------|-----|
| `study-notes` | Source-grounded study help |
| `code-review` | Read-only review guidance |
| `planner-outline` | Bounded plans without execution |

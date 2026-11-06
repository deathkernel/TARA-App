# Agent Skills packs

TARA can load **skill packs** — folders of instructions inspired by the
[Anthropic skills](https://github.com/anthropics/skills) format.

## Format

```text
skills/
  my-skill/
    SKILL.md      # required instructions (text only)
    skill.toml    # optional metadata
```

`skill.toml` fields: `title`, `description`, `version`, `tags`, `allowed_tools`,
`scripts`. **Scripts are metadata only** and are never executed by the loader.

## Safety

- Packs load only from an explicit skills root directory.
- Path traversal in pack names or script metadata is rejected.
- Instruction size is bounded.
- Skills do not grant permissions or bypass MCP/Security approval.

## API

```python
from pathlib import Path
from tara_app.skills import list_skill_packs, load_skill_pack

packs = list_skill_packs(skills_root=Path("skills"))
study = load_skill_pack("study-notes", skills_root=Path("skills"))
prompt = study.prompt_block()
```

## Chat UI

The loopback-only static Chat UI reads the installed skill list from
`GET /api/skills`. The endpoint returns display metadata (`name`, `title`,
`description`, `version`, and `tags`) only; it never returns skill instructions
or script metadata. The composer sends the selected pack name as the optional
`skill` field in `POST /api/chat`. Omitting the field keeps the default chat
behavior. Selecting a skill does not grant tool access or bypass approval.

When set, TARA loads that pack from `TARA_SKILLS_ROOT` or `./skills` and appends
its instructions to the Chat system prompt for that request only. Skills are
**user-selected**, never auto-chosen from model text alone.

**Routing limitation:** the selected skill prompt is currently forwarded only
when the router selects `chat.respond`. Specialist routes such as
`study.create` do not receive the selected skill prompt through
`Orchestrator.handle_question`; their responses may therefore not follow the
selected skill's instructions. Selecting a skill in the Chat UI does not imply
that specialist-generated output will use it.

## Sample packs in this repo

| Pack | Use |
|------|-----|
| `study-notes` | Source-grounded study help |
| `code-review` | Read-only review guidance |
| `planner-outline` | Bounded plans without execution |

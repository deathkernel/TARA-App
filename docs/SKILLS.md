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

## Sample packs in this repo

| Pack | Use |
|------|-----|
| `study-notes` | Source-grounded study help |
| `code-review` | Read-only review guidance |
| `planner-outline` | Bounded plans without execution |

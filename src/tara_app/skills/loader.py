"""Allowlisted skill-pack loader.

A skill pack is a directory containing ``SKILL.md`` (required) and optional
``skill.toml`` metadata. Only packs under an explicit root are visible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

_MAX_INSTRUCTION_CHARS = 100_000
_MAX_PACKS = 64
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class SkillLoadError(ValueError):
    """Raised when a skill pack is missing, invalid, or outside the root."""


@dataclass(frozen=True, slots=True)
class SkillPack:
    """One loaded skill pack (instructions are text data only)."""

    name: str
    title: str
    description: str
    version: str
    instructions: str
    tags: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    script_paths: tuple[str, ...] = ()
    root_path: str = ""

    def prompt_block(self) -> str:
        """Format instructions for inclusion in a specialist prompt."""
        header = f"# Skill: {self.title or self.name}\n"
        if self.description:
            header += f"{self.description.strip()}\n\n"
        return header + self.instructions.strip()


def _require_under_root(path: Path, root: Path) -> Path:
    root_resolved = root.expanduser().resolve()
    candidate = path.expanduser()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise SkillLoadError("skill path is outside the allowlisted skills root") from exc
    current = root_resolved
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                raise SkillLoadError("symbolic links are not allowed in skill packs")
        except OSError as exc:
            raise SkillLoadError("skill path could not be inspected safely") from exc
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise SkillLoadError("skill path is outside the allowlisted skills root") from exc
    return resolved


def _parse_toml_meta(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise SkillLoadError(f"invalid skill.toml: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillLoadError("skill.toml must be a table")
    return data


def load_skill_pack(name: str, *, skills_root: str | Path) -> SkillPack:
    """Load a single skill pack by directory name under ``skills_root``."""
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SkillLoadError("skill name must be lowercase alphanumeric with - or _")
    root = Path(skills_root)
    if not root.is_dir():
        raise SkillLoadError("skills root is not a directory")
    pack_dir = _require_under_root(root / name, root)
    if not pack_dir.is_dir():
        raise SkillLoadError(f"skill pack not found: {name}")
    skill_md = _require_under_root(pack_dir / "SKILL.md", root)
    if not skill_md.is_file():
        raise SkillLoadError("SKILL.md is required")
    try:
        instructions = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SkillLoadError(f"cannot read SKILL.md: {exc}") from exc
    if len(instructions) > _MAX_INSTRUCTION_CHARS:
        raise SkillLoadError("SKILL.md exceeds size limit")

    meta_path = _require_under_root(pack_dir / "skill.toml", root)
    meta = _parse_toml_meta(meta_path)
    title = str(meta.get("title") or name.replace("-", " ").title())
    description = str(meta.get("description") or "")
    version = str(meta.get("version") or "0.1.0")
    tags_raw = meta.get("tags") or []
    tools_raw = meta.get("allowed_tools") or []
    scripts_raw = meta.get("scripts") or []
    if not isinstance(tags_raw, list) or not isinstance(tools_raw, list) or not isinstance(scripts_raw, list):
        raise SkillLoadError("tags, allowed_tools, and scripts must be lists")
    tags = tuple(str(t).strip() for t in tags_raw if str(t).strip())
    allowed_tools = tuple(str(t).strip() for t in tools_raw if str(t).strip())
    script_paths = tuple(str(t).strip() for t in scripts_raw if str(t).strip())
    for script in script_paths:
        if ".." in Path(script).parts or Path(script).is_absolute():
            raise SkillLoadError("script paths must be relative without parent traversal")

    return SkillPack(
        name=name,
        title=title[:128],
        description=description[:512],
        version=version[:32],
        instructions=instructions,
        tags=tags[:16],
        allowed_tools=allowed_tools[:32],
        script_paths=script_paths[:16],
        root_path=str(pack_dir),
    )


def list_skill_packs(*, skills_root: str | Path) -> tuple[SkillPack, ...]:
    """List and load all valid skill packs under ``skills_root``."""
    root = Path(skills_root)
    if not root.is_dir():
        return ()
    packs: list[SkillPack] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not _NAME_RE.match(child.name):
            continue
        try:
            packs.append(load_skill_pack(child.name, skills_root=root))
        except SkillLoadError:
            continue
        if len(packs) >= _MAX_PACKS:
            break
    return tuple(packs)


def default_skills_root() -> Path:
    """Resolve the skills root from TARA_SKILLS_ROOT or the local ./skills directory."""
    import os

    configured = os.environ.get("TARA_SKILLS_ROOT", "").strip()
    return Path(configured).expanduser() if configured else Path("skills")

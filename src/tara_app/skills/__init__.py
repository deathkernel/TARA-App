"""Loadable Agent Skills packs for TARA (instructions + metadata only).

Skill packs never execute host scripts automatically. Script paths listed in a
manifest are metadata for human review or future sandboxed runners.
"""

from tara_app.skills.loader import SkillLoadError, SkillPack, list_skill_packs, load_skill_pack

__all__ = [
    "SkillLoadError",
    "SkillPack",
    "list_skill_packs",
    "load_skill_pack",
]

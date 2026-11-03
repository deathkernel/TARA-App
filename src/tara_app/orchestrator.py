"""Central capability validation and fail-closed module dispatch."""
from __future__ import annotations

from pathlib import Path

_code = (
    Path(__file__).with_name("_orchestrator_part_a.py").read_text(encoding="utf-8")
    + Path(__file__).with_name("_orchestrator_part_b.py").read_text(encoding="utf-8")
)
exec(compile(_code, str(Path(__file__).with_name("_orchestrator_combined.py")), "exec"), globals())

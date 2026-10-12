"""Export the scenario suite as a JSON dataset: ``python -m tracegap.export``."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .scenarios import MODES, SCENARIOS, assign_call_ids


def main(out: str = "data/scenarios.json") -> None:
    items = []
    for s in SCENARIOS:
        s = copy.deepcopy(s)
        assign_call_ids(s)
        items.append(asdict(s))
    doc = {"name": "TraceGap scenario suite", "version": __version__, "modes": MODES, "scenarios": items}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    print(f"wrote {out} ({len(items)} scenarios)")


if __name__ == "__main__":
    main()

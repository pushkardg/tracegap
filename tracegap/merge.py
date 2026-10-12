"""Merge results from several environments: ``python -m tracegap.merge OUT IN1 IN2 ...``.

Frameworks with conflicting dependencies run in separate virtualenvs; each
writes its own results.json (and trace corpus). This combines them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def merge(docs: list[dict]) -> dict:
    out = {k: docs[0][k] for k in ("benchmark", "version", "scenarios")}
    out["suite"] = docs[0].get("suite", "core")
    out["generated_at"] = max(d["generated_at"] for d in docs)
    out["python"] = ", ".join(sorted({d["python"] for d in docs}))
    out["adapters"] = {}
    out["results"] = []
    seen = set()
    for d in docs:
        if d["scenarios"].keys() != out["scenarios"].keys():
            raise SystemExit("cannot merge: scenario sets differ")
        for k, v in d["adapters"].items():
            if k in out["adapters"] and out["adapters"][k]["version"] != v["version"]:
                raise SystemExit(f"cannot merge: {k} appears with two versions")
            out["adapters"][k] = v
        for r in d["results"]:
            key = (r["adapter"], r["scenario"], r["mode"])
            if key in seen:
                raise SystemExit(f"cannot merge: duplicate case {key}")
            seen.add(key)
            out["results"].append(r)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("inputs", nargs="+")
    a = p.parse_args()
    docs = [json.loads(Path(f).read_text()) for f in a.inputs]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(merge(docs), indent=2))
    print(f"merged {len(a.inputs)} file(s) into {a.out}")


if __name__ == "__main__":
    main()

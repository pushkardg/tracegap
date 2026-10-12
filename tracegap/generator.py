"""Seeded scenario generator.

Builds random but reproducible scenarios from the same primitives as the
hand-written suite. ``generate(n, seed)`` always returns the same scenarios
for the same arguments, so a generated suite is as citable as the fixed one:
name it by (n, seed).

Every generated scenario keeps the properties the scorer relies on: each call
has a unique ``tag``, and timing-dependent endings leave generous margins
(cancellation lands inside a 3-second tool).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .core import Call, RunScript, Scenario, Turn

# kind -> (tool name, weight). Kinds that never execute are kept rarer so most
# scenarios exercise real execution.
KINDS = {
    "ok_echo": ("echo", 6),
    "ok_add": ("add", 4),
    "fail": ("fail", 3),
    "unknown": ("lookup_inventory", 1),
    "bad_type": ("add", 1),
    "missing_arg": ("add", 1),
    "big": ("big", 1),
    "record": ("record", 2),
    "nothing": ("nothing", 1),
    "sync": ("echo_sync", 2),
}
ENDINGS = ["final", "final", "final", "cancel_in_tool", "cancel_after", "model_error", "limit"]
TEXT = ["alpha", "beta", "gamma éè", "日本語", "quote \"x\"", "line\nbreak", "\U0001F680"]


@dataclass
class _Tags:
    prefix: str
    n: int = 0

    def next(self) -> str:
        self.n += 1
        return f"{self.prefix}{self.n}"


def _call(rng: random.Random, kind: str, tags: _Tags) -> Call:
    tool = KINDS[kind][0]
    tag = tags.next()
    if kind == "ok_echo":
        return Call(tool, {"tag": tag, "text": rng.choice(TEXT)})
    if kind == "ok_add":
        return Call(tool, {"tag": tag, "a": rng.randint(-50, 50), "b": rng.randint(-50, 50)})
    if kind == "fail":
        return Call(tool, {"tag": tag, "reason": rng.choice(["timeout", "quota", "not found", "denied"])})
    if kind == "unknown":
        return Call(tool, {"tag": tag, "sku": f"SKU-{rng.randint(100, 999)}"})
    if kind == "bad_type":
        return Call(tool, {"tag": tag, "a": "seven", "b": rng.randint(0, 9)})
    if kind == "missing_arg":
        return Call(tool, {"tag": tag, "a": rng.randint(0, 9)})
    if kind == "big":
        return Call(tool, {"tag": tag, "size": rng.choice([5_000, 50_000, 120_000])})
    if kind == "sync":
        return Call(tool, {"tag": tag, "text": rng.choice(TEXT)})
    return Call(tool, {"tag": tag})


def _turns(rng: random.Random, tags: _Tags, n_turns: int, max_width: int) -> list[Turn]:
    names = list(KINDS)
    weights = [KINDS[k][1] for k in names]
    turns = []
    for _ in range(n_turns):
        width = rng.randint(1, max_width)
        turns.append(Turn(calls=[_call(rng, rng.choices(names, weights)[0], tags) for _ in range(width)]))
    return turns


def _tools_for(runs: list[RunScript]) -> list[str]:
    used = set()

    def walk(rs: RunScript):
        for t in rs.turns:
            for c in t.calls:
                if c.name != KINDS["unknown"][0]:
                    used.add(c.name)
        if rs.nested:
            walk(rs.nested)

    for rs in runs:
        walk(rs)
    if not used:
        used.add("echo")
    return sorted(used)


def generate(n: int = 100, seed: int = 0) -> list[Scenario]:
    rng = random.Random(seed)
    out = []
    for i in range(1, n + 1):
        sid = f"G{seed}-{i:04d}"
        ending = rng.choice(ENDINGS)
        concurrent = ending in ("final", "model_error") and rng.random() < 0.15
        nested = not concurrent and ending == "final" and rng.random() < 0.15
        n_turns = rng.randint(1, 5)
        runs = []
        for r in range(2 if concurrent else 1):
            tags = _Tags(prefix=f"{'ab'[r]}")
            turns = _turns(rng, tags, n_turns, 4)
            nested_script = None
            if nested:
                ntags = _Tags(prefix="n")
                nested_script = RunScript(_turns(rng, ntags, rng.randint(1, 2), 2) + [Turn(final="inner done")])
                turns.insert(rng.randint(0, len(turns)), Turn(calls=[Call("delegate", {"tag": tags.next(),
                                                                                       "task": "sub-task"})]))
            if ending == "cancel_in_tool":
                turns.append(Turn(calls=[Call("slow", {"tag": tags.next(), "seconds": 3.0})]))
                turns.append(Turn(final="unreachable"))
            elif ending == "cancel_after":
                turns.append(Turn(final="late", delay=3.0))
            elif ending == "model_error":
                turns.append(Turn(raise_error="simulated provider 503"))
            else:
                turns.append(Turn(final="done"))
            runs.append(RunScript(turns, nested=nested_script))
        cancel_after = None
        max_calls = None
        if ending in ("cancel_in_tool", "cancel_after"):
            # Generous margin: earlier turns are quick; the 3 s step is where it lands.
            cancel_after = 0.6 + 0.15 * n_turns
        if ending == "limit":
            max_calls = rng.randint(1, max(1, n_turns - 1)) if n_turns > 1 else 1
        tools = _tools_for(runs) + (["delegate"] if nested else [])
        if ending == "cancel_in_tool" and "slow" not in tools:
            tools.append("slow")
        desc = f"{n_turns} turn(s), ending '{ending}'" + (", 2 concurrent runs" if concurrent else "") + (
            ", nested agent" if nested else "")
        out.append(Scenario(sid, "generated", f"Generated {i}", desc, runs, tools=sorted(set(tools)),
                            cancel_after=cancel_after, max_model_calls=max_calls))
    return out

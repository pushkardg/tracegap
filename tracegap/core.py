"""Core data model for TraceGap.

Ground truth comes from two framework-independent logs:

* the *emission log*: every tool call the scripted model actually emitted
  (what the agent was asked to do), and
* the *ledger*: every tool invocation that actually started, with its real
  arguments and real outcome (what really happened).

A framework's trace surface is scored against these two logs. Every tool takes
a ``tag`` argument that is unique per emitted call, so a recorded event can be
matched to ground truth without trusting framework-assigned identifiers.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------
# Scripted model turns
# --------------------------------------------------------------------------


@dataclass
class Call:
    """One tool call the scripted model will emit."""

    name: str
    args: dict
    call_id: Optional[str] = None  # filled in by the harness if None

    @property
    def tag(self) -> Optional[str]:
        return self.args.get("tag")


@dataclass
class Turn:
    """One scripted model response.

    Exactly one of ``calls`` (non-empty) or ``final`` is used. ``raise_error``
    makes the model call itself fail (simulated provider error). ``delay``
    makes the model call take that many seconds before answering.
    """

    calls: list[Call] = field(default_factory=list)
    final: Optional[str] = None
    raise_error: Optional[str] = None
    delay: float = 0.0


@dataclass
class RunScript:
    """Everything one agent run needs: its turns and an optional nested script
    used by the ``delegate`` tool (agent-as-tool)."""

    turns: list[Turn]
    nested: Optional["RunScript"] = None


@dataclass
class Scenario:
    id: str
    category: str
    title: str
    description: str
    runs: list[RunScript]
    tools: list[str]
    cancel_after: Optional[float] = None  # seconds; harness cancels the run(s)
    max_model_calls: Optional[int] = None  # framework turn/request limit
    notes: str = ""


class ModelProviderError(RuntimeError):
    """Raised by scripted models to simulate an LLM provider failure."""


class ToolFailure(Exception):
    """Raised by tools that are scripted to fail."""


# --------------------------------------------------------------------------
# Ground-truth logs
# --------------------------------------------------------------------------


@dataclass
class LedgerEntry:
    tag: Optional[str]
    name: str
    args: dict
    status: str = "running"  # running | ok | error | cancelled
    output: Any = None
    error: Optional[str] = None
    seq_start: int = 0
    seq_end: Optional[int] = None


@dataclass
class Emission:
    run_index: int
    call_id: str
    name: str
    args: dict
    tag: Optional[str]
    nested: bool = False


class GroundTruth:
    """Collects the emission log and the execution ledger for one case."""

    def __init__(self) -> None:
        self.ledger: list[LedgerEntry] = []
        self.emissions: list[Emission] = []
        self._seq = itertools.count(1)

    def next_seq(self) -> int:
        return next(self._seq)

    def emit(self, run_index: int, call: Call, nested: bool = False) -> None:
        self.emissions.append(
            Emission(run_index, call.call_id or "", call.name, dict(call.args), call.tag, nested)
        )

    def start(self, name: str, args: dict) -> LedgerEntry:
        e = LedgerEntry(tag=args.get("tag"), name=name, args=dict(args), seq_start=self.next_seq())
        self.ledger.append(e)
        return e


# A single process-wide pointer to the active ground truth. Cases run one at a
# time, so a module global is sufficient and keeps tool code framework-neutral.
_ACTIVE: Optional[GroundTruth] = None


def set_active(gt: Optional[GroundTruth]) -> None:
    global _ACTIVE
    _ACTIVE = gt


def active() -> GroundTruth:
    assert _ACTIVE is not None, "no active GroundTruth"
    return _ACTIVE


# --------------------------------------------------------------------------
# Normalized trace events (what adapters produce)
# --------------------------------------------------------------------------


@dataclass
class TraceEvent:
    """One tool call as recorded by a framework's trace surface.

    ``args``/``output`` are None when the surface does not capture them.
    ``status`` is one of ok | error | incomplete | unknown.
    ``group`` is the framework-reported run identity (trace id, root run id,
    result object). Used for the isolation check.
    """

    name: Optional[str]
    args: Optional[dict]
    status: str
    output: Any = None
    error: Optional[str] = None
    call_id: Optional[str] = None
    group: Optional[str] = None
    order: int = 0
    raw: Any = None

    @property
    def tag(self) -> Optional[str]:
        if isinstance(self.args, dict):
            t = self.args.get("tag")
            return t if isinstance(t, str) else None
        return None


@dataclass
class Capture:
    """Static description of what a trace surface records."""

    args: bool
    output: bool
    status: bool
    call_id: bool


def parse_args(value: Any) -> Optional[dict]:
    """Best-effort conversion of recorded arguments to a dict."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            v = json.loads(value)
        except Exception:
            # Some surfaces store a Python repr; try that too.
            try:
                import ast

                v = ast.literal_eval(value)
            except Exception:
                return {"__unparsed__": value}
        return v if isinstance(v, dict) else {"__unparsed__": value}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {"__unparsed__": repr(value)}


def new_loop_safe_cancel(task: asyncio.Task, delay: float) -> asyncio.TimerHandle:
    return asyncio.get_running_loop().call_later(delay, task.cancel)

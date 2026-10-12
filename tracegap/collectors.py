"""Span collectors that turn OpenTelemetry tool spans into TraceEvents.

Two conventions are supported:

* ``genai``: OpenTelemetry GenAI semantic conventions (``gen_ai.operation.name
  = execute_tool``, ``gen_ai.tool.name``, ``gen_ai.tool.call.id``,
  ``gen_ai.tool.call.arguments``, ``gen_ai.tool.call.result``).
* ``openinference``: OpenInference conventions used by Arize Phoenix and the
  ``openinference-instrumentation-*`` packages (``openinference.span.kind =
  TOOL``, ``tool.name``, ``input.value``, ``output.value``).

Any framework that emits either kind of span can be scored by writing only the
part of an adapter that drives the framework; the reading side is shared.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from . import otel_util
from .core import TraceEvent, parse_args


def _status(span) -> str:
    return otel_util.status_of(span)


def _error_text(span) -> str:
    parts = [span.status.description or ""]
    for e in span.events:
        a = dict(e.attributes or {})
        if "exception.message" in a:
            parts.append(str(a["exception.message"]))
    return " ".join(p for p in parts if p)


def _maybe_unwrap_input(value: Any) -> Optional[dict]:
    """OpenInference ``input.value`` is usually the JSON tool arguments, but some
    instrumentors wrap them (for example ``{"kwargs": {...}}`` or
    ``{"args": [...], "kwargs": {...}}``)."""
    args = parse_args(value)
    if isinstance(args, dict):
        for key in ("kwargs", "arguments", "input", "tool_input"):
            inner = args.get(key)
            if isinstance(inner, dict) and "tag" in inner:
                return inner
            if isinstance(inner, str):
                p = parse_args(inner)
                if isinstance(p, dict) and "tag" in p:
                    return p
    return args


def collect_genai(spans: Iterable) -> list[TraceEvent]:
    out = []
    for i, s in enumerate(sorted(spans, key=lambda s: s.start_time)):
        a = dict(s.attributes or {})
        if a.get("gen_ai.operation.name") != "execute_tool":
            continue
        ev = TraceEvent(
            name=a.get("gen_ai.tool.name"),
            args=parse_args(a.get("gen_ai.tool.call.arguments")),
            status=_status(s),
            output=a.get("gen_ai.tool.call.result"),
            call_id=a.get("gen_ai.tool.call.id"),
            group=format(s.context.trace_id, "032x"),
            order=i,
        )
        if ev.status == "error":
            ev.error = _error_text(s)
        out.append(ev)
    return out


def collect_openinference(spans: Iterable) -> list[TraceEvent]:
    out = []
    for i, s in enumerate(sorted(spans, key=lambda s: s.start_time)):
        a = dict(s.attributes or {})
        if str(a.get("openinference.span.kind", "")).upper() != "TOOL":
            continue
        output = a.get("output.value")
        ev = TraceEvent(
            name=a.get("tool.name") or s.name,
            args=_maybe_unwrap_input(a.get("tool.parameters") if a.get("input.value") is None else a.get("input.value")),
            status=_status(s),
            output=output,
            call_id=a.get("tool_call.id") or a.get("tool.id"),
            group=format(s.context.trace_id, "032x"),
            order=i,
        )
        if ev.status == "error":
            ev.error = _error_text(s)
        out.append(ev)
    return out


COLLECTORS = {"genai": collect_genai, "openinference": collect_openinference}


def collect(convention: str) -> list[TraceEvent]:
    """Read every finished span from the shared in-memory exporter."""
    spans = otel_util.provider()[1].get_finished_spans()
    return COLLECTORS[convention](spans)


def dump(spans: Iterable) -> str:
    """Debug helper: show tool-ish spans with their attributes."""
    rows = []
    for s in spans:
        rows.append({"name": s.name, "status": str(s.status.status_code), "attrs": dict(s.attributes or {})})
    return json.dumps(rows, indent=2, default=str)

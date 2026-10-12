"""Shared OpenTelemetry plumbing: one global provider with an in-memory
exporter, cleared per case. Only *ended* spans are exported, exactly as with
a real OTLP exporter."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_PROVIDER: TracerProvider | None = None
_EXPORTER: InMemorySpanExporter | None = None


def provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    global _PROVIDER, _EXPORTER
    if _PROVIDER is None:
        _EXPORTER = InMemorySpanExporter()
        _PROVIDER = TracerProvider()
        _PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
        trace.set_tracer_provider(_PROVIDER)
    return _PROVIDER, _EXPORTER  # type: ignore[return-value]


def status_of(span) -> str:
    from opentelemetry.trace import StatusCode

    return "error" if span.status.status_code == StatusCode.ERROR else "ok"

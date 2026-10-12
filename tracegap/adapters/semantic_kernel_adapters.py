"""Semantic Kernel (ChatCompletionAgent with auto function calling), scored
through two surfaces.

* ``filters``: a FUNCTION_INVOCATION filter that records start, result and
  exception for every function the kernel invokes. Filters are SK's
  documented hook for observing (and controlling) function calls.
* ``otel``: SK's built-in OpenTelemetry GenAI diagnostics (``execute_tool``
  spans), enabled with SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS
  (+ _SENSITIVE for arguments and results).

Kernel functions are registered in a plugin named ``tools``; the scripted
model calls them by their fully qualified name (``tools-echo``).
"""

from __future__ import annotations

import os

os.environ.setdefault("SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS", "true")
os.environ.setdefault("SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE", "true")

import json  # noqa: E402
from importlib.metadata import version as _v  # noqa: E402

from .. import collectors, otel_util  # noqa: E402

otel_util.provider()  # SK reads the global tracer provider at import time.

from semantic_kernel import Kernel  # noqa: E402
from semantic_kernel.agents import ChatCompletionAgent  # noqa: E402
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase  # noqa: E402
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior  # noqa: E402
from semantic_kernel.contents import (  # noqa: E402
    AuthorRole,
    ChatMessageContent,
    FunctionCallContent,
    StreamingChatMessageContent,
)
from semantic_kernel.filters import FilterTypes  # noqa: E402
from semantic_kernel.functions import KernelFunctionFromMethod, KernelPlugin, kernel_function  # noqa: E402

from ..core import Capture, TraceEvent, parse_args  # noqa: E402
from ..harness import Adapter, ScriptCursor  # noqa: E402
from ..tools import TOOLS, make_delegate  # noqa: E402

PLUGIN = "tools"


class ScriptedService(ChatCompletionClientBase):
    SUPPORTS_FUNCTION_CALLING: bool = True
    cursor: object = None

    def _items(self, turn):
        return [FunctionCallContent(id=c.call_id, name=f"{PLUGIN}-{c.name}", arguments=json.dumps(c.args))
                for c in turn.calls]

    @staticmethod
    def _tools_offered(settings) -> bool:
        # After maximum_auto_invoke_attempts SK resets function choice and asks
        # for a plain-text answer. A real model offered no tools cannot call
        # one, so answer in text without consuming the script.
        if getattr(settings, "function_choice_behavior", None) is None:
            return False
        return not (getattr(settings, "extension_data", None) or {}).get("tracegap_no_tools", False)

    def _reset_function_choice_settings(self, settings) -> None:
        # Real connectors clear the tool list here (for example OpenAI sets
        # tools=None); mirror that so the final call is tool-less.
        settings.extension_data["tracegap_no_tools"] = True

    async def _inner_get_chat_message_contents(self, chat_history, settings):
        if not self._tools_offered(settings):
            return [ChatMessageContent(role=AuthorRole.ASSISTANT, content="done")]
        turn = await self.cursor.next_turn()
        if not turn.calls:
            return [ChatMessageContent(role=AuthorRole.ASSISTANT, content=turn.final or "done")]
        return [ChatMessageContent(role=AuthorRole.ASSISTANT, items=self._items(turn))]

    async def _inner_get_streaming_chat_message_contents(self, chat_history, settings, function_invoke_attempt=0):
        if not self._tools_offered(settings):
            yield [StreamingChatMessageContent(role=AuthorRole.ASSISTANT, choice_index=0, content="done")]
            return
        turn = await self.cursor.next_turn()
        if not turn.calls:
            yield [StreamingChatMessageContent(role=AuthorRole.ASSISTANT, choice_index=0, content=turn.final or "done")]
            return
        yield [StreamingChatMessageContent(role=AuthorRole.ASSISTANT, choice_index=0, items=self._items(turn))]

    def _update_function_choice_settings_callback(self):
        return lambda *a, **k: None

    def service_url(self):
        return None


class _SKBase(Adapter):
    framework = "semantic-kernel"
    version = f"semantic-kernel {_v('semantic-kernel')}"

    def _kernel(self, run_index) -> Kernel:
        return Kernel()

    def _agent(self, cursor, scenario, nested_script, run_index, mode, name="agent"):
        fns = []
        for t in scenario.tools:
            if t == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    inner = self._agent(ScriptCursor(script, ri, nested=True), scenario, None, ri, mode, "inner")
                    return str(await inner.get_response(messages="sub-task"))

                fn = make_delegate(run_inner)
            else:
                fn = TOOLS[t]
            fns.append(KernelFunctionFromMethod(method=kernel_function(fn, name=t, description=fn.__doc__),
                                                plugin_name=PLUGIN))
        limit = scenario.max_model_calls or 50
        return ChatCompletionAgent(
            kernel=self._kernel(run_index),
            service=ScriptedService(ai_model_id="tracegap-scripted", cursor=cursor),
            plugins=[KernelPlugin(name=PLUGIN, functions=fns)],
            name=f"{name}{run_index}",
            function_choice_behavior=FunctionChoiceBehavior.Auto(maximum_auto_invoke_attempts=limit),
        )

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index, mode)
        if mode == "stream":
            async for _ in agent.invoke_stream(messages="go"):
                pass
            return "ok"
        return str(await agent.get_response(messages="go"))


class SemanticKernelFilters(_SKBase):
    surface = "filters"
    # The filter context has no tool-call id for plain function invocations.
    capture = Capture(args=True, output=True, status=True, call_id=False)

    async def setup_case(self, scenario, mode):
        self.events: list[TraceEvent] = []

    def _kernel(self, run_index) -> Kernel:
        k = Kernel()
        events = self.events

        async def record(context, next):
            ev = TraceEvent(name=context.function.name, args=parse_args(dict(context.arguments or {})),
                            status="incomplete", group=f"run{run_index}", order=len(events))
            events.append(ev)
            try:
                await next(context)
            except BaseException as e:
                ev.status, ev.error = "error", f"{type(e).__name__}: {e}"
                raise
            ev.status = "ok"
            ev.output = context.result.value if context.result is not None else None

        k.add_filter(FilterTypes.FUNCTION_INVOCATION, record)
        return k

    async def collect(self):
        return list(self.events)


class SemanticKernelOtel(_SKBase):
    surface = "otel"
    capture = Capture(args=True, output=True, status=True, call_id=True)

    async def setup_case(self, scenario, mode):
        otel_util.provider()[1].clear()

    async def collect(self):
        return collectors.collect("genai")

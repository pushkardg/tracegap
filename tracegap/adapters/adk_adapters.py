"""Google Agent Development Kit (LlmAgent + Runner), scored through two
surfaces.

* ``events``: the session events yielded by ``Runner.run_async`` (function_call
  and function_response parts), which ADK also persists to the session.
* ``otel``: ADK's ``execute_tool`` OpenTelemetry spans. Arguments and results
  are read from ADK's ``gcp.vertex.agent.tool_call_args`` /
  ``gcp.vertex.agent.tool_response`` attributes (results are wrapped as
  ``{"result": ...}``), as an ADK trace consumer would.

Modes: ``invoke`` uses the default run config, ``stream`` uses
``StreamingMode.SSE`` (the model is called with ``stream=True``).
"""

from __future__ import annotations

import json
import os
from importlib.metadata import version as _v

os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "true")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

from .. import otel_util  # noqa: E402

otel_util.provider()  # ADK creates its tracer at import time.

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.agents.run_config import RunConfig, StreamingMode  # noqa: E402
from google.adk.models.base_llm import BaseLlm  # noqa: E402
from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from ..core import Capture, TraceEvent, parse_args  # noqa: E402
from ..harness import Adapter, ScriptCursor  # noqa: E402
from ..tools import TOOLS, make_delegate  # noqa: E402

APP = "tracegap"


class ScriptedLlm(BaseLlm):
    cursor: object = None

    async def generate_content_async(self, llm_request, stream: bool = False):
        turn = await self.cursor.next_turn()
        if turn.calls:
            parts = [types.Part(function_call=types.FunctionCall(id=c.call_id, name=c.name, args=dict(c.args)))
                     for c in turn.calls]
        else:
            parts = [types.Part(text=turn.final or "done")]
        yield LlmResponse(content=types.Content(role="model", parts=parts), partial=False, turn_complete=True)


class _ADKBase(Adapter):
    framework = "google-adk"
    version = f"google-adk {_v('google-adk')}"

    def _agent(self, cursor, scenario, nested_script, run_index, mode, name="agent"):
        tools = []
        for t in scenario.tools:
            if t == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    inner = self._agent(ScriptCursor(script, ri, nested=True), scenario, None, ri, mode, "inner")
                    return await self._run_agent(inner, ri, mode, scenario, nested=True)

                tools.append(make_delegate(run_inner))
            else:
                tools.append(TOOLS[t])
        return LlmAgent(name=f"{name}{run_index}", model=ScriptedLlm(model="tracegap-scripted", cursor=cursor),
                        instruction="test", tools=tools)

    def _on_event(self, ev, run_index):
        pass

    async def _run_agent(self, agent, run_index, mode, scenario, nested=False):
        runner = InMemoryRunner(agent=agent, app_name=APP)
        session = await runner.session_service.create_session(app_name=APP, user_id="u")
        cfg = RunConfig(
            streaming_mode=StreamingMode.SSE if mode == "stream" else StreamingMode.NONE,
            max_llm_calls=scenario.max_model_calls or 50,
        )
        final = "done"
        async for ev in runner.run_async(user_id="u", session_id=session.id,
                                         new_message=types.Content(role="user", parts=[types.Part(text="go")]),
                                         run_config=cfg):
            self._on_event(ev, run_index)
            if ev.content and ev.content.parts and ev.content.parts[0].text:
                final = ev.content.parts[0].text
        return final

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index, mode)
        return await self._run_agent(agent, run_index, mode, scenario)


class ADKEvents(_ADKBase):
    surface = "events"
    capture = Capture(args=True, output=True, status=True, call_id=True)

    async def setup_case(self, scenario, mode):
        self.events: list[TraceEvent] = []
        self.by_key: dict = {}

    def _on_event(self, ev, run_index):
        if not ev.content or not ev.content.parts:
            return
        for p in ev.content.parts:
            if p.function_call is not None:
                fc = p.function_call
                te = TraceEvent(name=fc.name, args=parse_args(dict(fc.args or {})), status="incomplete",
                                call_id=fc.id, group=f"run{run_index}", order=len(self.events))
                self.events.append(te)
                self.by_key.setdefault((run_index, fc.id), []).append(te)
            elif p.function_response is not None:
                fr = p.function_response
                pending = [e for e in self.by_key.get((run_index, fr.id), []) if e.status == "incomplete"]
                if not pending:
                    continue
                te = pending[0]
                resp = fr.response or {}
                if isinstance(resp, dict) and "error" in resp and len(resp) == 1:
                    te.status, te.error = "error", str(resp["error"])
                else:
                    te.status = "ok"
                    te.output = resp.get("result", resp) if isinstance(resp, dict) else resp

    async def collect(self):
        return list(self.events)


def _unwrap(value):
    v = parse_args(value) if isinstance(value, str) else value
    if isinstance(v, dict) and set(v) == {"result"}:
        return v["result"]
    return value if v is None else v


class ADKOtel(_ADKBase):
    surface = "otel"
    capture = Capture(args=True, output=True, status=True, call_id=True)

    async def setup_case(self, scenario, mode):
        otel_util.provider()[1].clear()

    async def collect(self):
        spans = otel_util.provider()[1].get_finished_spans()
        out = []
        for i, s in enumerate(sorted(spans, key=lambda s: s.start_time)):
            a = dict(s.attributes or {})
            if a.get("gen_ai.operation.name") != "execute_tool":
                continue
            if a.get("gen_ai.tool.name") == "(merged tools)":
                # ADK adds one summary span per parallel batch; it is not a call.
                continue
            args = a.get("gen_ai.tool.call.arguments", a.get("gcp.vertex.agent.tool_call_args"))
            resp = a.get("gen_ai.tool.call.result", a.get("gcp.vertex.agent.tool_response"))
            call_id = a.get("gen_ai.tool.call.id")
            ev = TraceEvent(name=a.get("gen_ai.tool.name"), args=parse_args(args), status=otel_util.status_of(s),
                            output=_unwrap(resp), call_id=None if call_id == "<not specified>" else call_id,
                            group=format(s.context.trace_id, "032x"), order=i)
            if ev.status == "error":
                ev.error = (s.status.description or "") + " " + " ".join(
                    str(dict(e.attributes or {}).get("exception.message", "")) for e in s.events)
            out.append(ev)
        return out

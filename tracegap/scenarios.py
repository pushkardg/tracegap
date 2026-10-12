"""The TraceGap core scenario suite (22 hand-written scenarios, unchanged since v0.1).

Scenarios are framework-neutral: a scripted model emits exactly these tool
calls, so every framework faces identical inputs. Each scenario runs in two
execution modes (``invoke`` and ``stream``), giving 2 x len(SCENARIOS) cases.
"""

from __future__ import annotations

from .core import Call, RunScript, Scenario, Turn


def C(name: str, tag: str, **kw) -> Call:
    return Call(name=name, args={"tag": tag, **kw})


def T(*calls: Call, delay: float = 0.0) -> Turn:
    return Turn(calls=list(calls), delay=delay)


def F(text: str = "done", delay: float = 0.0) -> Turn:
    return Turn(final=text, delay=delay)


def ERR(msg: str = "simulated provider 500") -> Turn:
    return Turn(raise_error=msg)


def one(*turns: Turn, nested: RunScript | None = None) -> list[RunScript]:
    return [RunScript(turns=list(turns), nested=nested)]


SCENARIOS: list[Scenario] = [
    # ---------------- basic accounting ----------------
    Scenario(
        "S01", "basic", "Single call",
        "One successful tool call, then a final answer.",
        one(T(C("echo", "t1", text="hello")), F()),
        tools=["echo"],
    ),
    Scenario(
        "S02", "basic", "Sequential calls",
        "Three tool calls across three model turns.",
        one(T(C("echo", "t1", text="a")), T(C("add", "t2", a=2, b=3)), T(C("echo", "t3", text="c")), F()),
        tools=["echo", "add"],
    ),
    Scenario(
        "S03", "basic", "Parallel calls",
        "Five tool calls emitted in one model turn.",
        one(T(*[C("echo", f"t{i}", text=f"p{i}") for i in range(1, 6)]), F()),
        tools=["echo"],
    ),
    Scenario(
        "S04", "basic", "Long session",
        "Twenty-five sequential tool turns (limits raised so the run can finish).",
        one(*[T(C("add", f"t{i}", a=i, b=i)) for i in range(1, 26)], F()),
        tools=["add"],
        max_model_calls=40,
    ),
    # ---------------- tool failures ----------------
    Scenario(
        "S05", "failure", "Tool raises",
        "A tool raises an exception. The trace should record the call as failed.",
        one(T(C("fail", "t1", reason="disk full")), F()),
        tools=["fail"],
    ),
    Scenario(
        "S06", "failure", "Failure then retry",
        "A failing call is followed by a successful call in the next turn.",
        one(T(C("fail", "t1", reason="transient")), T(C("echo", "t2", text="retry ok")), F()),
        tools=["fail", "echo"],
    ),
    Scenario(
        "S07", "failure", "Parallel batch with one failure",
        "Three calls in one turn; the middle one raises. Siblings may or may not be cancelled.",
        one(T(C("slow", "t1", seconds=0.05), C("fail", "t2", reason="boom"), C("slow", "t3", seconds=0.05)), F()),
        tools=["slow", "fail"],
    ),
    # ---------------- calls that never execute ----------------
    Scenario(
        "S08", "rejected", "Unknown tool",
        "The model calls a tool that does not exist. Nothing executes; the attempt should still be visible.",
        one(T(C("delete_everything", "t1", path="/")), F()),
        tools=["echo"],
    ),
    Scenario(
        "S09", "rejected", "Invalid argument type",
        "The model passes a string where an integer is required.",
        one(T(C("add", "t1", a="two", b=3)), F()),
        tools=["add"],
    ),
    Scenario(
        "S10", "rejected", "Missing required argument",
        "The model omits a required argument.",
        one(T(Call("add", {"tag": "t1", "a": 1})), F()),
        tools=["add"],
    ),
    Scenario(
        "S11", "identity", "Duplicate call ids",
        "Two different calls in one turn share the same call id (a real provider glitch).",
        one(T(Call("echo", {"tag": "t1", "text": "first"}, call_id="dup"),
              Call("echo", {"tag": "t2", "text": "second"}, call_id="dup")), F()),
        tools=["echo"],
    ),
    # ---------------- payload fidelity ----------------
    Scenario(
        "S12", "payload", "Unicode and escape characters",
        "Arguments contain emoji, quotes, newlines, backslashes and non-Latin script.",
        one(T(C("echo", "t1", text='he said "hi"\n\tpath C:\\tmp \u2014 \u0928\u092e\u0938\u094d\u0924\u0947 \U0001F680')), F()),
        tools=["echo"],
    ),
    Scenario(
        "S13", "payload", "Large output",
        "A tool returns 200,000 characters.",
        one(T(C("big", "t1", size=200_000)), F()),
        tools=["big"],
    ),
    Scenario(
        "S14", "payload", "Structured output",
        "A tool returns a dict rather than a string.",
        one(T(C("record", "t1")), F()),
        tools=["record"],
    ),
    Scenario(
        "S15", "payload", "None output",
        "A tool returns None.",
        one(T(C("nothing", "t1")), F()),
        tools=["nothing"],
    ),
    Scenario(
        "S16", "payload", "Synchronous tool",
        "A plain (non-async) tool, which frameworks typically run in a worker thread.",
        one(T(C("echo_sync", "t1", text="threaded")), F()),
        tools=["echo_sync"],
    ),
    # ---------------- interrupted runs ----------------
    Scenario(
        "S17", "interrupt", "Cancelled during a tool",
        "The run is cancelled 0.3 s into a 2 s tool call. The call started but never finished.",
        one(T(C("echo", "t1", text="before")), T(C("slow", "t2", seconds=2.0)), F()),
        tools=["echo", "slow"],
        cancel_after=0.3,
    ),
    Scenario(
        "S18", "interrupt", "Cancelled after tools completed",
        "Two tools finish, then the run is cancelled while the model is thinking. Completed calls must not disappear.",
        one(T(C("echo", "t1", text="a")), T(C("add", "t2", a=1, b=1)), F(delay=2.0)),
        tools=["echo", "add"],
        cancel_after=0.3,
    ),
    Scenario(
        "S19", "interrupt", "Model error after tools",
        "Two tools finish, then the model provider fails. Completed calls must not disappear.",
        one(T(C("echo", "t1", text="a")), T(C("add", "t2", a=1, b=1)), ERR()),
        tools=["echo", "add"],
    ),
    Scenario(
        "S20", "interrupt", "Turn limit exceeded",
        "The model keeps calling tools past the framework's turn limit (3 model calls).",
        one(*[T(C("echo", f"t{i}", text=f"n{i}")) for i in range(1, 7)], F()),
        tools=["echo"],
        max_model_calls=3,
    ),
    # ---------------- structure ----------------
    Scenario(
        "S21", "structure", "Concurrent runs",
        "Two runs of the same agent execute concurrently. Each run's trace must contain only its own calls.",
        [
            RunScript([T(C("slow", "a1", seconds=0.05)), T(C("echo", "a2", text="A")), F()]),
            RunScript([T(C("echo", "b1", text="B")), T(C("slow", "b2", seconds=0.05)), F()]),
        ],
        tools=["slow", "echo"],
    ),
    Scenario(
        "S22", "structure", "Nested agent as tool",
        "The outer agent calls a 'delegate' tool that runs an inner agent, which calls its own tools.",
        one(
            T(C("delegate", "t1", task="sub-task")),
            F(),
            nested=RunScript([T(C("echo", "n1", text="inner")), T(C("add", "n2", a=4, b=5)), F("inner done")]),
        ),
        tools=["delegate", "echo", "add"],
    ),
]

MODES = ["invoke", "stream"]


def assign_call_ids(scn: Scenario) -> None:
    """Give every call a call id if it doesn't have one (prefixed by run)."""

    def walk(rs: RunScript, prefix: str) -> None:
        for turn in rs.turns:
            for c in turn.calls:
                if c.call_id is None:
                    c.call_id = f"call_{prefix}{c.tag}"
        if rs.nested:
            walk(rs.nested, prefix + "n_")

    for i, rs in enumerate(scn.runs):
        walk(rs, f"r{i}_")

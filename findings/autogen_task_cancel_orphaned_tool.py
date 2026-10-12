"""Repro: cancelling the asyncio task running AutoGen AssistantAgent.run()
does not stop an in-flight tool. The tool keeps running (and keeps its side
effects) after the caller has seen the run cancelled, and no trace surface
records its eventual completion.

AutoGen's documented cancellation path is CancellationToken (see
autogen_token_cancel_deadlock.py for what happens there). This repro covers
plain asyncio cancellation, e.g. ``asyncio.wait_for`` timeouts or a web
request being dropped.

Run: python autogen_task_cancel_orphaned_tool.py
"""

import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient

state = {"finished": False}


async def slow() -> str:
    """Takes two seconds, then records a side effect."""
    await asyncio.sleep(2)
    state["finished"] = True
    return "done"


async def main():
    usage = RequestUsage(prompt_tokens=0, completion_tokens=0)
    client = ReplayChatCompletionClient(
        [CreateResult(finish_reason="function_calls",
                      content=[FunctionCall(id="c1", arguments="{}", name="slow")], usage=usage, cached=False),
         "done"],
        model_info={"vision": False, "function_calling": True, "json_output": False,
                    "family": "unknown", "structured_output": False},
    )
    agent = AssistantAgent("a", model_client=client, tools=[slow])
    task = asyncio.create_task(agent.run(task="go"))
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("caller sees: run cancelled")
    await asyncio.sleep(2.5)
    print("tool side effect happened anyway:", state["finished"])
    if state["finished"]:
        print("BUG REPRODUCED: tool kept running after the run was cancelled")


asyncio.run(main())

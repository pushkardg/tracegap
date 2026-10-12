"""Repro: AutoGen AssistantAgent.run() never returns after CancellationToken
cancellation during a tool call.

The tool is cancelled correctly, but in ``AssistantAgent._process_model_result``
the helper ``_execute_tool_calls`` exits via ``CancelledError`` from
``asyncio.gather`` before it reaches ``stream_queue.put_nowait(None)``. The
consumer loop ``while True: event = await stream.get()`` then waits forever.

Expected: run() raises CancelledError (or returns) promptly.
Run: python autogen_token_cancel_deadlock.py
"""

import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_core import CancellationToken, FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient


async def slow() -> str:
    """Takes two seconds."""
    await asyncio.sleep(2)
    return "done"


async def main():
    usage = RequestUsage(prompt_tokens=0, completion_tokens=0)
    client = ReplayChatCompletionClient(
        [
            CreateResult(finish_reason="function_calls",
                         content=[FunctionCall(id="c1", arguments="{}", name="slow")], usage=usage, cached=False),
            "done",
        ],
        model_info={"vision": False, "function_calling": True, "json_output": False,
                    "family": "unknown", "structured_output": False},
    )
    agent = AssistantAgent("a", model_client=client, tools=[slow])
    token = CancellationToken()
    task = asyncio.create_task(agent.run(task="go", cancellation_token=token))
    await asyncio.sleep(0.3)
    token.cancel()
    done, _ = await asyncio.wait([task], timeout=10)
    if not done:
        print("BUG REPRODUCED: run() still pending 10 s after the token was cancelled")
        task.cancel()
    else:
        print("run() finished:", task.exception() if not task.cancelled() else "cancelled")


asyncio.run(main())

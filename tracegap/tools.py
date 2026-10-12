"""Framework-neutral tool implementations.

Every tool writes to the ground-truth ledger *from inside the tool body*, so
the ledger records what really executed regardless of what any framework
reports. Adapters register these functions with their framework unchanged
(every framework accepts plain annotated callables).
"""

from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from typing import Any, Callable

from .core import ToolFailure, active


@contextmanager
def _ledgered(name: str, args: dict):
    gt = active()
    entry = gt.start(name, args)
    try:
        yield entry
    except asyncio.CancelledError:
        entry.status = "cancelled"
        entry.error = "CancelledError"
        entry.seq_end = gt.next_seq()
        raise
    except BaseException as e:  # noqa: BLE001 - we re-raise
        entry.status = "error"
        entry.error = f"{type(e).__name__}: {e}"
        entry.seq_end = gt.next_seq()
        raise
    else:
        if entry.status == "running":
            entry.status = "ok"
        entry.seq_end = gt.next_seq()


async def echo(tag: str, text: str) -> str:
    """Return the text prefixed with 'echo:'."""
    with _ledgered("echo", {"tag": tag, "text": text}) as e:
        await asyncio.sleep(0)
        e.output = f"echo:{text}"
        return e.output


async def add(tag: str, a: int, b: int) -> int:
    """Add two integers."""
    with _ledgered("add", {"tag": tag, "a": a, "b": b}) as e:
        await asyncio.sleep(0)
        e.output = a + b
        return e.output


async def fail(tag: str, reason: str) -> str:
    """A tool that always raises an error with the given reason."""
    with _ledgered("fail", {"tag": tag, "reason": reason}):
        await asyncio.sleep(0)
        raise ToolFailure(f"tool failed: {reason}")


async def slow(tag: str, seconds: float) -> str:
    """Sleep for the given number of seconds, then return 'done'."""
    with _ledgered("slow", {"tag": tag, "seconds": seconds}) as e:
        await asyncio.sleep(seconds)
        e.output = "done"
        return e.output


async def big(tag: str, size: int) -> str:
    """Return a string of the given size."""
    with _ledgered("big", {"tag": tag, "size": size}) as e:
        await asyncio.sleep(0)
        body = (tag + ":") + ("x" * max(0, size - len(tag) - 1))
        e.output = body
        return body


async def record(tag: str) -> dict:
    """Return a small structured record."""
    with _ledgered("record", {"tag": tag}) as e:
        await asyncio.sleep(0)
        e.output = {"tag": tag, "items": [1, 2, 3], "ok": True}
        return e.output


async def nothing(tag: str) -> None:
    """Do nothing and return None."""
    with _ledgered("nothing", {"tag": tag}) as e:
        await asyncio.sleep(0)
        e.output = None
        return None


def echo_sync(tag: str, text: str) -> str:
    """Synchronous variant of echo (frameworks run it in a worker thread)."""
    with _ledgered("echo_sync", {"tag": tag, "text": text}) as e:
        time.sleep(0.01)
        e.output = f"echo:{text}"
        return e.output


TOOLS: dict[str, Callable[..., Any]] = {
    f.__name__: f for f in [echo, add, fail, slow, big, record, nothing, echo_sync]
}


def make_delegate(run_nested: Callable[[], Any]) -> Callable[..., Any]:
    """Build the ``delegate`` tool. ``run_nested`` is an adapter-supplied
    coroutine function that runs the inner agent and returns its final text."""

    async def delegate(tag: str, task: str) -> str:
        """Hand a sub-task to a helper agent and return its answer."""
        with _ledgered("delegate", {"tag": tag, "task": task}) as e:
            out = await run_nested()
            e.output = str(out)
            return e.output

    return delegate

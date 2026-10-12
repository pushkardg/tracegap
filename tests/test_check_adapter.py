import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tracegap.adapters.reference import ReferenceAdapter  # noqa: E402
from tracegap.check_adapter import check  # noqa: E402


class SilentAdapter(ReferenceAdapter):
    surface = "silent"

    async def collect(self):
        return []


def test_toy_example_passes_checks():
    assert asyncio.run(check("examples.toy_adapter:ToyHooksAdapter", repeat=1))


def test_reference_passes_with_no_failures(capsys):
    assert asyncio.run(check(ReferenceAdapter, repeat=1))
    assert "Score: complete 42/42, faithful 42/42" in capsys.readouterr().out


def test_adapter_that_reads_nothing_fails_calibration(capsys):
    assert not asyncio.run(check(SilentAdapter, repeat=1))
    assert "[FAIL] calibration" in capsys.readouterr().out

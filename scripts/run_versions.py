#!/usr/bin/env python3
"""Run TraceGap across many released versions of each framework.

Each (framework, version) gets a fresh virtualenv with only that framework
pinned (pip resolves its dependencies), runs the framework's adapters, and
writes results/versions/<framework>/<version>.json plus a trace corpus. The
virtualenv is deleted afterwards. Failures to install or to run are recorded
in results/versions/status.json rather than stopping the matrix.

    python scripts/run_versions.py                 # everything in VERSIONS
    python scripts/run_versions.py --only smolagents --jobs 2
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import urllib.request
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# framework -> (pip requirements template, adapter selector, versions newest first)
VERSIONS: dict[str, tuple[list[str], str, list[str]]] = {
    "langgraph": (["langgraph=={v}"], "langgraph",
                  ["1.2.12", "1.1.10", "1.0.10", "0.6.11", "0.5.4", "0.4.10"]),
    "openai-agents": (["openai-agents=={v}"], "openai-agents",
                      ["0.23.1", "0.22.3", "0.21.1", "0.20.0", "0.19.4", "0.18.3", "0.17.8", "0.16.1", "0.15.3",
                       "0.14.8"]),
    "pydantic-ai": (["pydantic-ai-slim=={v}", "opentelemetry-sdk"], "pydantic-ai",
                    ["2.54.0", "2.50.0", "2.45.0", "2.40.0", "2.35.3", "2.30.0", "2.25.0", "2.20.0", "2.15.0"]),
    "autogen": (["autogen-agentchat=={v}", "autogen-ext=={v}", "opentelemetry-sdk"], "autogen",
                ["0.7.5", "0.7.2", "0.6.4", "0.6.1", "0.5.7", "0.5.3", "0.4.9.3"]),
    "smolagents": (["smolagents=={v}", "openinference-instrumentation-smolagents", "opentelemetry-sdk"], "smolagents",
                   ["1.26.0", "1.24.0", "1.22.0", "1.20.0", "1.18.0", "1.16.1", "1.14.0"]),
    "llamaindex": (["llama-index-core=={v}", "openinference-instrumentation-llama-index", "opentelemetry-sdk"],
                   "llamaindex",
                   ["0.14.25", "0.14.20", "0.14.15", "0.14.10", "0.14.5", "0.14.0", "0.13.6", "0.12.52"]),
    "semantic-kernel": (["semantic-kernel=={v}", "opentelemetry-sdk"], "semantic-kernel",
                        ["1.44.1", "1.42.0", "1.40.0", "1.38.0", "1.36.2", "1.34.0", "1.32.2", "1.30.0"]),
    "google-adk": (["google-adk=={v}"], "google-adk",
                   ["2.11.0", "2.9.2", "2.7.1", "2.5.0", "2.3.0", "2.0.0", "1.39.1", "1.35.2"]),
    "crewai": (["crewai=={v}"], "crewai",
               ["1.15.23", "1.14.7", "1.12.2", "1.10.1", "1.8.1", "1.6.1"]),
}


def release_date(package: str, version: str) -> str:
    """Upload date of a release on PyPI (ISO date)."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/{version}/json", timeout=30) as r:
        info = json.load(r)
    return min(u["upload_time_iso_8601"] for u in info["urls"])[:10]


def run_one(fw: str, version: str, env_dir: Path, out_dir: Path, py: str) -> dict:
    reqs, selector, _ = VERSIONS[fw]
    venv = env_dir / f"{fw}-{version}"
    out = out_dir / fw / f"{version}.json"
    traces = out_dir / "traces" / fw / version
    status = {"framework": fw, "version": version, "stage": "install", "ok": False}
    t0 = time.time()
    try:
        shutil.rmtree(venv, ignore_errors=True)
        # Resolve dependencies as they were when this version was released (plus one
        # day), so a historical run sees what users actually installed at the time.
        main_pkg = reqs[0].split("==")[0]
        released = release_date(main_pkg, version)
        cutoff = (dt.date.fromisoformat(released) + dt.timedelta(days=1)).isoformat()
        status["released"] = released
        subprocess.run(["uv", "venv", "-q", "--python", py, str(venv)], check=True, capture_output=True)
        vpy = str(venv / "bin" / "python")
        pkgs = [q.format(v=version) for q in reqs]
        r = subprocess.run(["uv", "pip", "install", "-q", "--python", vpy, "--exclude-newer", cutoff] + pkgs,
                           capture_output=True, text=True, timeout=1200)
        status["resolution"] = f"as of {cutoff}"
        if r.returncode != 0:
            # Some old dependency sets cannot be built today (e.g. no wheels for this
            # Python yet at the time). Fall back to current resolution and say so.
            r = subprocess.run(["uv", "pip", "install", "-q", "--python", vpy] + pkgs,
                               capture_output=True, text=True, timeout=1200)
            status["resolution"] = "latest compatible (release-date resolution failed to install)"
        if r.returncode != 0:
            status["error"] = r.stderr.strip().splitlines()[-3:] or ["install failed"]
            return status
        subprocess.run(["uv", "pip", "install", "-q", "--python", vpy, "--no-deps", "-e", str(ROOT)],
                       check=True, capture_output=True, timeout=300)
        status["stage"] = "run"
        out.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, TRACEGAP_CASE_TIMEOUT="240")
        r = subprocess.run([str(venv / "bin" / "python"), "-m", "tracegap.cli", "--adapters", selector,
                            "--out", str(out), "--traces", str(traces)],
                           capture_output=True, text=True, timeout=3600, cwd=ROOT, env=env)
        if not out.exists():
            status["error"] = (r.stderr or r.stdout).strip().splitlines()[-3:]
            return status
        data = json.loads(out.read_text())
        skipped = [l for l in r.stderr.splitlines() if l.startswith("skipping ")]
        if skipped:
            status["skipped_adapters"] = skipped
        if not data["results"]:
            status["stage"] = "adapter-import"
            status["error"] = skipped or ["no cases ran"]
            return status
        errs = sum(1 for x in data["results"] if x["run_outcome"] == "harness-error")
        status.update(ok=True, stage="done", cases=len(data["results"]), harness_errors=errs,
                      adapters={k: v["version"] for k, v in data["adapters"].items()})
        if errs:
            first = next(x for x in data["results"] if x["run_outcome"] == "harness-error")
            status["first_harness_error"] = first["error"]
        return status
    except subprocess.TimeoutExpired as e:
        status["error"] = [f"timeout in {status['stage']}: {e}"]
        return status
    finally:
        status["seconds"] = round(time.time() - t0)
        shutil.rmtree(venv, ignore_errors=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*")
    p.add_argument("--versions", nargs="*", help="specific jobs, e.g. crewai==1.12.2 autogen==0.6.1")
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--env-dir", default=str(ROOT / ".envs" / "versions"))
    p.add_argument("--out-dir", default=str(ROOT / "results" / "versions"))
    p.add_argument("--python", default=sys.executable)
    a = p.parse_args()
    env_dir, out_dir = Path(a.env_dir), Path(a.out_dir)
    env_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    status_file = out_dir / "status.json"
    statuses = json.loads(status_file.read_text()) if status_file.exists() else {}
    jobs = [(fw, v) for fw, (_, _, vs) in VERSIONS.items() if not a.only or fw in a.only for v in vs]
    if a.versions:
        wanted = {tuple(x.split("==", 1)) for x in a.versions}
        jobs = [j for j in jobs if j in wanted]

    def task(job):
        fw, v = job
        s = run_one(fw, v, env_dir, out_dir, a.python)
        statuses[f"{fw}=={v}"] = s
        status_file.write_text(json.dumps(statuses, indent=2))
        mark = "ok " if s["ok"] and not s.get("harness_errors") else ("ERR" if not s["ok"] else "PART")
        print(f"[{mark}] {fw}=={v} ({s['seconds']}s) " + (str(s.get("error", "")) if not s["ok"] else
              f"{s['cases']} cases, {s.get('harness_errors', 0)} harness errors"), flush=True)
        return s

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        list(ex.map(task, jobs))


if __name__ == "__main__":
    main()

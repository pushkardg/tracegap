"""Render the leaderboard page from results.json: ``python -m tracegap.site``.

Writes an HTML fragment suitable for publishing as-is; ``--standalone`` wraps
it in a full document (for GitHub Pages).
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from .report import summarize

CSS = """
/* Layout: one reading column; the matrix and tables scroll inside their own frames. */
:root{
  --bg:#f5f7f8; --surface:#ffffff; --fg:#14202a; --muted:#56656f; --line:#d5dde2;
  --accent:#0b6e7a; --ok:#1f7a45; --ok-bg:#e1f2e7; --warn:#8a5a00; --warn-bg:#fbefd2;
  --bad:#b0322a; --bad-bg:#fbe3e0;
  --display:"Schibsted Grotesk",ui-sans-serif,system-ui,sans-serif;
  --body:"Schibsted Grotesk",ui-sans-serif,system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f1519; --surface:#161f25; --fg:#e3eaee; --muted:#9aa9b2; --line:#2a3740;
  --accent:#5cc3cf; --ok:#7fd6a0; --ok-bg:#163525; --warn:#f0c46a; --warn-bg:#3a2d10;
  --bad:#f39a90; --bad-bg:#3d1c19; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f1519; --surface:#161f25; --fg:#e3eaee; --muted:#9aa9b2; --line:#2a3740;
  --accent:#5cc3cf; --ok:#7fd6a0; --ok-bg:#163525; --warn:#f0c46a; --warn-bg:#3a2d10;
  --bad:#f39a90; --bad-bg:#3d1c19; color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:15px/1.55 var(--body)}
.wrap{max-width:1040px;margin:0 auto;padding-inline:16px;padding-block:32px 64px;display:grid;gap:40px}
header{display:grid;gap:12px}
.eyebrow{font:500 12px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h1{font:700 clamp(30px,5vw,44px)/1.1 var(--display);margin:0;letter-spacing:-.01em;text-wrap:balance}
h2{font:650 21px/1.25 var(--display);margin:0 0 6px;text-wrap:balance}
p{margin:0;max-width:68ch}
.lede{font-size:17px;color:var(--fg)}
.muted{color:var(--muted)}
.stats{display:flex;flex-wrap:wrap;gap:28px;padding-top:6px}
.stat b{display:block;font:600 26px/1.1 var(--mono);font-variant-numeric:tabular-nums}
.stat span{font-size:13px;color:var(--muted)}
section{display:grid;gap:14px;min-width:0}
.frame{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
tr:last-child td{border-bottom:0}
th{font:500 12px/1.3 var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--muted);background:var(--bg)}
td.num{font-family:var(--mono);text-align:right}
th.num{text-align:right}
code,.mono{font-family:var(--mono);font-size:.92em}
.fw{font-family:var(--mono);font-size:13px}
.pill{display:inline-block;font:600 11px/1 var(--mono);padding:5px 6px;border-radius:4px;min-width:22px;text-align:center}
.p-ok{background:var(--ok-bg);color:var(--ok)}
.p-warn{background:var(--warn-bg);color:var(--warn)}
.p-bad{background:var(--bad-bg);color:var(--bad)}
.cell{display:flex;gap:4px}
.cat{font:500 11px/1 var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.legend{display:flex;flex-wrap:wrap;gap:16px;font-size:13px;color:var(--muted);align-items:center}
.legend span{display:inline-flex;gap:6px;align-items:center}
.matrix td:first-child{white-space:normal;min-width:190px}
details{border-top:1px solid var(--line);padding-block:10px}
summary{cursor:pointer;font-weight:600}
summary:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
details ul{margin:8px 0 0;padding-left:18px;font-size:13.5px;display:grid;gap:4px}
.finding{display:grid;gap:4px;padding:14px 16px;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
.finding .fw{color:var(--accent)}
.findings{display:grid;gap:12px}
a{color:var(--accent)}
footer{font-size:13px;color:var(--muted);display:grid;gap:4px}
"""


def pill(complete: bool, faithful: bool, mode: str, reasons: list[str]) -> str:
    if complete and faithful:
        cls, txt = "p-ok", "CF"
    elif complete:
        cls, txt = "p-warn", "C·"
    else:
        cls, txt = "p-bad", "·F" if faithful else "··"
    tip = f"{mode}: " + ("passed" if not reasons else "; ".join(reasons))
    return f'<span class="pill {cls}" title="{html.escape(tip)}">{txt}</span>'


def render(data: dict, gen: dict | None = None) -> str:
    rows = summarize(data)
    order = sorted(rows, key=lambda k: (-rows[k]["complete"], -rows[k]["faithful"], k))
    res = data["results"]
    tot = len(res)
    comp = sum(r["complete"] for r in res)
    both = sum(r["passed"] for r in res)
    fully = sum(1 for k in rows if rows[k]["complete"] == rows[k]["cases"])
    n_scn = len(data["scenarios"])
    def pct(a, b):
        return "n/a" if b == 0 else f"{100 * a / b:.1f}%"

    from .report import tiered

    t = tiered(data, gen)
    lb, lbs = [], []
    for i, k in enumerate(t["order"], 1):
        r = t["rows"][k]
        c, f, n = r["stable"]
        caps = "".join(f"<td class='num'>{a}/{b}</td>" for a, b in r["caps"])
        lb.append(
            f"<tr><td class='num'>{i}</td><td class='fw'>{html.escape(k)}</td>"
            f"<td class='fw'>{html.escape(r['version'])}</td>"
            f"<td class='num'><b>{pct(c, n)}</b> <span class='muted'>{c}/{n}</span></td>"
            f"<td class='num'>{pct(f, n)} <span class='muted'>{f}/{n}</span></td>{caps}</tr>"
        )
        c, f, n = r["stress"]
        lbs.append(f"<tr><td class='fw'>{html.escape(k)}</td><td class='num'>{pct(c, n)} <span class='muted'>{c}/{n}</span></td>"
                   f"<td class='num'>{pct(f, n)} <span class='muted'>{f}/{n}</span></td></tr>")
    cap_th = "".join(f"<th class='num'>{html.escape(c)}</th>" for c in t["capabilities"])
    sc, _, sn = t["stable"]
    rc, _, rn = t["stress"]

    idx = {(r["adapter"], r["scenario"], r["mode"]): r for r in res}
    mx = []
    for sid, meta in data["scenarios"].items():
        cells = []
        for k in order:
            parts = []
            for m in ("invoke", "stream"):
                r = idx.get((k, sid, m))
                if r is None:
                    parts.append('<span class="pill">?</span>')
                else:
                    parts.append(pill(r["complete"], r["faithful"], m, r["failures"] + r["fidelity_failures"]))
            cells.append(f"<td><div class='cell'>{''.join(parts)}</div></td>")
        mx.append(
            f"<tr><td><span class='cat'>{html.escape(meta['category'])}</span><br>"
            f"<span class='mono'>{sid}</span> {html.escape(meta['title'])}</td>{''.join(cells)}</tr>"
        )

    fails = []
    for k in order:
        items = []
        for r in res:
            if r["adapter"] != k:
                continue
            for f in r["failures"]:
                items.append(f"<li><span class='mono'>{r['scenario']} {r['mode']}</span> completeness: {html.escape(f)}</li>")
            for f in r["fidelity_failures"]:
                items.append(f"<li><span class='mono'>{r['scenario']} {r['mode']}</span> fidelity: {html.escape(f)}</li>")
        if items:
            fails.append(f"<details><summary class='fw'>{html.escape(k)} ({len(items)})</summary><ul>{''.join(items)}</ul></details>")

    versions = "".join(
        f"<div><span class='fw'>{html.escape(k)}</span>: {html.escape(v['version'])}</div>" for k, v in data["adapters"].items()
    )
    head_cols = "".join(f"<th class='fw'>{html.escape(k)}</th>" for k in order)

    return f"""<title>TraceGap Leaderboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Schibsted+Grotesk:wght@400;500;600;700&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header>
  <div class="eyebrow">TraceGap v{html.escape(data['version'])} · the agent tracing correctness benchmark</div>
  <h1>Does your agent framework record what actually happened?</h1>
  <p class="lede">TraceGap drives agent frameworks with scripted models through {n_scn} fault scenarios, then compares each framework's own trace with ground truth written by the tools themselves. No API keys, no network, deterministic results.</p>
  <div class="stats">
    <div class="stat"><b>{tot}</b><span>cases ({len(rows)} surfaces × {n_scn} scenarios × 2 modes)</span></div>
    <div class="stat"><b>{comp}</b><span>complete ({pct(comp, tot)})</span></div>
    <div class="stat"><b>{both}</b><span>complete and faithful ({pct(both, tot)})</span></div>
    <div class="stat"><b>{fully}</b><span>surfaces complete in every core case</span></div>
    <div class="stat"><b>{pct(sc, sn)}</b><span>Stable-tier cases complete ({sc}/{sn})</span></div>
    <div class="stat"><b>{pct(rc, rn)}</b><span>Stress-tier cases complete ({rc}/{rn})</span></div>
  </div>
</header>

<section>
  <h2>Leaderboard: Stable tier</h2>
  <p class="muted">Ranked on Stable cases from the core suite (22 hand-written scenarios) and the generated suite (200 seeded scenarios), each in invoke and stream mode. Stable verdicts were identical across repeated full runs, so a re-run gives the same score. Complete: every call present with an honest status, no phantoms or duplicates, runs neither mixed nor fragmented. Faithful: every captured argument, output and error message exact. Capability columns: complete Stable cases among the scenarios testing tool failures (S05–S06), cancellation (S17–S18), rejected calls (S08–S10) and nested agents (S22).</p>
  <div class="frame"><table>
    <thead><tr><th class="num">#</th><th>Framework / surface</th><th>Version</th><th class="num">Complete</th><th class="num">Faithful</th>{cap_th}</tr></thead>
    <tbody>{''.join(lb)}</tbody>
  </table></div>
</section>

<section>
  <h2>Stress tier</h2>
  <p class="muted">Scenarios where a tool raises inside a parallel batch. How frameworks treat the failing call's siblings can depend on scheduling, so these are reported separately and not used for ranking.</p>
  <div class="frame"><table>
    <thead><tr><th>Framework / surface</th><th class="num">Complete</th><th class="num">Faithful</th></tr></thead>
    <tbody>{''.join(lbs)}</tbody>
  </table></div>
</section>

<section>
  <h2>Core scenario matrix</h2>
  <div class="legend">
    <span><span class="pill p-ok">CF</span> complete and faithful</span>
    <span><span class="pill p-warn">C·</span> complete, detail lost</span>
    <span><span class="pill p-bad">··</span> incomplete</span>
    <span>Each cell: invoke mode, then stream mode. Hover a pill for the reason.</span>
  </div>
  <div class="frame"><table class="matrix">
    <thead><tr><th>Scenario</th>{head_cols}</tr></thead>
    <tbody>{''.join(mx)}</tbody>
  </table></div>
</section>

<section>
  <h2>Defects found, with fixes</h2>
  <p class="muted">Each fix has a regression test that fails before and passes after, and the TraceGap scenarios listed pass on the patched framework.</p>
  <div class="frame"><table>
    <thead><tr><th>Project</th><th>Defect</th><th>Scenarios</th></tr></thead>
    <tbody>
      <tr><td class="fw">OpenAI Agents SDK</td><td style="white-space:normal">A tool interrupted by run cancellation closes its function span with no error, so it reads as a success.</td><td class="fw">S17</td></tr>
      <tr><td class="fw">AutoGen</td><td style="white-space:normal"><code>run()</code> hangs after a <code>CancellationToken</code> cancel during a tool; the in-flight tool keeps running after the run task is cancelled; the cancelled tool's span is left unset.</td><td class="fw">S17</td></tr>
      <tr><td class="fw">Semantic Kernel</td><td style="white-space:normal">A cancelled function's <code>execute_tool</code> span is left unset (successful-looking).</td><td class="fw">S17</td></tr>
      <tr><td class="fw">Google ADK</td><td style="white-space:normal">A cancelled tool's span is left unset, including siblings ADK cancels after one parallel call fails.</td><td class="fw">S07, S17</td></tr>
      <tr><td class="fw">smolagents</td><td style="white-space:normal">A step's memory records no tool calls when any call in it fails; duplicate call ids are silently dropped.</td><td class="fw">S05–S07, S11</td></tr>
    </tbody>
  </table></div>
  <p class="muted">Shared cause of the cancellation spans: OpenTelemetry's <code>use_span</code> records only <code>Exception</code>, and <code>asyncio.CancelledError</code> is a <code>BaseException</code>.</p>
</section>

<section>
  <h2>Across releases</h2>
  <p>The core suite was run against 65 past releases, with each release's dependencies resolved as of its release date. Highlights:</p>
  <ul>
    <li>smolagents' memory loss arrived with parallel tool calls in 1.18.0; silent dropping of duplicate call ids in 1.20.0.</li>
    <li>The OpenAI Agents SDK started rejecting duplicate call ids in 0.20.0 and redacting tool errors from spans in 0.23.</li>
    <li>Pydantic AI's OpenTelemetry spans started showing rejected calls in 2.30.0.</li>
  </ul>
  <p class="muted">Full history: <code>results/HISTORY.md</code> in the repository.</p>
</section>

<section>
  <h2>Every failure</h2>
  <div>{''.join(fails)}</div>
</section>

<footer>
  <div>Generated {html.escape(data['generated_at'])} · Python {html.escape(data['python'])} · core verdicts identical across four full runs.</div>
  {versions}
</footer>
</div>
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("results", nargs="?", default="results/results.json")
    p.add_argument("--generated", default="results/generated/results.json")
    p.add_argument("--out", default="site/index.html")
    p.add_argument("--standalone", action="store_true")
    a = p.parse_args()
    gen = json.loads(Path(a.generated).read_text()) if a.generated and Path(a.generated).exists() else None
    body = render(json.loads(Path(a.results).read_text()), gen)
    if a.standalone:
        body = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f"</head><body>{body}</body></html>")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(body)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

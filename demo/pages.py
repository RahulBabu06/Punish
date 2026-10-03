"""Server-rendered HTML for the gallery, mode comparison, dashboard and story pages (no external JS/CSS)."""

from __future__ import annotations

import html
import json
from urllib.parse import quote, urlencode

from demo.catalog import MODE_BLURB, MODE_SHORT, MODES

HACK_COLORS = {"suspicious_access": "#ff4d5e", "fabricated_verification": "#ff8a3d", "trace_claim_mismatch": "#ff5fd2",
               "rationalization": "#ffd23f", "fabricated_source": "#ff7a90", "methodological_drift": "#5fb4ff"}
SERIES_COLORS = ["#4da3ff", "#b48cff", "#ff8a3d", "#2ecc71", "#ffd23f", "#ff5fd2", "#5fe0d0", "#ff4d5e"]
MODE_COLORS = {"full_trace": "#b48cff", "report_only": "#4da3ff", "final_report": "#ff8a3d"}

esc = html.escape


def url(path: str, **params) -> str:
    items = []
    for k, v in params.items():
        if v is None or v is False:
            continue
        for x in v if isinstance(v, (list, tuple)) else [v]:
            items.append((k, "1" if x is True else str(x)))
    return path + ("?" + urlencode(items, quote_via=quote) if items else "")


def pct(x) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def num(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


CSS = r"""
:root{--bg:#0b0e14;--panel:#121722;--card:#151b27;--line:#232b3b;--text:#e6ebf5;--dim:#8a96ad;--faint:#5d687e;
--red:#ff4d5e;--green:#2ecc71;--blue:#4da3ff;--amber:#ffb347;--violet:#b48cff;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--blue)}code,.mono{font-family:var(--mono);font-size:.92em}
.wrap{padding:22px 32px 120px}
nav.top{display:flex;align-items:center;gap:20px;padding:12px 32px;border-bottom:1px solid var(--line);background:#0d1119;position:sticky;top:0;z-index:5}
.logo{font-weight:900;letter-spacing:.18em;background:var(--red);color:#fff;padding:6px 12px;border-radius:7px;text-decoration:none}
nav.top a.tab{color:var(--dim);text-decoration:none;font-weight:600;padding:6px 2px;border-bottom:2px solid transparent}
nav.top a.tab:hover{color:var(--text)}nav.top a.tab.on{color:var(--text);border-bottom-color:var(--red)}
nav.top .right{margin-left:auto;color:var(--faint);font-size:14px}
h1{margin:0 0 4px;font-size:26px}h2{font-size:19px;margin:30px 0 10px}h3{font-size:16px;margin:0 0 6px}
.sub{color:var(--dim);font-size:14px}.err{color:var(--red);font-size:20px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.06em;background:#0f141e}
td.n,th.n{text-align:right;font-family:var(--mono)}
tr:hover td{background:#161d2b}
.btn{display:inline-block;margin:0 0 0 6px;padding:5px 11px;border:1px solid var(--line);border-radius:7px;color:var(--text);text-decoration:none;font-size:14px;background:#182031;white-space:nowrap}
.btn:hover{border-color:var(--blue)}.btn.primary{background:var(--blue);color:#06101f;border-color:var(--blue);font-weight:700}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;font-weight:700;letter-spacing:.03em;border:1px solid var(--line);color:var(--dim);white-space:nowrap}
.pill.red{color:var(--red);border-color:var(--red)}.pill.green{color:var(--green);border-color:var(--green)}
.pill.blue{color:var(--blue);border-color:var(--blue)}.pill.violet{color:var(--violet);border-color:var(--violet)}.pill.amber{color:var(--amber);border-color:var(--amber)}
.pill.solid-red{background:var(--red);color:#fff;border-color:var(--red)}.pill.solid-green{background:#1e9e57;color:#fff;border-color:#1e9e57}
.vb{display:inline-flex;gap:4px;align-items:center;font-family:var(--mono);font-size:12px;padding:1px 7px;border-radius:6px;border:1px solid var(--line);color:var(--faint);margin-right:3px;white-space:nowrap}
.vb.hack{background:rgba(255,77,94,.16);border-color:rgba(255,77,94,.7);color:#ffb3bb}.vb.clean{background:rgba(46,204,113,.12);border-color:rgba(46,204,113,.6);color:#9be8bd}
.vb.wrong{outline:2px dashed var(--amber);outline-offset:1px}
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:14px 0 14px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.filters label{display:flex;flex-direction:column;font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;gap:4px}
select,input[type=search]{background:#0c1018;color:var(--text);border:1px solid var(--line);border-radius:7px;padding:6px 8px;font-size:14px;min-width:150px}
.count{margin-left:auto;color:var(--dim);font-family:var(--mono)}
.legend{color:var(--faint);font-size:13px;margin-top:10px}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:150px}
.stat b{display:block;font-size:28px;font-family:var(--mono)}.stats{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0}
.chart{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:16px}
.chart svg{width:100%;height:auto;display:block}
.chart .t{font-weight:700;margin-bottom:4px}
/* story bar */
#storybar{position:fixed;left:0;right:0;bottom:0;z-index:50;background:rgba(13,17,25,.97);border-top:2px solid var(--red);padding:12px 26px 14px;display:flex;gap:18px;align-items:center;box-shadow:0 -10px 30px rgba(0,0,0,.5)}
#storybar .st{font-weight:800;font-size:19px;white-space:nowrap}#storybar .sc{color:#d5dceb;font-size:17px;flex:1}
#storybar .sn{font-family:var(--mono);color:var(--dim);white-space:nowrap}
#storybar button{background:#182031;color:var(--text);border:1px solid var(--line);border-radius:7px;padding:6px 11px;font-size:15px;cursor:pointer}
#storybar .prog{position:absolute;left:0;top:-2px;height:2px;background:#fff;width:0}
"""


def nav(active: str) -> str:
    tabs = [("gallery", "/", "Gallery"), ("dashboard", "/dashboard", "Results"), ("story", "/story", "Story"),
            ("view", "/view", "Live view")]
    links = "".join(f'<a class="tab{" on" if k == active else ""}" href="{h}">{t}</a>' for k, h, t in tabs)
    return (f'<nav class="top"><a class="logo" href="/">PUNISH</a>{links}'
            '<span class="right">Scientific Integrity Auditor</span></nav>')


def shell(title: str, body: str, active: str = "", head: str = "", script: str = "") -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>Punish · {esc(title)}</title>'
            f'<link rel="icon" href="/favicon.ico"><style>{CSS}{head}</style></head><body>{nav(active)}'
            f'<div class="wrap">{body}</div><script>"use strict";{script}</script>{STORY_JS}</body></html>')


# ---------------------------------------------------------------------------------------------------- gallery
def gt_badges(it: dict) -> str:
    out = []
    lab = it.get("labeller")
    if lab is None:
        out.append('<span class="pill" title="no labeller result">labeller –</span>')
    else:
        src = " (computed with tasks.registry.label)" if it.get("labeller_source") == "computed" else ""
        out.append(f'<span class="pill {"solid-red" if lab else "green"}" title="deterministic labeller{src}">'
                   f'labeller {"HACK" if lab else "clean"}</span>')
    j = it.get("judge")
    if j is None:
        out.append('<span class="pill" title="no privileged-judge label">judge –</span>')
    else:
        tip = f'{j.get("model") or "judge"} · severity {j.get("severity")}: {j.get("rationale", "")}'
        out.append(f'<span class="pill {"solid-red" if j["hacked"] else "green"}" title="{esc(tip[:900])}">'
                   f'judge {"HACK" if j["hacked"] else "clean"}</span>')
    return " ".join(out)


def verdict_badge(mode: str, v: dict | None, truth: bool | None, label: str | None = None) -> str:
    short = label or MODE_SHORT[mode]
    if v is None:
        return f'<span class="vb" title="{mode}: no verdict">{short} –</span>'
    hack = v.get("hack_detected") is True
    conf = v.get("confidence")
    conf_s = f"{float(conf):.0%}" if isinstance(conf, (int, float)) else "?"
    wrong = truth is not None and hack != truth
    tip = f'{mode}: {"HACK" if hack else "clean"} (confidence {conf_s})' + (
        f' · {", ".join(v.get("hack_types") or [])}' if hack else "") + (
        " · disagrees with ground truth (either)" if wrong else "")
    return (f'<span class="vb {"hack" if hack else "clean"}{" wrong" if wrong else ""}" title="{esc(tip)}">'
            f'{short} {"⚑" if hack else "✓"} {conf_s}</span>')


def gallery_page(items: list[dict], default_key: str | None = None, live: bool = False) -> str:
    fields = [("experiment", "Experiment"), ("task_id", "Task"), ("agent_config", "Agent config"),
              ("subject_model", "Subject model")]
    opts = {f: sorted({str(it.get(f) or "?") for it in items}) for f, _ in fields}
    selects = "".join(
        f'<label>{lbl}<select data-f="{f}"><option value="">all ({len(opts[f])})</option>'
        + "".join(f'<option>{esc(o)}</option>' for o in opts[f]) + "</select></label>" for f, lbl in fields)
    selects += ('<label>Ground truth<select data-f="truth"><option value="">any</option><option value="hack">hacked '
                '(either)</option><option value="clean">clean</option><option value="split">labeller ≠ judge</option>'
                '</select></label><label>Auditor<select data-f="outcome"><option value="">any</option>'
                '<option value="wrong">any mode wrong</option><option value="fp">false positive (full_trace)</option>'
                '<option value="fn">missed (full_trace)</option><option value="fr_miss">caught by full_trace, '
                'missed by final_report</option></select></label>'
                '<label>Search<input type="search" data-f="q" placeholder="trajectory id"></label>')
    rows = []
    for it in items:
        key = it["key"]
        v = it["verdicts"]
        truth = it.get("hacked_either")
        ft = (v.get("full_trace") or {}).get("hack_detected")
        fr = (v.get("final_report") or {}).get("hack_detected")
        outcome = []
        if truth is not None and any((x or {}).get("hack_detected") is not None and x["hack_detected"] != truth
                                     for x in v.values()):
            outcome.append("wrong")
        if truth is False and ft is True:
            outcome.append("fp")
        if truth is True and ft is False:
            outcome.append("fn")
        if truth is True and ft is True and fr is False:
            outcome.append("fr_miss")
        j = it.get("judge")
        split = j is not None and it.get("labeller") is not None and j["hacked"] != it["labeller"]
        tcls = ("hack" if truth else "clean") if truth is not None else ""
        data = {f: str(it.get(f) or "?") for f, _ in fields}
        attrs = " ".join(f'data-{k}="{esc(val)}"' for k, val in data.items())
        attrs += f' data-truth="{tcls}{" split" if split else ""}" data-outcome="{" ".join(outcome)}" data-q="{esc(key.lower())}"'
        badges = "".join(verdict_badge(m, v.get(m), truth) for m in MODES)
        for name, rv in (it.get("reaudits") or {}).items():
            badges += "<br>" + "".join(verdict_badge(m, rv.get(m), truth, f"{name[:14]}·{MODE_SHORT[m]}")
                                       for m in MODES if m in rv)
        status = "" if it["finished"] else f'<span class="pill amber">{"in progress" if it["exists"] else "waiting"}</span>'
        links = [f'<a class="btn primary" href="{esc(url("/view", traj=key, live=0, progressive=1))}">Replay</a>',
                 f'<a class="btn" href="{esc(url("/compare", traj=key))}">Compare modes</a>']
        if not it["finished"]:
            links.append(f'<a class="btn" href="{esc(url("/view", traj=key, live=1))}">Live tail</a>')
        rows.append(
            f'<tr {attrs}><td><a href="{esc(url("/compare", traj=key))}"><code>{esc(it["trajectory_id"])}</code></a> {status}'
            f'<div class="sub">{esc(it["experiment"])} · {it["lines"]} lines</div></td>'
            f'<td>{esc(str(it.get("task_id") or "?"))}</td><td><span class="pill {"green" if it.get("agent_config") == "honest" else "red"}">'
            f'{esc(str(it.get("agent_config") or "?"))}</span></td><td class="mono">{esc(str(it.get("subject_model") or "?"))}</td>'
            f'<td>{gt_badges(it)}</td><td>{badges}</td><td style="text-align:right">{"".join(links)}</td></tr>')
    default = ""
    if default_key:
        default = (f'<a class="btn primary" style="margin-left:auto" href="/view">'
                   f'{"Live tail" if live else "Open"} <code>{esc(default_key)}</code> &rarr;</a>')
    body = f"""
<div style="display:flex;align-items:end;gap:16px"><div><h1>Trajectory gallery</h1>
<div class="sub">Every trajectory under <code>results/*/trajectories/</code> (and <code>fixtures/</code>). Ground truth: deterministic
labeller and privileged judge. Verdicts: <b>FT</b> full_trace · <b>RO</b> report_only · <b>FR</b> final_report.</div></div>{default}</div>
<div class="filters" id="filters">{selects}<span class="count" id="count"></span></div>
<table id="gallery"><thead><tr><th>Trajectory</th><th>Task</th><th>Config</th><th>Subject model</th><th>Ground truth</th>
<th>Auditor verdicts</th><th></th></tr></thead><tbody>{"".join(rows) or '<tr><td colspan=7 class="sub">No trajectories found.</td></tr>'}</tbody></table>
<div class="legend">⚑ = flagged as hacking, ✓ = clean, % = auditor confidence that the trajectory contains hacking. A dashed amber
outline means the verdict disagrees with the ground truth (hacked if the labeller or the judge says so). Hover a badge for details.</div>"""
    script = r"""
const sels = [...document.querySelectorAll("#filters [data-f]")];
const rows = [...document.querySelectorAll("#gallery tbody tr[data-q]")];
function apply(){
  const f = Object.fromEntries(sels.map(s => [s.dataset.f, s.value.trim().toLowerCase()]));
  let n = 0;
  for (const r of rows){
    let ok = true;
    for (const k of ["experiment","task_id","agent_config","subject_model"]) if (f[k] && r.dataset[k].toLowerCase() !== f[k]) ok = false;
    if (f.truth && !(r.dataset.truth || "").split(" ").includes(f.truth)) ok = false;
    if (f.outcome && !(r.dataset.outcome || "").split(" ").includes(f.outcome)) ok = false;
    if (f.q && !r.dataset.q.includes(f.q)) ok = false;
    r.hidden = !ok; if (ok) n++;
  }
  document.getElementById("count").textContent = n + " / " + rows.length + " trajectories";
  const p = new URLSearchParams(); sels.forEach(s => { if (s.value) p.set(s.dataset.f, s.value); });
  history.replaceState(null, "", p.toString() ? "?" + p : location.pathname);
}
const init = new URLSearchParams(location.search);
sels.forEach(s => { if (init.get(s.dataset.f)) s.value = init.get(s.dataset.f); s.addEventListener("input", apply); });
apply();
"""
    return shell("Gallery", body, "gallery", script=script)


# ---------------------------------------------------------------------------------------------------- compare
COMPARE_CSS = r"""
.vcard{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;border-top:4px solid var(--mc)}
.vcard .mh{display:flex;align-items:center;gap:10px}.vcard .mh b{font-family:var(--mono);font-size:17px;color:var(--mc)}
.vcard .saw{margin-left:auto;font-family:var(--mono);font-size:13px;color:var(--dim)}
.verd{margin:10px 0;padding:10px 12px;border-radius:10px;text-align:center;font-weight:900;font-size:26px;letter-spacing:.05em;border:2px solid var(--line)}
.verd.hack{border-color:var(--red);background:radial-gradient(circle at 50% 0,rgba(255,77,94,.35),rgba(255,77,94,.06) 70%)}
.verd.clean{border-color:var(--green);color:var(--green);background:rgba(46,204,113,.08)}.verd.none{color:var(--faint)}
.verd small{display:block;font-size:13px;font-weight:600;letter-spacing:0;color:var(--dim);font-family:var(--mono)}
.verd .ok{color:var(--green)}.verd .bad{color:var(--amber)}
.bar{height:8px;border-radius:99px;background:#202838;overflow:hidden;margin:4px 0 10px}.bar i{display:block;height:100%}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}.chip{font-size:12px;font-weight:700;padding:2px 9px;border-radius:99px;border:1px solid;font-family:var(--mono)}
.ev{border:1px solid var(--line);border-left:4px solid var(--red);border-radius:9px;padding:7px 10px;margin:0 0 8px;cursor:pointer;font-size:14px;background:var(--card)}
.ev:hover{border-color:var(--red)}.ev .eh{display:flex;gap:8px;align-items:center;margin-bottom:2px;flex-wrap:wrap}.ev .lr{margin-left:auto;font-family:var(--mono);color:var(--red);font-weight:700}
.tag{font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:1px 7px;border-radius:5px}
.tag.cot{background:rgba(180,140,255,.18);color:var(--violet)}.tag.trace{background:rgba(255,138,61,.16);color:#ffb37a}
.notes{color:var(--dim);font-size:13px;white-space:pre-wrap;max-height:9em;overflow:auto;border-top:1px solid var(--line);padding-top:8px}
.grid{display:grid;grid-template-columns:56px minmax(0,1fr) repeat(3,150px);gap:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-top:12px}
.grid>div{padding:8px 10px;border-bottom:1px solid var(--line);min-width:0}
.grid .gh{position:sticky;top:57px;z-index:2;background:#0f141e;color:var(--dim);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.grid .ln{font-family:var(--mono);color:var(--faint);text-align:right}
.row-cot .ln,.row-cot.evt{box-shadow:inset 3px 0 0 var(--violet)}
.evt .tt{font-family:var(--mono);font-size:14px}.evt .tt .k{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin-right:8px}
.evt .tx{white-space:pre-wrap;word-break:break-word;color:#cfd8e6;font-size:13px;max-height:7.5em;overflow:hidden;font-family:var(--mono);margin-top:3px}
.evt.open .tx{max-height:none}
.evt .cot{white-space:pre-wrap;font-style:italic;color:#d6c8f5;background:rgba(180,140,255,.08);border-left:3px solid var(--violet);padding:5px 9px;border-radius:0 7px 7px 0;font-size:14px;margin:4px 0;max-height:9em;overflow:hidden}
.evt.open .cot{max-height:none}
.evt .cot .lbl{display:block;font-style:normal;font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--violet)}
.cell{font-size:12px;display:flex;flex-direction:column;gap:3px;align-items:flex-start}
.cell.hidden{background:repeating-linear-gradient(135deg,transparent 0 6px,rgba(255,255,255,.035) 6px 12px);color:var(--faint)}
.cell .seen{color:var(--faint)}.cell .part{color:var(--violet)}
.cell .cite{font-family:var(--mono);font-weight:700;padding:1px 7px;border-radius:5px;color:#160409;cursor:pointer}
.focus{background:rgba(255,77,94,.13)!important}
.judge{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:12px 0;font-size:14px;color:#cfd8e6}
.headline{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0 2px}
"""


def _verdict_card(mode: str, v: dict | None, info: dict, data: dict) -> str:
    total = len(data["lines"])
    saw = data["visible_counts"][mode]
    truth = info.get("hacked_either")
    head = (f'<div class="mh"><b>{mode}</b><span class="saw" title="lines shown to the auditor">sees {saw}/{total} lines</span>'
            f'</div><div class="sub">{esc(MODE_BLURB[mode])}</div>')
    if v is None:
        return (f'<div class="vcard" style="--mc:{MODE_COLORS[mode]}">{head}<div class="verd none">NO VERDICT'
                '<small>not audited in this mode</small></div></div>')
    hack = v.get("hack_detected") is True
    conf = v.get("confidence") if isinstance(v.get("confidence"), (int, float)) else 0
    right = "" if truth is None else (
        '<span class="ok">✓ matches ground truth</span>' if hack == truth else
        f'<span class="bad">✗ {"false positive" if hack else "missed the hack"}</span>')
    chips = "".join(f'<span class="chip" style="color:{HACK_COLORS.get(t, "#ff4d5e")};border-color:{HACK_COLORS.get(t, "#ff4d5e")}">'
                    f'{esc(t)}</span>' for t in v.get("hack_types") or [])
    evs = []
    for i, e in enumerate(v.get("evidence") or []):
        r = e.get("line_range") or [0, 0]
        c = HACK_COLORS.get(e.get("hack_type"), "#ff4d5e")
        tags = ""
        if e.get("cites_reasoning"):
            tags += '<span class="tag cot" title="cites a line whose private reasoning only full_trace sees">private reasoning</span>'
        if e.get("only_full_trace_visible") or (mode != "final_report" and all(
                data["lines"][k - 1]["visibility"]["final_report"] == "hidden"
                for k in range(max(int(r[0]), 1), min(int(r[-1]), total) + 1))):
            tags += '<span class="tag trace" title="none of these lines are visible to final_report">trace only</span>'
        rng = f"L{r[0]}" if r[0] == r[-1] else f"L{r[0]}–{r[-1]}"
        evs.append(f'<div class="ev" style="border-left-color:{c}" data-a="{r[0]}" data-b="{r[-1]}" data-mode="{mode}">'
                   f'<div class="eh"><span class="chip" style="color:{c};border-color:{c}">{esc(str(e.get("hack_type")))}</span>'
                   f'{tags}<span class="lr">{rng}</span></div>{esc(e.get("explanation") or "")}</div>')
    notes = f'<div class="notes">{esc(v.get("auditor_notes") or "")}</div>' if v.get("auditor_notes") else ""
    return (f'<div class="vcard" style="--mc:{MODE_COLORS[mode]}">{head}'
            f'<div class="verd {"hack" if hack else "clean"}">{"HACK DETECTED" if hack else "CLEAN"}'
            f'<small>confidence {conf:.0%} {right}</small></div>'
            f'<div class="bar"><i style="width:{conf * 100:.0f}%;background:{"var(--red)" if hack else "var(--green)"}"></i></div>'
            f'<div class="chips">{chips}</div>{"".join(evs)}{notes}</div>')


def compare_page(data: dict) -> str:
    info = data["info"]
    key = info["key"]
    cards = "".join(_verdict_card(m, data["verdicts"].get(m), info, data) for m in MODES)
    grid = ['<div class="gh">line</div><div class="gh">event · <span style="color:var(--violet)">purple = private '
            'reasoning, visible only to full_trace</span></div>'
            + "".join(f'<div class="gh" style="color:{MODE_COLORS[m]}">{m}</div>' for m in MODES)]
    for ln in data["lines"]:
        n = ln["line"]
        cot = ln["visibility"]["report_only"] == "partial"
        rc = " row-cot" if cot else ""
        body = f'<div class="tt"><span class="k">{esc(ln["kind"])}</span>{esc(ln["title"])}</div>'
        if cot:
            body += (f'<div class="cot"><span class="lbl">private reasoning · only full_trace sees this</span>'
                     f'{esc(ln["reasoning"][:4000])}</div>')
        if ln["text"]:
            body += f'<div class="tx">{esc(ln["text"][:6000])}</div>'
        cells = []
        for m in MODES:
            vis = ln["visibility"][m]
            parts = []
            for c in ln["cited"].get(m, []):
                col = HACK_COLORS.get(c["hack_type"], "#ff4d5e")
                parts.append(f'<span class="cite" style="background:{col}" data-mode="{m}" data-i="{c["index"]}" '
                             f'title="evidence #{c["index"] + 1}">#{c["index"] + 1} {esc(str(c["hack_type"]))}</span>')
            label = {"full": '<span class="seen">seen</span>', "partial": '<span class="part">seen · no reasoning</span>',
                     "hidden": "not shown"}[vis]
            cells.append(f'<div class="cell {vis}{rc}">{label}{"".join(parts)}</div>')
        grid.append(f'<div class="ln{rc}" id="L{n}">L{n}</div><div class="evt{rc}" data-line="{n}">{body}</div>{"".join(cells)}')
    judge = ""
    if info.get("judge"):
        j = info["judge"]
        judge = (f'<div class="judge"><b>Privileged judge</b> ({esc(str(j.get("model") or ""))}, sees the planted exploit): '
                 f'<b style="color:{"var(--red)" if j["hacked"] else "var(--green)"}">{"HACKED" if j["hacked"] else "clean"}</b>'
                 f' · severity {esc(str(j.get("severity")))} — {esc(j.get("rationale") or "")}</div>')
    n_cot = len(data["reasoning_lines"])
    cot_note = (f'{n_cot} assistant turn(s) carry private reasoning that report_only and final_report never see.'
                if n_cot else 'No captured private reasoning in this trajectory (probe_v1 predates interleaved thinking).')
    body = f"""
<div class="headline"><h1 style="margin-right:8px">Mode comparison</h1><code>{esc(info["trajectory_id"])}</code>
<span class="pill blue">{esc(str(info.get("task_id")))}</span><span class="pill red">{esc(str(info.get("agent_config")))}</span>
<span class="pill">{esc(str(info.get("subject_model")))}</span><span class="pill">{esc(info["experiment"])}</span>{gt_badges(info)}
<span style="margin-left:auto"><a class="btn primary" href="{esc(url("/view", traj=key, live=0, progressive=1))}">Replay</a>
{"".join(f'<a class="btn" href="{esc(url("/view", traj=key, live=0, progressive=1, auditor_mode=m))}">{MODE_SHORT[m]}</a>' for m in MODES)}</span></div>
<div class="sub">Same trajectory, three auditors with different access. {esc(cot_note)} Click an evidence item to jump to its lines.</div>
{judge}<div class="cards">{cards}</div>
<div class="grid" id="grid">{"".join(grid)}</div>"""
    script = r"""
function focus(a, b, mode){
  document.querySelectorAll(".focus").forEach(e => e.classList.remove("focus"));
  for (let l = a; l <= b; l++){ const el = document.querySelector(`.evt[data-line="${l}"]`); if (el) el.classList.add("focus", "open"); const ln = document.getElementById("L" + l); if (ln) ln.classList.add("focus"); }
  const first = document.getElementById("L" + a); if (first) first.scrollIntoView({behavior:"smooth", block:"center"});
}
document.querySelectorAll(".ev").forEach(e => e.addEventListener("click", () => focus(+e.dataset.a, +e.dataset.b, e.dataset.mode)));
document.querySelectorAll(".cite").forEach(c => c.addEventListener("click", () => {
  const ev = document.querySelectorAll(`.ev[data-mode="${c.dataset.mode}"]`)[+c.dataset.i];
  if (ev){ ev.scrollIntoView({behavior:"smooth", block:"center"}); ev.style.boxShadow = "0 0 0 2px var(--red)"; setTimeout(() => ev.style.boxShadow = "", 1500); }
}));
document.querySelectorAll(".evt").forEach(e => e.addEventListener("dblclick", () => e.classList.toggle("open")));
"""
    return shell(f"Compare {info['trajectory_id']}", body, "gallery", head=COMPARE_CSS, script=script)


# ---------------------------------------------------------------------------------------------------- dashboard
def bar_chart(title: str, groups: list[tuple[str, list[tuple[str, float | None]]]], series: list[str],
              colors: dict[str, str] | None = None, ymax: float = 1.0, fmt=pct, width: int = 640) -> str:
    """Grouped vertical bar chart as inline SVG. groups = [(group_label, [(series_name, value|None), ...])]."""
    colors = colors or {s: SERIES_COLORS[i % len(SERIES_COLORS)] for i, s in enumerate(series)}
    h, top, bottom, left, right = 300, 34, 62, 44, 10
    plot_w, plot_h = width - left - right, h - top - bottom
    n = max(len(groups), 1)
    gw = plot_w / n
    bw = max(4.0, min(42.0, (gw - 14) / max(len(series), 1)))
    out = [f'<svg viewBox="0 0 {width} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(title)}" '
           f'font-family="system-ui,sans-serif">']
    for i, s in enumerate(series):  # legend
        x = left + i * 128
        out.append(f'<rect x="{x}" y="6" width="12" height="12" rx="2" fill="{colors[s]}"/>'
                   f'<text x="{x + 17}" y="16" font-size="12" fill="#c3cbe0">{esc(s)}</text>')
    for k in range(5):
        y = top + plot_h - plot_h * k / 4
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#232b3b"/>'
                   f'<text x="{left - 6}" y="{y + 4:.1f}" font-size="11" fill="#8a96ad" text-anchor="end">'
                   f'{fmt(ymax * k / 4)}</text>')
    for gi, (glabel, vals) in enumerate(groups):
        gx = left + gi * gw + (gw - bw * len(series)) / 2
        lookup = dict(vals)
        for si, s in enumerate(series):
            v = lookup.get(s)
            x = gx + si * bw
            if v is None:
                out.append(f'<text x="{x + bw / 2:.1f}" y="{top + plot_h - 4}" font-size="10" fill="#5d687e" '
                           f'text-anchor="middle">n/a</text>')
                continue
            bh = plot_h * min(max(v / ymax, 0), 1)
            y = top + plot_h - bh
            out.append(f'<rect x="{x + 1:.1f}" y="{y:.1f}" width="{bw - 2:.1f}" height="{bh:.1f}" rx="2" fill="{colors[s]}">'
                       f'<title>{esc(glabel)} · {esc(s)}: {fmt(v)}</title></rect>')
            if bw >= 22:
                out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 4:.1f}" font-size="11" fill="#e6ebf5" '
                           f'text-anchor="middle">{fmt(v)}</text>')
        lines = glabel.split("\n")
        for li, part in enumerate(lines):
            out.append(f'<text x="{left + gi * gw + gw / 2:.1f}" y="{top + plot_h + 18 + li * 14}" font-size="12" '
                       f'fill="{"#e6ebf5" if li == 0 else "#8a96ad"}" text-anchor="middle">{esc(part)}</text>')
    out.append("</svg>")
    return f'<div class="chart"><div class="t">{esc(title)}</div>{"".join(out)}</div>'


def _short_model(m: str) -> str:
    return str(m).replace("claude-", "").replace("-20251001", "").replace("-20250929", "")


def _table(headers: list[str], rows: list[list], numeric_from: int = 1) -> str:
    th = "".join(f'<th class="{"n" if i >= numeric_from else ""}">{esc(h)}</th>' for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f'<td class="{"n" if i >= numeric_from else ""}">{c}</td>' for i, c in enumerate(r))
                   + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body or '<tr><td class=sub>no data</td></tr>'}</tbody></table>"


def dashboard_page(d: dict) -> str:
    label = d["label"]
    exp_boxes = "".join(
        f'<label style="flex-direction:row;align-items:center;gap:6px;text-transform:none;font-size:14px;color:var(--text)">'
        f'<input type="checkbox" name="exp" value="{esc(e)}"{" checked" if e in d["selected"] else ""}> {esc(e)}</label>'
        for e in d["experiments"])
    label_sel = "".join(f'<option{" selected" if l == label else ""}>{l}</option>' for l in d["labels"])
    form = (f'<form class="filters" method="get" action="/dashboard">{exp_boxes}<label>Ground truth<select name="label" '
            f'onchange="this.form.submit()">{label_sel}</select></label><button class="btn primary">Update</button>'
            f'<span class="count">{d["n_trajectories"]} trajectories · {d["n_audits"]} audits</span></form>')
    if not d["experiments"]:
        return shell("Results", "<h1>Results</h1><p class=sub>No experiments with episodes/ under results/.</p>", "dashboard")

    primary = [r for r in d["auditor"] if r["auditor"] == "claude-sonnet-4-6"] or d["auditor"]
    best = max((r for r in primary if r["auroc"] is not None), key=lambda r: r["auroc"], default=None)
    hacked = sum(r[label] * r["n"] for r in d["hack_rate"] if r[label] is not None)
    stats = (f'<div class="stats"><div class="stat"><span class="sub">agent trajectories</span><b>{d["n_trajectories"]}</b></div>'
             f'<div class="stat"><span class="sub">auditor verdicts</span><b>{d["n_audits"]}</b></div>'
             f'<div class="stat"><span class="sub">hacked ({esc(label)})</span><b>{hacked:.0f}</b></div>')
    for r in primary:
        stats += (f'<div class="stat"><span class="sub">{esc(r["auditor_mode"])} recall / precision</span>'
                  f'<b style="color:{MODE_COLORS.get(r["auditor_mode"], "#fff")}">{pct(r["recall"])} / {pct(r["precision"])}</b></div>')
    if best:
        stats += f'<div class="stat"><span class="sub">best AUROC ({esc(best["auditor_mode"])})</span><b>{num(best["auroc"])}</b></div>'
    stats += "</div>"

    hr_groups = [(f'{r["agent_config"]}\n{_short_model(r["subject_model"])}',
                  [(l, r[l]) for l in ("labeller", "judge", "either")]) for r in
                 sorted(d["hack_rate"], key=lambda r: (["honest", "incentivized", "pressure", "covert"].index(r["agent_config"])
                                                       if r["agent_config"] in ("honest", "incentivized", "pressure", "covert") else 9,
                                                       r["subject_model"]))]
    c1 = bar_chart("Hack rate by agent config and subject model", hr_groups, ["labeller", "judge", "either"],
                   {"labeller": "#4da3ff", "judge": "#b48cff", "either": "#ff4d5e"}, width=max(640, 70 * len(hr_groups)))
    aud_groups = [(f'{r["auditor_mode"]}' + (f'\n{_short_model(r["auditor"])}' if len({x["auditor"] for x in d["auditor"]}) > 1 else ""),
                   [("precision", r["precision"]), ("recall", r["recall"]), ("AUROC", r["auroc"])]) for r in d["auditor"]]
    c2 = bar_chart(f"Auditor quality per mode (vs {label})", aud_groups, ["precision", "recall", "AUROC"],
                   {"precision": "#4da3ff", "recall": "#ff4d5e", "AUROC": "#2ecc71"}, fmt=num, width=max(640, 110 * len(aud_groups)))
    cfgs = sorted({r["agent_config"] for r in d["by_config"]})
    rc_groups = [(c, [(m, next((r["recall"] for r in d["by_config"] if r["agent_config"] == c and r["auditor_mode"] == m), None))
                      for m in MODES]) for c in cfgs]
    c3 = bar_chart(f"Auditor recall by agent config (vs {label}; all auditors)", rc_groups, list(MODES), MODE_COLORS)
    fp_groups = [(c, [(m, next((r["fpr"] for r in d["by_config"] if r["agent_config"] == c and r["auditor_mode"] == m), None))
                      for m in MODES]) for c in cfgs]
    c4 = bar_chart(f"False-positive rate by agent config (vs {label})", fp_groups, list(MODES), MODE_COLORS)

    t_hr = _table(["subject model", "agent config", "trajectories", "hack rate (labeller)", "hack rate (judge)", "hack rate (either)"],
                  [[esc(_short_model(r["subject_model"])), esc(r["agent_config"]), r["n"], pct(r["labeller"]), pct(r["judge"]),
                    pct(r["either"])] for r in d["hack_rate"]], numeric_from=2)
    t_aud = _table(["auditor", "mode", "n", "hacked", "TP", "FP", "FN", "TN", "precision", "recall", "F1", "FPR", "AUROC"],
                   [[esc(_short_model(r["auditor"])), f'<b style="color:{MODE_COLORS.get(r["auditor_mode"], "#fff")}">{esc(r["auditor_mode"])}</b>',
                     r["n"], r["pos"], r["tp"], r["fp"], r["fn"], r["tn"], num(r["precision"]), num(r["recall"]), num(r["f1"]),
                     num(r["fpr"]), num(r["auroc"])] for r in d["auditor"]], numeric_from=2)
    t_task = _table([f"task (hacked/total, {label})", *d["configs"]],
                    [[f'<a href="/?task_id={quote(t["task_id"])}">{esc(t["task_id"])}</a>',
                      *[("–" if t["cells"][c] is None else f'{t["cells"][c][0]}/{t["cells"][c][1]}') for c in d["configs"]]]
                     for t in d["per_task"]])
    a = d["agreement"]
    t_agree = _table(["judged trajectories", "both hacked", "labeller only", "judge only", "neither"],
                     [[a["n"], a["both"], a["labeller_only"], a["judge_only"], a["neither"]]], numeric_from=0)
    body = f"""<h1>Results</h1>
<div class="sub">Computed live from <code>eval.analyze.load_experiment</code> over <code>results/&lt;exp&gt;/episodes</code> (+ re-audits in
<code>reaudit_*/</code>). Ground truth <b>{esc(label)}</b>: labeller = deterministic planted-exploit rule; judge = privileged Opus judge; either = hacked if either says so.</div>
{form}{stats}<div class="charts">{c1}{c2}{c3}{c4}</div>
<h2>Hack rate by subject model and agent config</h2>{t_hr}
<h2>Auditor precision / recall / AUROC (vs {esc(label)})</h2>{t_aud}
<h2>Hacked trajectories per task</h2>{t_task}
<h2>Labeller vs judge agreement</h2>{t_agree}"""
    return shell("Results", body, "dashboard")


# ---------------------------------------------------------------------------------------------------- story
STORY_JS = r"""<script>
(function(){
  const step = new URLSearchParams(location.search).get("story");
  if (step === null) return;
  const i = parseInt(step, 10) || 0;
  fetch("/api/story").then(r => r.json()).then(steps => {
    const s = steps[i]; if (!s) return;
    const bar = document.createElement("div"); bar.id = "storybar";
    const esc = t => String(t || "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
    bar.innerHTML = `<div class="prog" id="sprog"></div><span class="sn">${i + 1}/${steps.length}</span><span class="st">${esc(s.title)}</span>
      <span class="sc">${esc(s.caption)}</span><button id="sprev" title="previous (←)">◀</button><button id="spause" title="pause (space)">❚❚</button><button id="snext" title="next (→)">▶</button>`;
    document.body.append(bar);
    document.body.style.paddingBottom = "90px";
    const go = k => { if (k >= 0 && k < steps.length) location.href = "/story?step=" + k; };
    let paused = false, timer = null, t0 = 0, dur = 0;
    const prog = document.getElementById("sprog");
    function tick(){ if (paused || !dur) return; const f = Math.min(1, (performance.now() - t0) / dur); prog.style.width = (f * 100) + "%";
      if (f >= 1){ if (i + 1 < steps.length) go(i + 1); else document.getElementById("snext").textContent = "end"; } else timer = requestAnimationFrame(tick); }
    function arm(seconds){ dur = Math.max(1, seconds) * 1000; t0 = performance.now(); cancelAnimationFrame(timer); tick(); }
    document.getElementById("sprev").onclick = () => go(i - 1);
    document.getElementById("snext").onclick = () => go(i + 1);
    const pause = () => { paused = !paused; document.getElementById("spause").textContent = paused ? "▶ resume" : "❚❚"; if (!paused && dur){ t0 = performance.now() - (parseFloat(prog.style.width) || 0) / 100 * dur; tick(); } };
    document.getElementById("spause").onclick = pause;
    document.addEventListener("keydown", e => { if (e.key === "ArrowRight") go(i + 1); else if (e.key === "ArrowLeft") go(i - 1); else if (e.key === " "){ e.preventDefault(); pause(); } });
    if (s.kind === "view"){
      if (window.__punishDone) arm(s.dwell); else document.addEventListener("punish:done", () => arm(s.dwell), {once: true});
    } else arm(s.dwell);
  });
})();
</script>"""

STORY_CSS = r"""<style>
#storybar{position:fixed;left:0;right:0;bottom:0;z-index:50;background:rgba(13,17,25,.97);border-top:2px solid #ff4d5e;padding:12px 26px 14px;display:flex;gap:18px;align-items:center;box-shadow:0 -10px 30px rgba(0,0,0,.5);font-family:system-ui,sans-serif;color:#e6ebf5}
#storybar .st{font-weight:800;font-size:19px;white-space:nowrap}#storybar .sc{color:#d5dceb;font-size:17px;flex:1}
#storybar .sn{font-family:ui-monospace,Menlo,monospace;color:#8a96ad;white-space:nowrap}
#storybar button{background:#182031;color:#e6ebf5;border:1px solid #232b3b;border-radius:7px;padding:6px 11px;font-size:15px;cursor:pointer}
#storybar .prog{position:absolute;left:0;top:-2px;height:2px;background:#fff;width:0}
body.has-story main{padding-bottom:80px}
</style>"""


def story_url(step: dict, index: int) -> str:
    if step["kind"] == "compare":
        return url("/compare", traj=step["traj"], story=index)
    if step["kind"] == "dashboard":
        return url("/dashboard", story=index, exp=step.get("experiments"), label=step.get("label"))
    return url("/view", traj=step["traj"], live=0, auditor_mode=step.get("auditor_mode"),
               progressive=1 if step.get("progressive") else 0, delay=step.get("delay"), audit=step.get("audit"), story=index)


def story_index_page(steps: list[dict]) -> str:
    rows = [[f'<a href="/story?step={i}">{i + 1}</a>', esc(s["title"]), esc(s["caption"]), esc(s["kind"]),
             f'<code>{esc(s.get("traj") or "")}</code>' + (f' · {esc(s.get("auditor_mode"))}' if s["kind"] == "view" else "")]
            for i, s in enumerate(steps)]
    body = (f'<div style="display:flex;align-items:end;gap:16px"><div><h1>Story mode</h1><div class="sub">Curated real examples '
            f'played in order with auto-advance. Keys: → next, ← previous, space pause.</div></div>'
            f'<a class="btn primary" style="margin-left:auto;font-size:18px;padding:10px 18px" href="/story?step=0">▶ Play</a></div>'
            f'<div style="height:14px"></div>{_table(["#", "title", "caption", "page", "trajectory"], rows, numeric_from=99)}')
    return shell("Story", body, "story")


def story_payload(steps: list[dict]) -> str:
    return json.dumps([{**s, "url": story_url(s, i)} for i, s in enumerate(steps)], ensure_ascii=False)

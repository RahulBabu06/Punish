"""Static, self-contained HTML export of the demo: story, curated gallery, mode comparisons, dashboard.

    python -m demo.export --out docs/demo.html [--max-gallery 120] [--story PLAYLIST_JSON]

Every page is rendered by the same code as the server (``demo.pages`` and ``demo.app.VIEWER_HTML``), then
gzip-compressed and base64-inlined. A small hash router shows each page in an iframe. The viewer's EventSource
is replaced by a replay of pre-computed ``demo.core.stream()`` events. The file needs no server, no network
and no external assets; open it via file:// in any current browser (it uses DecompressionStream).
"""

from __future__ import annotations

import argparse
import base64
import gzip
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from demo import benchmarks, catalog, pages
from demo.app import VIEWER_HTML
from demo.core import FIXTURES_DIR, RESULTS_DIR, ROOT, StreamOptions, stream

DEFAULT_OUT = ROOT / "docs" / "demo.html"
VIEW_KEYS = ("traj", "auditor_mode", "progressive", "audit")
TRUE = {"1", "true", "yes", "on"}
HREF_RE = re.compile(r'href="(/[^"]*)"')


def route_key(href: str, experiments: list[str], default_traj: str) -> str:
    """Canonical page id for an in-app link; mirrored by keyOf() in ROUTER_JS."""
    parts = urlsplit(html.unescape(href))
    path, q = parts.path or "/", parse_qs(parts.query, keep_blank_values=True)

    def get(k):
        return (q.get(k) or [""])[-1]

    if path == "/view":
        vals = {"traj": get("traj") or default_traj, "auditor_mode": get("auditor_mode") or "full_trace",
                "progressive": "1" if get("progressive").lower() in TRUE else "0", "audit": get("audit") or "file"}
        return "/view?" + "&".join(f"{k}={vals[k]}" for k in VIEW_KEYS)
    if path == "/compare":
        return "/compare?traj=" + get("traj")
    if path == "/dashboard":
        exps = sorted(set(q.get("exp") or []))
        if experiments and set(exps) >= set(experiments):
            exps = []
        return "/dashboard?exp=" + ",".join(exps) + "&label=" + (get("label") or "either")
    return path


def _bucket(it: dict) -> int:
    v, truth = it["verdicts"], it.get("hacked_either")
    ft = (v.get("full_trace") or {}).get("hack_detected")
    fr = (v.get("final_report") or {}).get("hack_detected")
    if truth and ft and fr is False:
        return 0  # caught with the trace, missed from the report alone
    if truth and ft:
        return 1
    if truth and ft is False:
        return 2  # missed hack
    if truth is False and ft:
        return 3  # false positive
    return 4


def curate(items: list[dict], must: set[str], cap: int) -> list[dict]:
    """``must`` keys plus up to ``cap`` interesting trajectories, spread over experiments, tasks and configs."""
    picked = {it["key"] for it in items if it["key"] in must}
    queues = []
    by_exp: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        if it["key"] not in picked and it["finished"] and it["experiment"] != "fixtures":
            by_exp[it["experiment"]].append(it)
    for its in by_exp.values():
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for it in sorted(its, key=lambda it: (_bucket(it), it["key"])):
            groups[(it["task_id"], it["agent_config"])].append(it)
        ranked = sorted(((rank, _bucket(it), it["key"], it) for g in groups.values() for rank, it in enumerate(g)),
                        key=lambda t: t[:3])
        queues.append([t[3] for t in ranked])
    budget = max(cap - len(picked), 0)
    while budget and any(queues):
        for q in queues:
            if q and budget:
                picked.add(q.pop(0)["key"])
                budget -= 1
    return [it for it in items if it["key"] in picked]


def view_events(key: str, results_dir: Path) -> list:
    q = parse_qs(urlsplit(key).query)
    path = Path(q["traj"][0])
    opts = StreamOptions(trajectory=path if path.is_absolute() else ROOT / path, delay=0, live=False,
                         auditor_mode=q["auditor_mode"][0], progressive=q["progressive"][0] == "1",
                         audit=q["audit"][0], results_dir=results_dir)
    return [[name, data] for name, data in stream(opts) if name != "ping"]


def pack(text: str) -> str:
    return base64.b64encode(gzip.compress(text.encode("utf-8"), 9, mtime=0)).decode("ascii")


BLOCK_RE = re.compile(r"<style>.*?</style>|<script>.*?</script>", re.S)


def shared_blocks(pages_: dict[str, str], min_len: int = 400) -> list[str]:
    """<style>/<script> blocks repeated across pages; stored once and re-inserted by the router."""
    seen: dict[str, int] = {}
    for page in pages_.values():
        for b in set(BLOCK_RE.findall(page)):
            if len(b) >= min_len:
                seen[b] = seen.get(b, 0) + 1
    return sorted((b for b, n in seen.items() if n > 1), key=len, reverse=True)


def dedupe(page: str, index: dict[str, int]) -> str:
    return BLOCK_RE.sub(lambda m: f"<!--punish:{index[m.group(0)]}-->" if m.group(0) in index else m.group(0), page)


def _strip(page: str) -> str:
    return re.sub(r'<link rel="icon"[^>]*>', "", page)


def build(results_dir: Path = RESULTS_DIR, fixtures_dir: Path | None = FIXTURES_DIR, story: str | None = None,
          max_gallery: int = 120, delay: float = 0.8) -> tuple[str, dict]:
    """Return (html, stats)."""
    items = catalog.gallery(results_dir, fixtures_dir)
    steps = catalog.load_story(story, results_dir)
    experiments = [e.name for e in catalog.analysis_experiments(results_dir)]
    default_traj = catalog.rel(fixtures_dir / "trajectories" / "example.jsonl") if fixtures_dir else ""
    must = {s["traj"] for s in steps if s.get("traj")} | {default_traj}
    chosen = curate(items, must, max_gallery)
    allowed = {it["key"] for it in chosen} | must
    key = lambda href: route_key(href, experiments, default_traj)  # noqa: E731

    note = (f"Static export: a curated {len(chosen)} of {len(items)} trajectories (hacks caught or missed, false "
            f"positives, every experiment). Run <code>python -m demo.app</code> to browse them all.")
    rendered: dict[str, str] = {"/": pages.gallery_page(chosen, note=note), "/story": pages.story_index_page(steps)}
    for it in chosen:
        rendered[key(pages.url("/compare", traj=it["key"]))] = pages.compare_page(
            catalog.compare(ROOT / it["key"], results_dir, fixtures_dir))
    bench = benchmarks.benchmarks(results_dir, fixtures_dir or FIXTURES_DIR)
    bench_keys = [k for k in benchmarks.trajectory_keys(bench) if k not in allowed]
    rendered["/benchmarks"] = benchmarks.benchmarks_page(bench)
    for k in bench_keys:
        rendered[key(pages.url("/compare", traj=k))] = pages.compare_page(catalog.compare(ROOT / k, results_dir, fixtures_dir))
    allowed |= set(bench_keys)
    for label in ("either", "labeller", "judge"):
        for sel in [[]] + [[e] for e in experiments]:
            k = key(pages.url("/dashboard", exp=sel, label=label))
            rendered[k] = pages.dashboard_page(catalog.dashboard(results_dir, sel or None, label))
    payload = json.loads(pages.story_payload(steps))

    views: dict[str, str] = {}
    lines: dict[str, list] = {}  # trajectory lines are shared by every mode's replay: stored once, referenced as ["@", i]
    hrefs = [s["url"] for s in payload] + ["/view"]
    for page in list(rendered.values()):
        hrefs += HREF_RE.findall(page)
    for href in hrefs:
        k = key(href)
        if k.startswith("/view?"):
            traj = parse_qs(urlsplit(k).query)["traj"][0]
            if traj in allowed and k not in views:
                shared = lines.setdefault(traj, [])
                index = {json.dumps(x, sort_keys=True): i for i, x in enumerate(shared)}
                events = []
                for name, data in view_events(k, results_dir):
                    if name in ("traj", "parse_error"):
                        sig = json.dumps([name, data], sort_keys=True)
                        if sig not in index:
                            index[sig] = len(shared)
                            shared.append([name, data])
                        events.append(["@", index[sig]])
                    else:
                        events.append([name, data])
                views[k] = json.dumps({"traj": traj, "events": events}, ensure_ascii=False).replace("</", "<\\/")
        elif k.startswith("/dashboard?") and k not in rendered:
            q = parse_qs(urlsplit(k).query, keep_blank_values=True)
            sel = [e for e in q["exp"][0].split(",") if e]
            rendered[k] = pages.dashboard_page(catalog.dashboard(results_dir, sel or None, q["label"][0]))

    missing = pages.shell("Not in this export", '<h1>Not included in the static export</h1><p class="sub">'
                          '<code id="missing-href"></code> is not part of this file. Run <code>python -m demo.app'
                          '</code> from the repo to browse every trajectory.</p><p><a href="/">Back to the gallery</a></p>')
    stripped = {k: _strip(v) for k, v in rendered.items()}
    blocks = shared_blocks(stripped)
    index = {b: i for i, b in enumerate(blocks)}
    data = {"pages": {k: pack(dedupe(v, index)) for k, v in stripped.items()}, "blocks": pack(json.dumps(blocks)), "views": {k: pack(v) for k, v in views.items()},
            "lines": {k: pack(json.dumps(v, ensure_ascii=False).replace("</", "<\\/")) for k, v in lines.items()},
            "viewer": pack(VIEWER_HTML.replace("</body>", pages.STORY_CSS + pages.STORY_JS + "</body>")),
            "missing": pack(_strip(missing)), "story": payload, "experiments": experiments,
            "defaultTraj": default_traj, "delay": delay}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out = TEMPLATE.replace("__DATA__", blob).replace("__ROUTER__", ROUTER_JS)
    stats = {"trajectories": len(items), "gallery": len(chosen), "pages": len(rendered), "views": len(views),
             "story_steps": len(steps), "bytes": len(out.encode("utf-8"))}
    return out, stats


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Punish · Scientific Integrity Auditor (static demo)</title>
<style>html,body{margin:0;height:100%;background:#0b0e14;color:#e6ebf5;font:16px system-ui,sans-serif}
#f{border:0;width:100%;height:100%;display:block}#err{padding:40px}</style></head>
<body><iframe id="f" title="Punish demo"></iframe>
<noscript><div id="err">This static demo needs JavaScript.</div></noscript>
<script type="application/json" id="punish-data">__DATA__</script>
<script>__ROUTER__</script></body></html>"""

ROUTER_JS = r"""
"use strict";
const D = JSON.parse(document.getElementById("punish-data").textContent);
const frame = document.getElementById("f");
const texts = new Map();
async function unpack(b64){
  if (texts.has(b64)) return texts.get(b64);
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const t = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  texts.set(b64, t); return t;
}
function keyOf(u){
  const i = u.indexOf("?"), path = (i < 0 ? u : u.slice(0, i)) || "/", q = new URLSearchParams(i < 0 ? "" : u.slice(i + 1));
  const g = k => { const v = q.getAll(k); return v.length ? v[v.length - 1] : ""; };
  if (path === "/view") return "/view?traj=" + (g("traj") || D.defaultTraj) + "&auditor_mode=" + (g("auditor_mode") || "full_trace")
    + "&progressive=" + (["1", "true", "yes", "on"].includes(g("progressive").toLowerCase()) ? "1" : "0") + "&audit=" + (g("audit") || "file");
  if (path === "/compare") return "/compare?traj=" + g("traj");
  if (path === "/dashboard"){
    let e = [...new Set(q.getAll("exp"))].sort();
    if (D.experiments.length && D.experiments.every(x => e.includes(x))) e = [];
    return "/dashboard?exp=" + e.join(",") + "&label=" + (g("label") || "either");
  }
  return path;
}
const js = v => JSON.stringify(v).replace(/</g, "\\u003c");
function shim(search, extra){
  const q = new URLSearchParams(search);
  const delay = q.has("delay") ? (parseFloat(q.get("delay")) || 0) : D.delay;
  return "<script>window.__punishSearch=" + js(search) + ";window.__punishStory=" + js(D.story) + ";window.__punishDelay=" + js(delay) + ";" + extra + "(" + SHIM + ")();<\/script>";
}
const SHIM = String(function(){
  window.__punishGo = u => parent.postMessage({punishGo: u}, "*");
  document.addEventListener("click", e => {
    const a = e.target.closest ? e.target.closest("a[href]") : null; if (!a) return;
    const h = a.getAttribute("href"); if (h && h.startsWith("/")){ e.preventDefault(); window.__punishGo(h); }
  }, true);
  HTMLFormElement.prototype.submit = function(){ this.requestSubmit(); };
  document.addEventListener("submit", e => {
    e.preventDefault(); const f = e.target;
    window.__punishGo((f.getAttribute("action") || "/") + "?" + new URLSearchParams(new FormData(f)));
  }, true);
  if (!window.__punishEvents) return;
  window.EventSource = class {
    constructor(){ this.h = {}; this.closed = false; setTimeout(() => this.run(), 30); }
    addEventListener(n, f){ (this.h[n] = this.h[n] || []).push(f); }
    close(){ this.closed = true; }
    emit(n, d){ const ev = new MessageEvent(n, {data: JSON.stringify(d)}); (this.h[n] || []).forEach(f => f(ev)); }
    async run(){
      const sleep = s => new Promise(r => setTimeout(r, s * 1000)), delay = window.__punishDelay;
      for (let [n, d] of window.__punishEvents){
        if (n === "@") [n, d] = window.__punishLines[d];
        if (this.closed) return;
        if (n === "meta") d.delay = delay;
        if (n === "traj" && d.line > 1 && delay) await sleep(delay);
        this.emit(n, d);
        if (n === "status" && /complete/i.test(d.text || "") && delay) await sleep(delay);
      }
    }
  };
});
async function show(u){
  const i = u.indexOf("?"), path = i < 0 ? u : u.slice(0, i), search = i < 0 ? "" : u.slice(i);
  const step = new URLSearchParams(search).get("step");
  if (path === "/story" && step !== null){
    const s = D.story[parseInt(step, 10)];
    location.replace("#" + (s ? s.url : "/story")); return;
  }
  const k = keyOf(u);
  let page, extra = "";
  if (k.startsWith("/view?") && D.views[k]){
    const v = JSON.parse(await unpack(D.views[k]));
    page = await unpack(D.viewer);
    extra = "window.__punishLines=" + await unpack(D.lines[v.traj]) + ";window.__punishEvents=" + js(v.events) + ";";
  } else if (D.pages[k]){
    page = await unpack(D.pages[k]);
    if (page.includes("<!--punish:")){
      const blocks = JSON.parse(await unpack(D.blocks));
      page = page.replace(/<!--punish:(\d+)-->/g, (m, i) => blocks[+i]);
    }
  }
  else { page = (await unpack(D.missing)).replace('<code id="missing-href"></code>', "<code>" + u.replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c])) + "</code>"); }
  const tag = shim(search, extra);
  frame.srcdoc = page.replace(/<head[^>]*>/i, m => m + tag);
}
frame.addEventListener("load", () => { try { frame.contentWindow.focus(); } catch (e) {} });
window.addEventListener("message", e => { if (e.data && typeof e.data.punishGo === "string") location.hash = "#" + e.data.punishGo; });
const current = () => decodeURIComponent(location.hash.slice(1)) || "/";
window.addEventListener("hashchange", () => show(current()));
if (typeof DecompressionStream === "undefined") document.body.innerHTML = "<p style='padding:40px'>This browser lacks DecompressionStream; please use a current Chrome, Firefox or Safari.</p>";
else show(current());
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m demo.export", description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=str(DEFAULT_OUT), help="output HTML file (default docs/demo.html)")
    p.add_argument("--results-dir", default=str(RESULTS_DIR))
    p.add_argument("--story", default=None, metavar="PLAYLIST_JSON", help="custom story playlist (default: built-in)")
    p.add_argument("--max-gallery", type=int, default=120, help="trajectories in the curated gallery (story ones always included)")
    p.add_argument("--delay", type=float, default=0.8, help="default replay delay in seconds")
    args = p.parse_args(argv)
    out_html, stats = build(Path(args.results_dir), FIXTURES_DIR, args.story, args.max_gallery, args.delay)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(out_html, encoding="utf-8")
    print(f"wrote {out} ({stats['bytes'] / 1e6:.2f} MB): {stats['gallery']}/{stats['trajectories']} trajectories in the gallery, "
          f"{stats['pages']} pages, {stats['views']} replays, {stats['story_steps']} story steps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

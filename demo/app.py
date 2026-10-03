"""Live demo UI: streaming trajectory (left) + auditor flag feed (right).

Dependency-free: stdlib ``http.server`` + Server-Sent Events + one inline HTML page.

    python -m demo.app                                    # replay the golden fixture
    python -m demo.app --flags-progressive --delay 1.5    # flags appear as soon as evidence streams
    python -m demo.app --watch results/trajectories/<episode_id>.jsonl   # tail a live run
    python -m demo.app --audit heuristic                  # audit with auditor.heuristic when finished
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import threading
import webbrowser
from dataclasses import dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from demo import catalog, pages
from demo.core import (FIXTURES_DIR, RESULTS_DIR, ROOT, StreamOptions, find_verdict, parse_line, read_lines,
                       run_heuristic, stream, trajectory_id_of, verdict_candidates)

DEFAULT_TRAJECTORY = FIXTURES_DIR / "trajectories" / "example.jsonl"


@dataclass
class AppConfig:
    """Server-wide defaults; most can be overridden per page via query parameters."""

    defaults: StreamOptions = field(default_factory=lambda: StreamOptions(trajectory=DEFAULT_TRAJECTORY))
    fixtures_dir: Path = FIXTURES_DIR
    results_dir: Path = RESULTS_DIR
    story: str | None = None  # playlist spec for /story ("default" or a JSON file); None = built-in default

    def trajectory_dirs(self) -> list[tuple[str, Path]]:
        """fixtures/trajectories, results/trajectories and every results/<exp>/trajectories."""
        out = [("fixtures", self.fixtures_dir / "trajectories"), ("results", self.results_dir / "trajectories")]
        for exp in catalog.experiments(self.results_dir, None):
            if exp.name != "results":
                out.append(("results", exp.trajectories))
        return out

    def story_steps(self) -> list[dict]:
        return catalog.load_story(self.story, self.results_dir)


def traj_key(path: Path) -> str:
    """Stable string used in ?traj= links: repo-relative when possible."""
    path = Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


class BadRequest(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def resolve_options(config: AppConfig, query: dict[str, list[str]]) -> StreamOptions:
    """Build StreamOptions for a request; only trajectories under the known dirs (or the CLI one) are served."""
    q = {k: v[-1] for k, v in query.items() if v}
    base = config.defaults
    opts = replace(base, results_dir=config.results_dir)
    if q.get("traj"):
        candidate = Path(q["traj"])
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        candidate = candidate.resolve()
        if candidate != Path(base.trajectory).resolve():
            allowed = [d.resolve() for _, d in config.trajectory_dirs()]
            if candidate.suffix != ".jsonl" or not any(candidate.is_relative_to(d) for d in allowed):
                raise BadRequest(403, "Only .jsonl files under fixtures/trajectories or results/[<exp>/]trajectories are served.")
            opts = replace(opts, trajectory=candidate, verdict=None,
                           live=candidate.is_relative_to(config.results_dir.resolve()) and base.live)
    try:
        if "delay" in q:
            opts = replace(opts, delay=max(0.0, float(q["delay"])))
        if "poll" in q:
            opts = replace(opts, poll=max(0.01, float(q["poll"])))
    except ValueError:
        raise BadRequest(400, "delay/poll must be numbers")
    for name in ("live", "progressive"):
        if name in q:
            opts = replace(opts, **{name: q[name].lower() in {"1", "true", "yes", "on"}})
    if "audit" in q:
        if q["audit"] not in {"file", "heuristic"}:
            raise BadRequest(400, "audit must be 'file' or 'heuristic'")
        opts = replace(opts, audit=q["audit"])
    if "auditor_mode" in q:
        if q["auditor_mode"] not in {"full_trace", "report_only", "final_report"}:
            raise BadRequest(400, "auditor_mode must be 'full_trace', 'report_only' or 'final_report'")
        opts = replace(opts, auditor_mode=q["auditor_mode"])
    if not opts.live and not Path(opts.trajectory).exists():
        raise BadRequest(404, f"Trajectory not found: {traj_key(opts.trajectory)}")
    return opts


def list_trajectories(config: AppConfig) -> list[dict]:
    """Metadata for every trajectory the index page offers."""
    out = []
    seen = set()
    entries = [("cli", Path(config.defaults.trajectory))]
    for source, directory in config.trajectory_dirs():
        if directory.is_dir():
            entries += [(source, p) for p in sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)]
    for source, path in entries:
        if path.resolve() in seen or (source == "cli" and not path.exists() and not config.defaults.live):
            continue
        seen.add(path.resolve())
        info = {"key": traj_key(path), "name": path.name, "source": source, "default": source == "cli",
                "exists": path.exists(), "lines": 0, "finished": False, "mtime": None, "config": {}}
        if path.exists():
            lines = read_lines(path)
            first = parse_line(lines[0])[0] if lines else None
            last = parse_line(lines[-1])[0] if lines else None
            info.update(lines=len(lines), mtime=path.stat().st_mtime,
                        finished=bool(last and last.get("type") == "final_report"),
                        config=(first or {}).get("config") or {})
        explicit = config.defaults.verdict if source == "cli" else None
        verdict, vpath = find_verdict(verdict_candidates(path, info["config"].get("trajectory_id"), explicit, config.results_dir))
        info["verdict"] = None if verdict is None else {
            "hack_detected": verdict.get("hack_detected"), "confidence": verdict.get("confidence"),
            "path": traj_key(vpath)}
        out.append(info)
    return out


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "PunishDemo/1.0"
    config: AppConfig  # set on the subclass created by make_server

    def log_message(self, fmt, *args):  # keep the console quiet for SSE polling
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        routes = {"/": self.page_index, "/view": self.page_view, "/events": self.sse_events,
                  "/verdict": self.api_verdict, "/api/trajectories": self.api_trajectories,
                  "/compare": self.page_compare, "/dashboard": self.page_dashboard, "/story": self.page_story,
                  "/api/gallery": self.api_gallery, "/api/compare": self.api_compare,
                  "/api/dashboard": self.api_dashboard, "/api/story": self.api_story,
                  "/healthz": lambda q: self.send_text(200, "ok", "text/plain"),
                  "/favicon.ico": lambda q: self.send_text(200, FAVICON, "image/svg+xml")}
        handler = routes.get(url.path)
        if handler is None:
            return self.send_text(404, "Not found", "text/plain")
        try:
            handler(query)
        except BadRequest as exc:
            if url.path in {"/", "/view", "/compare", "/dashboard", "/story"}:
                self.send_text(exc.status, error_page(str(exc)), "text/html")
            else:
                self.send_json(exc.status, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            pass

    # --- responses -----------------------------------------------------------------
    def send_text(self, status: int, body: str, ctype: str):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: int, obj):
        self.send_text(status, json.dumps(obj, ensure_ascii=False, indent=2), "application/json")

    # --- routes --------------------------------------------------------------------
    def page_index(self, query):
        d = self.config.defaults
        default_key = traj_key(d.trajectory) if (d.live or Path(d.trajectory).exists()) else None
        self.send_text(200, pages.gallery_page(self.gallery(), default_key, d.live), "text/html")

    def gallery(self) -> list[dict]:
        items = catalog.gallery(self.config.results_dir, self.config.fixtures_dir)
        known = {it["key"] for it in items}
        cli = Path(self.config.defaults.trajectory)
        if traj_key(cli) not in known and (cli.exists() or self.config.defaults.live):
            items.insert(0, catalog.trajectory_info(cli, results_dir=self.config.results_dir))
        return items

    def page_view(self, query):
        resolve_options(self.config, query)  # validate early so bad links get a friendly page
        self.send_text(200, VIEWER_HTML.replace("</body>", pages.STORY_CSS + pages.STORY_JS + "</body>"), "text/html")

    def compare_data(self, query) -> dict:
        if not (query.get("traj") or [""])[-1]:
            raise BadRequest(400, "compare needs ?traj=<path to a trajectory .jsonl>")
        opts = resolve_options(self.config, {"traj": query["traj"]})
        if not Path(opts.trajectory).exists():
            raise BadRequest(404, f"Trajectory not found: {traj_key(opts.trajectory)}")
        return catalog.compare(Path(opts.trajectory), self.config.results_dir, self.config.fixtures_dir)

    def page_compare(self, query):
        self.send_text(200, pages.compare_page(self.compare_data(query)), "text/html")

    def api_compare(self, query):
        self.send_json(200, self.compare_data(query))

    def dashboard_data(self, query) -> dict:
        label = (query.get("label") or ["either"])[-1]
        return catalog.dashboard(self.config.results_dir, query.get("exp") or None, label)

    def page_dashboard(self, query):
        self.send_text(200, pages.dashboard_page(self.dashboard_data(query)), "text/html")

    def api_dashboard(self, query):
        self.send_json(200, self.dashboard_data(query))

    def api_gallery(self, query):
        self.send_json(200, self.gallery())

    def page_story(self, query):
        steps = self.config.story_steps()
        if "step" not in query:
            return self.send_text(200, pages.story_index_page(steps), "text/html")
        try:
            i = int(query["step"][-1])
        except ValueError:
            raise BadRequest(400, "step must be an integer")
        if not 0 <= i < len(steps):
            raise BadRequest(404, f"No story step {i} (the playlist has {len(steps)} steps).")
        self.send_response(302)
        self.send_header("Location", pages.story_url(steps[i], i))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def api_story(self, query):
        self.send_text(200, pages.story_payload(self.config.story_steps()), "application/json")

    def api_trajectories(self, query):
        self.send_json(200, list_trajectories(self.config))

    def api_verdict(self, query):
        opts = resolve_options(self.config, query)
        if opts.audit == "heuristic":
            verdict, error = run_heuristic(opts.trajectory, opts.auditor_mode)
            if error:
                return self.send_json(503, {"error": error})
            return self.send_json(200, verdict)
        tid = None
        if Path(opts.trajectory).exists():
            lines = read_lines(opts.trajectory)
            tid = trajectory_id_of(parse_line(lines[0])[0]) if lines else None
        verdict, _ = find_verdict(verdict_candidates(opts.trajectory, tid, opts.verdict, opts.results_dir, opts.auditor_mode))
        if verdict is None:
            return self.send_json(404, {"error": "No verdict available yet for this trajectory."})
        self.send_json(200, verdict)

    def sse_events(self, query):
        opts = resolve_options(self.config, query)
        try:
            start_line = int(self.headers.get("Last-Event-ID") or 0)
        except ValueError:
            start_line = 0
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(b"retry: 2000\n\n")
        for name, data in stream(opts, start_line=start_line):
            if name == "ping":
                self.wfile.write(b": ping\n\n")
            else:
                msg = f"event: {name}\n"
                if name in {"traj", "parse_error"}:
                    msg = f"id: {data['line']}\n" + msg
                msg += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                self.wfile.write(msg.encode("utf-8"))
            self.wfile.flush()
        self.close_connection = True


def make_server(config: AppConfig | None = None, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = type("BoundDemoHandler", (DemoHandler,), {"config": config or AppConfig()})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def view_url(key: str | None = None, **params) -> str:
    parts = [f"traj={quote(key)}"] if key else []
    parts += [f"{k}={quote(str(v))}" for k, v in params.items() if v is not None]
    return "/view" + ("?" + "&".join(parts) if parts else "")


def error_page(message: str) -> str:
    return PAGE_SHELL.replace("__TITLE__", "Error").replace(
        "__BODY__", f'<h1>Can\'t open that trajectory</h1><p class="err">{html.escape(message)}</p><p><a href="/">Back to the index</a></p>')


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect width="16" height="16" rx="3" fill="#ff4d5e"/>'
           '<text x="8" y="12" font-size="11" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="900">P</text></svg>')

PAGE_SHELL = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Punish · __TITLE__</title>
<style>
:root{--bg:#0b0e14;--panel:#121722;--line:#232b3b;--text:#e6ebf5;--dim:#8a96ad;--red:#ff4d5e;--green:#2ecc71;--blue:#4da3ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:17px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:32px 40px}
a{color:var(--blue)}code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.92em}
header{display:flex;gap:24px;align-items:center;margin-bottom:28px}h1{margin:0;font-size:28px}
.logo{font-weight:900;letter-spacing:.18em;background:var(--red);color:#fff;padding:10px 14px;border-radius:8px}
.sub{color:var(--dim);font-size:15px;margin:4px 0 0}.err{color:var(--red);font-size:20px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:14px 16px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}th{color:var(--dim);font-weight:600;font-size:14px;text-transform:uppercase;letter-spacing:.06em}
.links{white-space:nowrap;text-align:right}.btn{display:inline-block;margin-left:8px;padding:8px 14px;border:1px solid var(--line);border-radius:8px;color:var(--text);text-decoration:none;font-size:15px;background:#182031}
.btn:hover{border-color:var(--blue)}.btn.primary{background:var(--blue);color:#06101f;border-color:var(--blue);font-weight:700}.btn.big{margin-left:auto;padding:12px 20px}
.pill{display:inline-block;padding:2px 10px;border-radius:99px;font-size:13px;font-weight:700;letter-spacing:.04em;border:1px solid}
.pill.red{color:var(--red);border-color:var(--red)}.pill.green{color:var(--green);border-color:var(--green)}.pill.blue{color:var(--blue);border-color:var(--blue)}.pill.dim{color:var(--dim);border-color:var(--line)}
</style></head><body>__BODY__</body></html>"""

VIEWER_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Punish · Integrity Auditor</title>
<style>
:root{
  --bg:#0a0d13;--panel:#10151f;--card:#151b27;--card2:#1a2130;--line:#252e40;--text:#e8edf6;--dim:#8a96ad;--faint:#5d687e;
  --red:#ff4d5e;--red-bg:rgba(255,77,94,.12);--green:#2ecc71;--green-bg:rgba(46,204,113,.12);--blue:#4da3ff;--amber:#ffb347;
  --violet:#b48cff;--violet-bg:rgba(180,140,255,.08);--mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--text);font:17px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;display:flex;flex-direction:column;overflow:hidden}
a{color:var(--blue)}
/* header */
.top{display:flex;align-items:center;gap:18px;padding:12px 22px;border-bottom:1px solid var(--line);background:#0d1119;flex:none}
.logo{font-weight:900;letter-spacing:.2em;background:var(--red);color:#fff;padding:6px 12px;border-radius:7px;font-size:16px;text-decoration:none}
.title{font-weight:700;font-size:19px}
.title .sub{display:block;color:var(--dim);font-weight:400;font-size:14px;font-family:var(--mono)}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto;align-items:center}
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 11px;border-radius:99px;font-size:13px;font-weight:700;letter-spacing:.05em;border:1px solid var(--line);color:var(--dim);white-space:nowrap;text-transform:uppercase}
.pill.red{color:var(--red);border-color:rgba(255,77,94,.6)}.pill.green{color:var(--green);border-color:rgba(46,204,113,.6)}.pill.blue{color:var(--blue);border-color:rgba(77,163,255,.6)}
.dot{width:9px;height:9px;border-radius:50%;background:var(--faint)}
.status.live .dot{background:var(--red);animation:pulse 1.2s infinite}.status.streaming .dot{background:var(--blue);animation:pulse 1.2s infinite}.status.finished .dot{background:var(--green)}
@keyframes pulse{50%{opacity:.25}}
/* layout */
main{flex:1;display:grid;grid-template-columns:minmax(0,1.6fr) minmax(400px,1fr);min-height:0}
.pane{display:flex;flex-direction:column;min-height:0}
.pane+.pane{border-left:1px solid var(--line);background:var(--panel)}
.pane-head{display:flex;align-items:center;gap:12px;padding:10px 22px;border-bottom:1px solid var(--line);color:var(--dim);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;flex:none}
.pane-head .count{margin-left:auto;font-family:var(--mono);letter-spacing:0;text-transform:none;font-weight:400}
.scroll{overflow-y:auto;flex:1;min-height:0;scroll-behavior:auto}
#stream{padding:18px 22px 120px}
/* cards */
.card{position:relative;display:grid;grid-template-columns:52px minmax(0,1fr);margin:0 0 12px;animation:enter .35s ease-out;scroll-margin:90px}
@keyframes enter{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.ln{font-family:var(--mono);color:var(--faint);font-size:14px;padding-top:13px;text-align:right;padding-right:12px;user-select:none}
.box{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:11px 15px 12px;min-width:0;transition:border-color .2s,box-shadow .2s,background .2s}
.card.result .box{background:#131925;border-style:dashed}
.card.paired-next{margin-bottom:3px}.card.paired-next .box{border-bottom-left-radius:3px;border-bottom-right-radius:3px}
.card.result.paired-prev .box{border-top-left-radius:3px;border-top-right-radius:3px}
.hdr{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.badge{font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding:2px 9px;border-radius:6px;background:#222b3c;color:var(--dim)}
.badge.system{background:#2a2f3d;color:#c3cbe0}.badge.user{background:#173254;color:#8fc4ff}.badge.assistant{background:#2d2350;color:#cbb4ff}
.badge.tool{background:#3a2a10;color:var(--amber)}.badge.read_file{background:#10304a;color:#7cc4ff}.badge.run_python{background:#3a2a10;color:var(--amber)}.badge.write_report{background:#123b26;color:#6ee7a0}
.badge.result{background:#1d2433;color:var(--dim)}.badge.final{background:#123b26;color:#6ee7a0}.badge.error{background:var(--red-bg);color:var(--red)}
.etype{font-family:var(--mono);font-size:13px;color:var(--faint)}
.callsig{font-family:var(--mono);font-size:16px;color:#dfe6f3;word-break:break-all}.callsig b{color:#fff}
.pair{font-family:var(--mono);font-size:13px;color:var(--dim);cursor:pointer;border-bottom:1px dotted var(--faint)}
.pair:hover{color:var(--text)}
.ok{color:var(--green)}.bad{color:var(--red)}
.content{white-space:pre-wrap;word-wrap:break-word}
.thought{margin:4px 0 8px;padding:9px 13px;border-left:3px solid var(--violet);background:var(--violet-bg);border-radius:0 8px 8px 0;color:#d6c8f5;font-style:italic;white-space:pre-wrap}
.label{display:block;font-style:normal;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--violet);margin-bottom:2px}
.label.pub{color:var(--blue)}
body.report-only .thought .label::after{content:" · hidden from auditor (report_only)";color:var(--faint)}
body.mode-final_report .card.fr-hidden{opacity:.32}
body.mode-final_report .card.fr-hidden .hdr::after{content:"not shown to the auditor (final_report)";font-size:12px;color:var(--amber);font-weight:700;letter-spacing:.04em}
pre{margin:6px 0 0;font-family:var(--mono);font-size:14px;line-height:1.45;background:#0c1018;border:1px solid #1e2636;border-radius:8px;padding:10px 12px;white-space:pre-wrap;word-break:break-word;color:#cfd8e6}
.clamp pre{max-height:12.5em;overflow:hidden;-webkit-mask-image:linear-gradient(#000 65%,transparent);mask-image:linear-gradient(#000 65%,transparent)}
.toggle{margin-top:6px;background:none;border:1px solid var(--line);color:var(--dim);border-radius:6px;padding:3px 10px;font-size:13px;cursor:pointer}
.toggle:hover{color:var(--text);border-color:var(--dim)}
.md h3{margin:6px 0 4px;font-size:20px}.md h4{margin:10px 0 2px;font-size:16px;color:#c9d3e5}.md p{margin:3px 0}.md li{margin-left:18px}
.kv{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.kv span{font-family:var(--mono);font-size:13px;background:#0c1018;border:1px solid var(--line);border-radius:6px;padding:1px 8px;color:var(--dim)}
.kv span b{color:var(--text);font-weight:500}
/* flagged lines */
.right{display:flex;gap:10px;align-items:center;margin-left:auto}.flags{display:flex;gap:6px;flex-wrap:wrap}
.flag{font-size:12px;font-weight:800;letter-spacing:.04em;padding:2px 9px;border-radius:6px;background:var(--red);color:#fff;cursor:pointer}
.card.flagged .box{border:2px solid var(--red);box-shadow:0 0 0 1px rgba(255,77,94,.25),0 0 22px rgba(255,77,94,.18);background:linear-gradient(0deg,rgba(255,77,94,.05),rgba(255,77,94,.05)),var(--card)}
.card.flagged .ln{color:var(--red);font-weight:700}
.card.focus .box{background:linear-gradient(0deg,rgba(255,77,94,.16),rgba(255,77,94,.16)),var(--card);box-shadow:0 0 0 3px rgba(255,77,94,.55),0 0 34px rgba(255,77,94,.4)}
.card.focus::before{content:"";position:absolute;left:40px;top:6px;bottom:6px;width:4px;border-radius:4px;background:var(--red)}
.card.pairhl .box{border-color:var(--blue)}
/* right pane */
#feed{padding:20px 22px 80px}
.banner{border-radius:14px;padding:22px 22px 18px;border:2px solid var(--line);background:var(--card);text-align:center;margin-bottom:16px}
.banner .big{font-size:40px;font-weight:900;letter-spacing:.06em;line-height:1.1}
.banner .small{color:var(--dim);font-size:14px;margin-top:6px;font-family:var(--mono);overflow-wrap:anywhere}
.banner.pending .big{color:var(--dim);font-size:30px}
.banner.pending .big::after{content:"";display:inline-block;width:.6em;animation:dots 1.4s steps(4) infinite;text-align:left}
@keyframes dots{0%{content:""}25%{content:"."}50%{content:".."}75%{content:"..."}}
.banner.hack{border-color:var(--red);background:radial-gradient(circle at 50% 0,rgba(255,77,94,.35),rgba(255,77,94,.08) 70%);box-shadow:0 0 40px rgba(255,77,94,.25)}
.banner.hack .big{color:#fff;text-shadow:0 0 18px rgba(255,77,94,.8)}
.banner.clean{border-color:var(--green);background:radial-gradient(circle at 50% 0,rgba(46,204,113,.28),rgba(46,204,113,.06) 70%)}
.banner.clean .big{color:var(--green)}
.banner.reveal{animation:reveal .7s cubic-bezier(.2,1.4,.4,1)}
@keyframes reveal{from{transform:scale(.85);opacity:0}to{transform:none;opacity:1}}
.conf{display:flex;align-items:center;gap:14px;margin:4px 0 16px}
.conf .num{font-size:30px;font-weight:800;font-family:var(--mono);min-width:3.4em}
.conf .bar{flex:1;height:12px;border-radius:99px;background:#202838;overflow:hidden}
.conf .bar i{display:block;height:100%;width:0;border-radius:99px;transition:width 1s ease-out}
.conf .lbl{color:var(--dim);font-size:13px;display:block}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.chip{font-size:14px;font-weight:700;padding:5px 12px;border-radius:99px;border:1px solid;font-family:var(--mono)}
.section{color:var(--dim);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin:6px 0 10px}
.ev{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--red);border-radius:10px;padding:11px 14px;margin-bottom:10px;cursor:pointer;transition:transform .15s,border-color .15s,background .15s;animation:enter .4s ease-out}
.ev:hover{transform:translateX(-3px);border-color:var(--red)}
.ev.active{background:#2a1820;border-color:var(--red);box-shadow:0 0 0 2px rgba(255,77,94,.45)}
.ev .eh{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.ev .lines{margin-left:auto;font-family:var(--mono);font-size:14px;color:var(--red);font-weight:700;white-space:nowrap}
.ev .ex{color:#d5dceb;font-size:16px}
.notes{color:var(--dim);font-size:15px;border-top:1px solid var(--line);padding-top:12px;margin-top:8px;white-space:pre-wrap}
.notice{border:1px solid var(--amber);color:var(--amber);background:rgba(255,179,71,.08);border-radius:10px;padding:10px 14px;margin-bottom:12px;font-size:15px}
.notice.error{border-color:var(--red);color:var(--red);background:var(--red-bg)}
.stat{color:var(--dim);font-size:15px;margin-bottom:14px;min-height:1.5em}
.waiting{color:var(--faint);text-align:center;padding:10px 0 0;font-size:15px}
.legend{color:var(--faint);font-size:13px;margin-top:18px}
@media (max-width:1000px){body{overflow:auto}main{grid-template-columns:1fr}.scroll{overflow:visible}.pane+.pane{border-left:0;border-top:1px solid var(--line)}}
</style>
</head>
<body>
<div class="top">
  <a class="logo" href="/" title="All trajectories">PUNISH</a>
  <div class="title">Scientific Integrity Auditor<span class="sub" id="tid">loading…</span></div>
  <div class="meta" id="meta"></div>
  <span class="pill status" id="status"><span class="dot"></span><span id="status-text">connecting</span></span>
</div>
<main>
  <section class="pane">
    <div class="pane-head">Agent trajectory<span class="count" id="count">0 events</span></div>
    <div class="scroll" id="stream-wrap"><div id="stream"></div></div>
  </section>
  <section class="pane">
    <div class="pane-head">Auditor flag feed<span class="count" id="flagcount"></span></div>
    <div class="scroll"><div id="feed">
      <div id="notices"></div>
      <div class="banner pending" id="banner"><div class="big">AUDITING</div><div class="small" id="banner-sub">watching the trajectory</div></div>
      <div class="stat" id="stat"></div>
      <div id="verdict-body" hidden>
        <div class="conf"><div class="num" id="conf-num">–</div><div style="flex:1"><span class="lbl">confidence the trajectory contains hacking</span><div class="bar"><i id="conf-bar"></i></div></div></div>
        <div class="chips" id="chips"></div>
      </div>
      <div class="section" id="ev-title" hidden>Evidence <span style="text-transform:none;letter-spacing:0;font-weight:400">· click to jump to the lines</span></div>
      <div id="evidence"></div>
      <div class="notes" id="notes" hidden></div>
      <div class="legend">Purple italic = the agent's <b>private reasoning</b>; plain text = what it said publicly.</div>
    </div></div>
  </section>
</main>
<script>
"use strict";
const HACK_COLORS = {
  suspicious_access:"#ff4d5e", fabricated_verification:"#ff8a3d", trace_claim_mismatch:"#ff5fd2",
  rationalization:"#ffd23f", fabricated_source:"#ff7a90", methodological_drift:"#5fb4ff"
};
const $ = id => document.getElementById(id);
function h(tag, attrs, ...kids){
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})){
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style") el.style.cssText = v;
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()){ if (kid != null && kid !== false) el.append(kid instanceof Node ? kid : String(kid)); }
  return el;
}
const state = {
  lines: new Map(),      // line -> card element
  events: new Map(),     // line -> event
  calls: new Map(),      // tool_call id -> line
  results: new Map(),    // tool_call id -> result line
  evidence: [],          // index -> item
  verdict: null, auto: true, finished: false, live: false, progRevealed: false,
};

/* ---------- helpers ---------- */
function collapsible(text, cls){
  const s = String(text ?? "");
  const nLines = s.split("\n").length;
  const pre = h("pre", {class: cls || null}, s);
  if (nLines <= 10 && s.length <= 700) return pre;
  const wrap = h("div", {class:"clamp"}, pre);
  const btn = h("button", {class:"toggle"}, `Show all (${nLines} lines)`);
  btn.addEventListener("click", ev => {
    ev.stopPropagation();
    const open = wrap.classList.toggle("clamp");
    btn.textContent = open ? `Show all (${nLines} lines)` : "Collapse";
  });
  wrap.append(btn);
  return wrap;
}
function markdown(text){
  const box = h("div", {class:"md"});
  let para = [];
  const flush = () => { if (para.length){ box.append(h("p", {}, para.join(" "))); para = []; } };
  for (const raw of String(text || "").split("\n")){
    const line = raw.trimEnd();
    let m;
    if (!line.trim()) { flush(); continue; }
    if ((m = line.match(/^#\s+(.*)/))) { flush(); box.append(h("h3", {}, m[1])); }
    else if ((m = line.match(/^#{2,6}\s+(.*)/))) { flush(); box.append(h("h4", {}, m[1])); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { flush(); box.append(h("li", {}, m[1])); }
    else para.push(line);
  }
  flush();
  if (!box.childNodes.length) box.append(h("p", {class:"etype"}, "(empty report)"));
  return box;
}
function badge(cls, text){ return h("span", {class:"badge " + cls}, text); }
function setStatus(kind, text){ const s = $("status"); s.className = "pill status " + kind; $("status-text").textContent = text; }
function argSig(name, args){
  args = args || {};
  if (name === "read_file") return [h("b", {}, "read_file"), "(", JSON.stringify(args.path ?? ""), ")"];
  if (name === "write_report") return [h("b", {}, "write_report"), "(", JSON.stringify(args.path ?? ""), ", …)"];
  if (name === "run_python") return [h("b", {}, "run_python"), "(code)"];
  return [h("b", {}, name || "?"), "(", Object.keys(args).join(", "), ")"];
}
function jumpTo(line, flash){
  const el = state.lines.get(line);
  if (!el) return;
  state.auto = false;
  el.scrollIntoView({behavior:"smooth", block:"center"});
  if (flash){ el.classList.add("pairhl"); setTimeout(() => el.classList.remove("pairhl"), 1400); }
}

/* ---------- trajectory cards ---------- */
function renderEvent(line, ev){
  state.events.set(line, ev);
  const box = h("div", {class:"box"});
  const hdr = h("div", {class:"hdr"});
  const flags = h("div", {class:"flags"});
  const right = h("div", {class:"right"}, flags);
  const card = h("div", {class:"card", id:"L" + line, "data-line": line}, h("div", {class:"ln"}, "L" + line), box);
  box.append(hdr);
  const t = ev.type;
  if (t === "system_prompt"){
    const c = ev.config || {};
    hdr.append(badge("system", "system"), h("span", {class:"etype"}, "system_prompt"));
    box.append(h("div", {class:"content"}, ev.text || ""));
    box.append(h("div", {class:"kv"}, ...["task_id", "agent_config", "model"].filter(k => c[k] != null).map(k => h("span", {}, k + " ", h("b", {}, String(c[k]))))));
    setHeader(c);
  } else if (t === "message"){
    const role = ev.role || "?";
    hdr.append(badge(role === "user" ? "user" : "assistant", role), h("span", {class:"etype"}, "message"));
    if (role === "assistant"){
      box.append(h("div", {class:"thought"}, h("span", {class:"label"}, "private reasoning"), ev.reasoning ? ev.reasoning : h("span", {style:"opacity:.6"}, "(none)")));
      box.append(h("span", {class:"label pub"}, "public"));
    }
    box.append(h("div", {class:"content"}, ev.content || ""));
  } else if (t === "tool_call"){
    card.classList.add("call");
    hdr.append(badge(ev.name || "tool", "tool call"), h("span", {class:"callsig"}, argSig(ev.name, ev.args)), h("span", {class:"etype"}, ev.id || ""));
    const a = ev.args || {};
    if (ev.name === "run_python") box.append(collapsible(a.code));
    else if (ev.name === "write_report") box.append(collapsible(a.content));
    else if (ev.name !== "read_file") box.append(collapsible(JSON.stringify(a, null, 2)));
    if (ev.id) state.calls.set(ev.id, line);
  } else if (t === "tool_result"){
    card.classList.add("result");
    const callLine = state.calls.get(ev.id);
    const call = callLine ? state.events.get(callLine) : null;
    hdr.append(badge("result", "tool result"), h("span", {class:"etype"}, ev.id || ""));
    if (call) hdr.append(h("span", {class:"callsig", style:"font-size:14px;color:var(--dim)"}, "↳ ", argSig(call.name, call.args)));
    if (ev.exit_code != null) hdr.append(h("span", {class:"etype " + (ev.exit_code === 0 ? "ok" : "bad")}, "exit " + ev.exit_code));
    box.append(collapsible(ev.output));
    if (ev.id) state.results.set(ev.id, line);
    if (callLine){
      const callCard = state.lines.get(callLine);
      right.append(h("span", {class:"pair", title:"jump to the tool call", onclick: () => jumpTo(callLine, true)}, "call L" + callLine));
      if (callCard){
        callCard.querySelector(".right").append(h("span", {class:"pair", title:"jump to the result", onclick: () => jumpTo(line, true)}, "result L" + line));
        if (callLine === line - 1){ callCard.classList.add("paired-next"); card.classList.add("paired-prev"); }
        const pairOn = on => [callCard, card].forEach(c => c.classList.toggle("pairhl", on));
        for (const c of [callCard, card]){ c.addEventListener("mouseenter", () => pairOn(true)); c.addEventListener("mouseleave", () => pairOn(false)); }
      }
    } else {
      hdr.append(h("span", {class:"etype bad"}, "no matching tool_call"));
    }
  } else if (t === "final_report"){
    hdr.append(badge("final", "final report"), h("span", {class:"etype"}, "final_report"));
    box.append(markdown(ev.text));
  } else {
    hdr.append(badge("error", t || "unknown"));
    box.append(collapsible(JSON.stringify(ev, null, 2)));
  }
  hdr.append(right);
  if (!(t === "system_prompt" || t === "final_report" || (t === "message" && ev.role === "user"))) card.classList.add("fr-hidden");
  addCard(line, card);
}
function renderParseError(line, err, raw){
  const box = h("div", {class:"box"}, h("div", {class:"hdr"}, badge("error", "unparseable line"), h("span", {class:"etype"}, err), h("div", {class:"right"}, h("div", {class:"flags"}))), collapsible(raw));
  addCard(line, h("div", {class:"card", id:"L" + line, "data-line": line}, h("div", {class:"ln"}, "L" + line), box));
}
function addCard(line, card){
  if (state.lines.has(line)) return;
  state.lines.set(line, card);
  const stream = $("stream");
  // keep line order even if events arrive out of order (e.g. after a reconnect)
  const after = [...stream.children].find(c => +c.dataset.line > line);
  stream.insertBefore(card, after || null);
  $("count").textContent = state.lines.size + (state.lines.size === 1 ? " event" : " events");
  markLine(line);
  if (state.auto){ const w = $("stream-wrap"); w.scrollTop = w.scrollHeight; }
}
function setHeader(c){
  $("tid").textContent = c.trajectory_id || "";
  const meta = $("meta"); meta.innerHTML = "";
  if (c.task_id) meta.append(h("span", {class:"pill blue"}, c.task_id));
  if (c.agent_config) meta.append(h("span", {class:"pill " + (c.incentivized ? "red" : "green")}, c.agent_config));
  if (c.model) meta.append(h("span", {class:"pill"}, c.model));
}

/* ---------- evidence ---------- */
function covering(line){ return state.evidence.map((e, i) => [e, i]).filter(([e]) => e && Array.isArray(e.line_range) && e.line_range[0] <= line && line <= e.line_range[1]); }
function markLine(line){
  const card = state.lines.get(line);
  if (!card) return;
  const hits = covering(line);
  card.classList.toggle("flagged", hits.length > 0);
  const flags = card.querySelector(".flags");
  flags.innerHTML = "";
  const seen = new Set();
  for (const [e, i] of hits){
    if (seen.has(e.hack_type)) continue;
    seen.add(e.hack_type);
    flags.append(h("span", {class:"flag", style:`background:${HACK_COLORS[e.hack_type] || "var(--red)"};color:#160409`, title:e.explanation || "", onclick: ev => { ev.stopPropagation(); focusEvidence(i, true); }}, e.hack_type));
  }
}
function remarkAll(){ for (const line of state.lines.keys()) markLine(line); }
function rangeText(r){ return r[0] === r[1] ? "L" + r[0] : `L${r[0]}–${r[1]}`; }
function addEvidence(index, item){
  if (state.evidence[index]) return;
  state.evidence[index] = item;
  const r = Array.isArray(item.line_range) ? item.line_range : [0, 0];
  const color = HACK_COLORS[item.hack_type] || "var(--red)";
  const el = h("div", {class:"ev", id:"ev" + index, "data-index": index, style:`border-left-color:${color}`, onclick: () => focusEvidence(index, false)},
    h("div", {class:"eh"}, h("span", {class:"chip", style:`color:${color};border-color:${color}`}, item.hack_type || "?"), h("span", {class:"lines"}, rangeText(r))),
    h("div", {class:"ex"}, item.explanation || ""));
  const list = $("evidence");
  const after = [...list.children].find(c => +c.dataset.index > index);
  list.insertBefore(el, after || null);
  $("ev-title").hidden = false;
  $("flagcount").textContent = list.children.length + (list.children.length === 1 ? " flag" : " flags");
  for (let l = r[0]; l <= r[1]; l++) markLine(l);
}
function focusEvidence(index, fromCard){
  const item = state.evidence[index];
  if (!item) return;
  document.querySelectorAll(".card.focus").forEach(c => c.classList.remove("focus"));
  document.querySelectorAll(".ev.active").forEach(c => c.classList.remove("active"));
  const ev = $("ev" + index); if (ev){ ev.classList.add("active"); if (fromCard) ev.scrollIntoView({behavior:"smooth", block:"nearest"}); }
  const [a, b] = item.line_range;
  for (let l = a; l <= b; l++){ const c = state.lines.get(l); if (c) c.classList.add("focus"); }
  const first = state.lines.get(a);
  if (first && !fromCard){ state.auto = false; first.scrollIntoView({behavior:"smooth", block: (b - a) > 2 ? "start" : "center"}); }
}

/* ---------- verdict ---------- */
function setBanner(kind, big, small){
  const b = $("banner");
  const changed = !b.classList.contains(kind);
  b.className = "banner " + kind + (changed && kind !== "pending" ? " reveal" : "");
  b.querySelector(".big").textContent = big;
  $("banner-sub").textContent = small || "";
}
function showVerdict(d){
  const v = d.verdict || {};
  state.verdict = v;
  document.body.classList.toggle("report-only", v.auditor_mode === "report_only");
  const hack = v.hack_detected === true;
  setBanner(hack ? "hack" : "clean", hack ? "HACK DETECTED" : "CLEAN", [v.auditor_mode, d.source].filter(Boolean).join(" · "));
  $("verdict-body").hidden = false;
  const conf = typeof v.confidence === "number" ? v.confidence : null;
  $("conf-num").textContent = conf == null ? "–" : Math.round(conf * 100) + "%";
  const bar = $("conf-bar");
  bar.style.background = hack ? "linear-gradient(90deg,#ff8a3d,var(--red))" : "linear-gradient(90deg,#1e9e57,var(--green))";
  requestAnimationFrame(() => { bar.style.width = conf == null ? "0" : (conf * 100) + "%"; });
  const chips = $("chips"); chips.innerHTML = "";
  for (const t of v.hack_types || []){ const c = HACK_COLORS[t] || "var(--red)"; chips.append(h("span", {class:"chip", style:`color:${c};border-color:${c};background:${c}1f`}, t)); }
  (v.evidence || []).forEach((e, i) => addEvidence(i, e));
  remarkAll();
  if (v.auditor_notes){ $("notes").hidden = false; $("notes").textContent = v.auditor_notes; }
  if (d.problems && d.problems.length) notice("warn", "Verdict has schema problems: " + d.problems.join("; "));
  $("stat").textContent = hack ? `${(v.evidence || []).length} evidence item(s) across ${state.lines.size} events` : "No hacking found in this trajectory.";
}
function notice(level, text){ $("notices").append(h("div", {class:"notice " + (level === "error" ? "error" : "")}, text)); }

/* ---------- wiring ---------- */
$("stream-wrap").addEventListener("scroll", () => {
  const w = $("stream-wrap");
  state.auto = w.scrollHeight - w.scrollTop - w.clientHeight < 60;
});
const es = new EventSource("/events" + location.search);
const on = (name, fn) => es.addEventListener(name, e => fn(JSON.parse(e.data || "{}")));
on("meta", m => {
  state.live = !!m.live;
  setStatus(m.live ? "live" : "streaming", m.live ? "live" : "replay");
  const meta = $("meta");
  if (m.audit === "heuristic") meta.append(h("span", {class:"pill"}, "heuristic auditor"));
  document.body.classList.add("mode-" + (m.auditor_mode || "full_trace"));
  if (m.auditor_mode === "report_only") document.body.classList.add("report-only");
  if (m.auditor_mode && m.auditor_mode !== "full_trace") meta.append(h("span", {class:"pill"}, m.auditor_mode));
});
on("traj", d => { if (!state.lines.has(d.line)) renderEvent(d.line, d.event || {}); if ((d.event || {}).type === "final_report") $("stat").textContent = "Trajectory complete."; });
on("parse_error", d => renderParseError(d.line, d.error, d.raw));
on("status", d => { $("stat").textContent = d.text || ""; });
on("notice", d => notice(d.level, d.text));
on("evidence", d => {
  addEvidence(d.index, d.item);
  if (!state.verdict) setBanner("hack", "HACK DETECTED", "auditor flags streaming in…");
});
on("verdict", showVerdict);
on("reset", () => { state.lines.clear(); state.events.clear(); state.calls.clear(); state.results.clear(); $("stream").innerHTML = ""; });
on("done", () => {
  es.close(); state.finished = true;
  window.__punishDone = true; document.dispatchEvent(new Event("punish:done"));
  setStatus("finished", "finished");
  if (!state.verdict && $("banner").classList.contains("pending")) setBanner("pending", "NO VERDICT", "");
});
es.onerror = () => { if (!state.finished) setStatus("", "reconnecting"); };
document.addEventListener("keydown", e => {
  if (e.key === "End"){ state.auto = true; const w = $("stream-wrap"); w.scrollTop = w.scrollHeight; }
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= 9 && state.evidence[n - 1]) focusEvidence(n - 1, false);
});
</script>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m demo.app", description=__doc__.split("\n\n")[0])
    p.add_argument("--host", default="127.0.0.1", help="bind address (0.0.0.0 to share on the LAN)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--trajectory", default=str(DEFAULT_TRAJECTORY), help="trajectory JSONL to replay")
    p.add_argument("--verdict", default=None, help="verdict JSON (default: looked up next to the trajectory)")
    p.add_argument("--watch", default=None, metavar="JSONL",
                   help="live mode: tail this file while the agent writes it, then poll results/verdicts/<episode_id>.json")
    p.add_argument("--delay", type=float, default=1.2, help="replay: seconds between events")
    p.add_argument("--flags-progressive", action="store_true",
                   help="replay: reveal each evidence item as soon as its last line has streamed")
    p.add_argument("--audit", choices=["file", "heuristic"], default="file",
                   help="where the verdict comes from: a verdict file, or auditor.heuristic once the trajectory finishes")
    p.add_argument("--auditor-mode", choices=["full_trace", "report_only", "final_report"], default="full_trace")
    p.add_argument("--poll", type=float, default=0.25, help="live: polling interval in seconds")
    p.add_argument("--verdict-timeout", type=float, default=0.0, help="live: stop waiting for a verdict after N seconds (0 = never)")
    p.add_argument("--story", nargs="?", const="default", default=None, metavar="PLAYLIST_JSON",
                   help="open the curated story playlist (auto-advancing); optional JSON list of steps to use instead")
    p.add_argument("--results-dir", default=str(RESULTS_DIR))
    p.add_argument("--open", action="store_true", help="open the browser")
    p.add_argument("--verbose", action="store_true", help="log HTTP requests")
    return p


def config_from_args(args: argparse.Namespace) -> AppConfig:
    live = args.watch is not None
    defaults = StreamOptions(
        trajectory=Path(args.watch or args.trajectory).resolve(),
        verdict=Path(args.verdict).resolve() if args.verdict else None,
        live=live, delay=args.delay, progressive=args.flags_progressive, audit=args.audit,
        auditor_mode=args.auditor_mode, poll=args.poll, verdict_timeout=args.verdict_timeout,
        results_dir=Path(args.results_dir).resolve())
    return AppConfig(defaults=defaults, results_dir=defaults.results_dir, story=args.story)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    if not config.defaults.live and not config.defaults.trajectory.exists():
        print(f"error: trajectory not found: {config.defaults.trajectory}", file=sys.stderr)
        return 2
    server = make_server(config, args.host, args.port)
    server.verbose = args.verbose
    host = "localhost" if args.host in {"127.0.0.1", "0.0.0.0"} else args.host
    base = f"http://{host}:{server.server_address[1]}"
    mode = "live tail" if config.defaults.live else "replay"
    print(f"Punish demo ({mode}) of {traj_key(config.defaults.trajectory)}")
    print(f"  viewer:    {base}/view\n  gallery:   {base}/\n  results:   {base}/dashboard\n  story:     {base}/story")
    start = f"{base}/view"
    if args.story:
        steps = config.story_steps()
        print(f"Story: {len(steps)} steps -> {base}/story?step=0")
        start = f"{base}/story?step=0"
    if args.open:
        threading.Timer(0.5, webbrowser.open, args=(start,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

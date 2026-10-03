# `demo/`

Live demo of the integrity auditor: the agent's trajectory streams in on the left, and the auditor's
flag feed on the right shows the verdict (HACK DETECTED / CLEAN, confidence, hack types) and the evidence.
Clicking an evidence item scrolls to its lines and highlights them; flagged lines are outlined red with their
`hack_type`. Dependency-free: stdlib `http.server` + Server-Sent Events + one inline HTML page (no npm, no CDNs).

See the `demo/` section of [ARCHITECTURE.md](../ARCHITECTURE.md) for the spec and schemas.

## Pitch pages (demo v2)

```bash
.venv/bin/python -m demo.app --port 8000 --story --open   # curated story, auto-advancing (→ next, ← back, space pause)
# http://localhost:8000/            gallery of every results/*/trajectories/*.jsonl (filters + ground-truth/verdict badges)
# http://localhost:8000/compare?traj=results/probe_v1/trajectories/metric_gaming__covert__ep000.jsonl   mode comparison
# http://localhost:8000/dashboard   hack rates + auditor precision/recall/AUROC (eval.analyze.load_experiment) + SVG charts
.venv/bin/python -m demo.app --story my_story.json         # custom playlist: JSON list of steps (see catalog.load_story)
```

Results layout read by `catalog.py`: `results/<exp>/{trajectories,verdicts,episodes,judgments}/`, plus
`results/<exp>/reaudit_<name>/{verdicts,episodes}/` (shown as extra auditors in the gallery and dashboard).

## Run (from the repo root)

```bash
# Replay the golden fixture offline (default: fixtures/trajectories/example.jsonl + fixtures/verdicts/example.json)
.venv/bin/python -m demo.app --port 8000 --delay 1.2
# open http://localhost:8000/view   (index of all trajectories: http://localhost:8000/)

# The money shot: each flag appears as soon as its last line has streamed (eval.py read -> red flag)
.venv/bin/python -m demo.app --flags-progressive --delay 1.5

# Any trajectory/verdict pair
.venv/bin/python -m demo.app --trajectory path/to/x.jsonl --verdict path/to/x.json

# Live: tail a trajectory the agent runner is writing, then poll results/verdicts/<episode_id>.json
.venv/bin/python -m demo.app --watch results/trajectories/leaked_answer__incentivized__ep000.jsonl
.venv/bin/python -m eval.run_episode --task leaked_answer --config incentivized   # in another shell

# Audit with the offline rule-based auditor (auditor.heuristic) once final_report is seen
.venv/bin/python -m demo.app --audit heuristic [--auditor-mode report_only]
```

Other flags: `--host 0.0.0.0` (share on the LAN), `--poll 0.25`, `--verdict-timeout N`, `--results-dir results`,
`--open` (open the browser), `--verbose` (log requests). In the viewer, `1`–`9` jump to evidence items and `End`
resumes auto-scroll.

No-browser fallback (same options, ANSI output):

```bash
.venv/bin/python -m demo.terminal --flags-progressive --delay 0.8
.venv/bin/python -m demo.terminal --watch results/trajectories/<episode_id>.jsonl
```

## Endpoints

| Path | What |
|---|---|
| `/` | gallery of trajectories in `fixtures/`, `results/trajectories/` and `results/<exp>/trajectories/` |
| `/compare?traj=<path>` | the three auditor modes side by side (evidence cited, lines each mode could see) |
| `/dashboard?exp=<name>&label=labeller\|judge\|either` | results dashboard |
| `/story`, `/story?step=N` | story playlist / redirect to step N |
| `/api/gallery`, `/api/compare`, `/api/dashboard`, `/api/story` | the same data as JSON |
| `/view?traj=<path>` | the two-pane viewer |
| `/events?traj=<path>` | SSE stream (see below) |
| `/verdict?traj=<path>` | the verdict JSON (404 if none yet; `?audit=heuristic` runs `auditor.heuristic`) |
| `/api/trajectories` | index data as JSON |

`/view`, `/events` and `/verdict` accept query overrides of the CLI defaults: `traj`, `live=0|1`, `delay`,
`progressive=0|1`, `audit=file|heuristic`, `auditor_mode=full_trace|report_only|final_report`, `poll`. Only `.jsonl` files under
`fixtures/trajectories/`, `results/[<exp>/]trajectories/` or the CLI trajectory are served.

SSE events, in order: `meta`, then one `traj` per JSONL line (`{"line": n, "event": {...}}`, SSE `id` = line number,
so reconnects resume via `Last-Event-ID`; malformed lines arrive as `parse_error`), `evidence` (`{"index", "item"}`,
progressive mode only), `status` / `notice` messages, `verdict` (`{"verdict", "source", "problems"}`), and finally
`done`. Live mode holds back partially written lines, sends `: ping` keepalives, and emits `reset` if the file is truncated.

## Verdict lookup

With `--audit file` (default), the verdict is the `--verdict` file if given, otherwise the first that exists of
`<traj_dir>/../verdicts/<stem>.json` (so `fixtures/trajectories/x.jsonl` -> `fixtures/verdicts/x.json`),
`results/verdicts/<trajectory_id>.json` and `results/verdicts/<stem>.json`.

## Code

- `core.py`: shared streaming logic (`stream(StreamOptions)` yields the events above; used by both front-ends).
- `app.py`: HTTP server + inline page (`make_server(AppConfig, host, port)` for embedding/tests).
- `terminal.py`: ANSI replay (`replay(StreamOptions, out)`).
- `catalog.py`: read-only index of `results/` (gallery rows, per-mode visibility/citations, dashboard data, story).
- `pages.py`: server-rendered HTML for gallery / compare / dashboard / story (inline CSS + SVG, no external assets).

Tests: `.venv/bin/pytest -q tests/test_demo.py tests/test_demo_v2.py`.

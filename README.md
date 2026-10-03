# Punish

**An auditor that catches AI science agents reward-hacking, by reading what they did and
not just what they wrote.**

A Claude "subject" agent works on small science tasks that contain planted exploits: a
leaked answer key, a grader that pays for R² ≥ 0.90, a sponsor who wants p < 0.05, a corrupt
data plate, a thin bibliography, or a forgiving metric. A Claude auditor then reads the
agent's trajectory (private reasoning, tool calls and results, final report) and returns a
structured verdict: `hack_detected`, `confidence`, `hack_types` from a closed six-type
vocabulary, and line-level `evidence`. Built for the London AI x Science Hackathon,
Track 2.

Preliminary headline (v2 sweep: 240 trajectories from Sonnet 4.6 and Haiku 4.5, 720
audits, Opus-judge ground truth):

| auditor sees | recall | FPR | AUROC |
|---|---|---|---|
| reasoning + actions + report (`full_trace`) | 0.89 | 0.25 | 0.94 |
| actions + report (`report_only`) | 0.92 | 0.25 | 0.92 |
| final report only (`final_report`) | 0.66 | 0.20 | 0.83 |

Reading only the report misses a third of the hacks. Seeing the actions recovers them, and
seeing the reasoning adds little on these tasks. Instructed (`covert`) agents hack 77–83% of
the time, pressured or incentivised agents 13–33%, and honest agents 0–10%. A deterministic
exploit labeller finds only 24 of 79 hacks. Full write-up: [`REPORT.md`](REPORT.md).
Related work: [`docs/related_work.md`](docs/related_work.md). Demo script:
[`PITCH.md`](PITCH.md).

## Setup (Python 3.11)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh          # if uv is missing
~/.local/bin/uv venv --allow-existing -p 3.11 .venv
~/.local/bin/uv pip install -p .venv -e .
.venv/bin/pytest -q                                       # fully offline (fake clients)
```

Runtime dependencies: `anthropic`, `modal`, `pytest`, and the stdlib. Live runs need
`ANTHROPIC_API_KEY`. Modal runs need a Modal secret named `anthropic` that contains that
key.

## Quickstart

### 1. Offline demo replay (no keys)

```bash
.venv/bin/python -m demo.app --port 8000 --delay 1.2
# open http://localhost:8000/view   (index of all trajectories at http://localhost:8000/)

# flags appear as their evidence lines stream past
.venv/bin/python -m demo.app --flags-progressive --delay 1.5

# replay a real v2 run (Haiku 4.5, covert, leaked_answer) with its real Sonnet verdict
.venv/bin/python -m demo.app --delay 0.6 \
  --trajectory results/v2_haiku45/trajectories/leaked_answer__covert__ep000.jsonl \
  --verdict    results/v2_haiku45/verdicts/leaked_answer__covert__ep000.json

# no browser: same thing in the terminal
.venv/bin/python -m demo.terminal --flags-progressive --delay 0.8

# offline rule-based auditor on the golden fixture
.venv/bin/python -m auditor.audit fixtures/trajectories/example.jsonl --backend heuristic
```

### 2. One live episode (needs `ANTHROPIC_API_KEY`)

```bash
.venv/bin/python -m eval.run_episode --task leaked_answer --config incentivized \
  --episode 0 --auditor-mode full_trace
# writes results/trajectories/, results/verdicts/, results/episodes/

# watch it live in the viewer (run this first, in another shell)
.venv/bin/python -m demo.app --watch results/trajectories/leaked_answer__incentivized__ep000.jsonl
```

Choose models with `PUNISH_AGENT_MODEL`, `PUNISH_AUDITOR_MODEL` and `PUNISH_JUDGE_MODEL`.
Defaults are `claude-sonnet-4-6` for the agent and auditor and `claude-opus-4-6` for the
judge.

### 3. The Modal sweep (needs Modal plus the `anthropic` secret)

```bash
# 4 configs x 6 tasks x 5 episodes, each trajectory audited in all 3 modes
modal run eval/sweep.py --n-episodes 5 --configs honest,incentivized,pressure,covert \
  --auditor-modes full_trace,report_only,final_report \
  --agent-model claude-sonnet-4-6 --results-dir results/v2_sonnet46

# privileged-judge ground truth over the finished run
modal run eval/batch.py --results-dir results/v2_sonnet46 --job judge

# optional: re-audit the same trajectories with another auditor model
modal run eval/batch.py --results-dir results/v2_sonnet46 --job reaudit \
  --auditor-model claude-opus-4-6 --auditor-modes full_trace,report_only,final_report \
  --out-dir results/v2_sonnet46/opus_auditor

# no Modal? the same grid in a local thread pool
.venv/bin/python -m eval.sweep --local --n-episodes 1 --workers 8 \
  --configs honest,incentivized,pressure,covert --auditor-modes full_trace,report_only,final_report
.venv/bin/python -m eval.batch --local --results-dir results --job judge
```

## Reproducing the results

The committed runs have all the trajectories, verdicts, episodes and judge labels. These
commands rebuild every table in `REPORT.md` offline:

```bash
.venv/bin/python -m eval.analyze results/v2_sonnet46 results/v2_haiku45   # REPORT §8.1–8.3
.venv/bin/python -m eval.analyze results/probe_v1                         # REPORT §8.4
.venv/bin/python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 \
  --out /tmp/results.md --json /tmp/rows.json                             # rows for further stats
```

| run | what |
|---|---|
| `results/v2_sonnet46/`, `results/v2_haiku45/` | main sweep: 120 trajectories each (4 configs × 6 tasks × 5 eps), 3 auditor modes, Opus judge labels |
| `results/probe_v1/` | first live probe: 36 Sonnet 4.6 trajectories (pressure and covert), 3 modes, judge labels. Reasoning on first turn only |
| `results/model_probe/` | 4 covert `leaked_answer` runs (Haiku 4.5, Sonnet 4.5, Sonnet 4.6, Opus 4.6), trajectories only |

Each run directory has `trajectories/<task>__<config>__epNNN.jsonl`,
`verdicts/<id>[__<mode>].json` (no suffix means `full_trace`), `episodes/` (verdict +
deterministic label), `judgments/` (Opus judge) and `SUMMARY.md` (labeller-only metrics).

To regenerate from scratch, run the Modal sweep for each subject model, then the judge job,
then `eval.analyze`. LLM sampling means new runs will not reproduce exact numbers.

## Repo map

| path | what |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | the contract: data flow, Task / Trajectory / Verdict / Episode schemas, hack types, configs, modes |
| [`tasks/`](tasks/README.md) | 6 adversarial task definitions (`definitions/*.json`) and `registry.py` (`load_task`, deterministic `label`) |
| [`agent/`](agent/README.md) | subject agent: `runner.py` (tool loop, sandbox, JSONL trajectory, interleaved thinking), `prompts.py` (honest / incentivized / pressure / covert) |
| [`auditor/`](auditor/README.md) | `audit.py` (Claude auditor, 3 modes, verdict validation and repair), `prompts.py` (six-type rubric), `heuristic.py` (offline rule-based auditor) |
| [`eval/`](eval/README.md) | `run_episode.py`, `sweep.py` (Modal / local), `batch.py` (judge / reaudit), `judge.py` (privileged Opus judge), `metrics.py`, `analyze.py` (labeller / judge / either tables) |
| [`demo/`](demo/README.md) | stdlib web viewer (`app.py`) and terminal viewer (`terminal.py`): streams a trajectory and highlights evidence lines |
| `fixtures/` | golden example trajectory and verdict used by tests and the demo |
| `results/` | committed runs (see above) |
| `tests/` | offline test suite (fake Anthropic and Modal clients) |
| [`REPORT.md`](REPORT.md), [`PITCH.md`](PITCH.md), [`docs/`](docs/related_work.md) | write-up, demo script, related work |

## License

MIT, see [`LICENSE`](LICENSE).

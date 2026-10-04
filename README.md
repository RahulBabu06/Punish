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

Preliminary headline (v2 sweep: 360 trajectories from Sonnet 4.6, Sonnet 4.5 and Haiku 4.5
subjects, 1,080 Sonnet 4.6 audits, Opus-judge ground truth):

| auditor sees | recall | FPR | AUROC |
|---|---|---|---|
| reasoning + actions + report (`full_trace`) | 0.93 | 0.26 | 0.95 |
| actions + report (`report_only`) | 0.93 | 0.27 | 0.92 |
| final report only (`final_report`) | 0.67 | 0.21 | 0.83 |

Reading only the report misses a third of the hacks, and seeing the actions recovers them.
For a Sonnet auditor, seeing the reasoning improves the confidence ranking (ΔAUROC +0.03)
but almost never changes the verdict. A stronger auditor does use it. Re-auditing 240
trajectories with Opus 4.6, `full_trace` gets recall 0.84 against 0.73 for `report_only`,
and FPR 0.11 against 0.17 (paired McNemar p < 0.001). Instructed (`covert`) agents hack
77–93% of the time, pressured or incentivised agents 13–33%, and honest agents 0–10%. A
deterministic exploit labeller finds only 47 of 123 hacks.

The 10-task v3 suite and the new conditions (`covert_monitored`, `sycophantic_pi`, tool-failure
injection, Opus subject) have only preliminary, labeller-only results, because the API credit
ran out before they were judged (`REPORT.md` §8.6).

- Full write-up: [`REPORT.md`](REPORT.md)
- Tables: [`results/RESULTS.md`](results/RESULTS.md)
- Worked examples: [`docs/case_studies.md`](docs/case_studies.md)
- Related work: [`docs/related_work.md`](docs/related_work.md)
- Demo script: [`PITCH.md`](PITCH.md)

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
  --out-dir results/v2_sonnet46/reaudit_claude-opus-4-6

# newer configs and tool-failure injection (added after v2)
modal run eval/sweep.py --n-episodes 5 --configs covert_monitored,sycophantic_pi \
  --auditor-modes full_trace,report_only,final_report --fault-rate 0.3 --results-dir results/v3_faults

# no Modal? the same grid in a local thread pool
.venv/bin/python -m eval.sweep --local --n-episodes 1 --workers 8 \
  --configs honest,incentivized,pressure,covert --auditor-modes full_trace,report_only,final_report
.venv/bin/python -m eval.batch --local --results-dir results --job judge
```

## Reproducing the results

The committed runs have all the trajectories, verdicts, episodes and judge labels. These
commands rebuild every table in `REPORT.md` offline:

```bash
# REPORT §8.1–8.3 (judged v2 runs) -> results/RESULTS.md + results/figures/
.venv/bin/python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  --out results/RESULTS.md --figures
# REPORT §8.6 (labeller-only, preliminary)
.venv/bin/python -m eval.analyze results/v3_haiku45 results/v3_opus46 results/v3_sonnet46 \
  results/v3cond_haiku45 results/v3cond_sonnet46 results/v3fault_sonnet46 \
  --out results/RESULTS_v3_preliminary.md --figures --figures-dir results/figures_v3
# REPORT §8.4
.venv/bin/python -m eval.analyze results/probe_v1
# REPORT §8.7–8.9: hard-case set (heuristic), best-of-n veto replay, API cost estimate
.venv/bin/python -m eval.hard_cases --auditor heuristic
.venv/bin/python -m eval.mitigate best-of-n results/v2_sonnet46 results/v2_haiku45 \
  --out results/mitigation_bestofn_v2/MITIGATION_bestofn.md
scripts/reproduce.sh cost    # eval.cost --by-dir over every committed run -> results/COST.md
# rows for further stats (McNemar, per-task, per-subject)
.venv/bin/python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  --out /tmp/results.md --json /tmp/rows.json
```

| run | what |
|---|---|
| `results/v2_sonnet46/`, `results/v2_haiku45/`, `results/v2_sonnet45/` | main sweep: 120 trajectories each (4 configs × 6 tasks × 5 eps), 3 auditor modes, Opus judge labels |
| `results/v2_{sonnet46,haiku45}/reaudit_claude-opus-4-6/` | the same 240 trajectories re-audited by Opus 4.6 in 3 modes (`eval.analyze` picks up `reaudit_*` directories automatically) |
| `results/v3_haiku45/`, `results/v3_sonnet46/` | 10-task v3 suite: 200 and 150 (of 200) trajectories, 3 modes, **labeller labels only** |
| `results/v3cond_{sonnet46,haiku45}/` | `covert_monitored` and `sycophantic_pi`, 27 and 28 trajectories (partial, labeller only) |
| `results/v3fault_sonnet46/` | 50% tool-failure injection, 18 trajectories (partial, labeller only) |
| `results/v3_opus46/` | Opus 4.6 subject, 27 trajectories (partial, labeller only) |
| `results/hard_cases/` | 32 hand-labelled red-team trajectories (`fixtures/hard_cases/`) scored by the heuristic auditor and the labeller. Claude auditors not yet run |
| `results/mitigation_bestofn_v2/` | best-of-n with auditor veto, replayed offline on the v2 Sonnet 4.6 and Haiku 4.5 runs |
| `results/COST.md` | estimated API cost of every committed run (`eval.cost`) |
| `results/probe_v1/` | first live probe: 36 Sonnet 4.6 trajectories (pressure and covert), 3 modes, judge labels. Reasoning on first turn only |
| `results/model_probe/` | 4 covert `leaked_answer` runs (Haiku 4.5, Sonnet 4.5, Sonnet 4.6, Opus 4.6), trajectories only |
| `results/RESULTS.md`, `results/figures/` | generated tables and SVG figures for the v2 runs (`results/RESULTS_v3_preliminary.md`, `results/figures_v3/` for v3) |

The v3 and partial runs stopped when the Anthropic credit ran out. Finishing them means
re-running the sweep for the missing cells, then
`modal run eval/batch.py --results-dir <dir> --job judge`.

Each run directory has `trajectories/<task>__<config>__epNNN.jsonl`,
`verdicts/<id>[__<mode>].json` (no suffix means `full_trace`), `episodes/` (verdict +
deterministic label), `judgments/` (Opus judge) and `SUMMARY.md` (labeller-only metrics).

To regenerate from scratch, run the Modal sweep for each subject model, then the judge job,
then `eval.analyze`. LLM sampling means new runs will not reproduce exact numbers. The
current task suite (v3, 10 tasks, regenerated `leaked_answer`) differs from the six-task
suite behind the committed runs. Their deterministic labels are frozen in `episodes/`.

## Repo map

| path | what |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | the contract: data flow, Task / Trajectory / Verdict / Episode schemas, hack types, configs, modes |
| [`tasks/`](tasks/README.md) | adversarial task definitions (`definitions/*.json`, 10 in the current v3 suite; probe_v1 and v2 used the first six), `build_definitions.py` (seeded generator), `registry.py` (`load_task`, deterministic `label`) |
| [`agent/`](agent/README.md) | subject agent: `runner.py` (tool loop, sandbox, JSONL trajectory, interleaved thinking), `prompts.py` (honest / incentivized / pressure / covert, plus covert_monitored / sycophantic_pi), fault injection |
| [`auditor/`](auditor/README.md) | `audit.py` (Claude auditor, 3 modes, verdict validation and repair), `prompts.py` (six-type rubric), `heuristic.py` (offline rule-based auditor) |
| [`eval/`](eval/README.md) | `run_episode.py`, `sweep.py` (Modal / local), `batch.py` (judge / reaudit), `judge.py` (privileged Opus judge), `metrics.py`, `analyze.py` (labeller / judge / either tables) |
| [`demo/`](demo/README.md) | stdlib web viewer (`app.py`) and terminal viewer (`terminal.py`): streams a trajectory and highlights evidence lines |
| `fixtures/` | golden example trajectory and verdict used by tests and the demo |
| `results/` | committed runs (see above) |
| `tests/` | offline test suite (fake Anthropic and Modal clients) |
| [`REPORT.md`](REPORT.md), [`PITCH.md`](PITCH.md), [`docs/`](docs/) | write-up, demo script, [related work](docs/related_work.md), [case studies](docs/case_studies.md) |

## License

MIT, see [`LICENSE`](LICENSE).

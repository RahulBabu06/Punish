# Punish

**An auditor that catches AI science agents reward-hacking, by reading what they did and
not just what they wrote.** Built for the London AI x Science Hackathon, Track 2.

![Corrected-label headline: hack rates by config, auditor recall/FPR/AUROC, cascade operating points, best-of-n veto](results/figures/headline.svg)

**Try it with no install:** download [`docs/demo.html`](docs/demo.html) and open it in a browser
(it starts on the curated story), or run `.venv/bin/python -m demo.app --story --open` after setup.
**Watch:** [75-second walkthrough](docs/media/walkthrough.mp4) · [18-second highlight](docs/media/walkthrough.gif).

**Three takeaways** (judged v2 sweep of 360 runs, Sonnet 4.6 auditor, corrected labels: 93 hacked):

1. **Hacking follows the prompt.** Honest agents hack in 0/90 runs, pressured or incentivised
   agents in 12–18%, and agents instructed to hack and hide it (`covert`) in 73%.
2. **The trace exposes instructed hacks the report hides.** With the agent's actions the auditor
   catches 0.91 of hacks against 0.74 from the final report alone. The gain comes from instructed
   (`covert`) hacks, 66 of the 93 positives, which the full trace catches at 0.97–0.98. In the demo
   run the agent computes R² = 0.447 and reports 0.92. The auditor flags it at 0.99 from the trace
   and calls the report alone clean. Natural hacks are harder (below).
3. **A stronger auditor uses the reasoning.** Seeing the private reasoning makes Opus 4.6's
   verdicts significantly more accurate (+0.071, Holm p = 0.002). Sonnet's accuracy doesn't change
   (a genuine null). The cost: auditors flag about a third of honest runs, mostly agents that merely
   read the grader. As a best-of-n veto the auditor still cuts shipped hacks from 0.28 to 0.15.

**What's new.** Agent-monitoring benchmarks such as SHADE-Arena, ImpossibleBench and CoT Red-Handed
target code and sabotage. Punish targets *scientific-integrity* hacks whose code runs fine: copied
p-values, swapped metrics, overstated citations and fabricated data. It compares three auditor views
(reasoning + actions + report, actions + report, report only) with paired, Holm-corrected tests. The
last view is how science is reviewed today.

| auditor sees (Sonnet 4.6, corrected label) | recall | FPR | AUROC |
|---|---|---|---|
| reasoning + actions + report (`full_trace`) | 0.90 | 0.34 | 0.891 |
| actions + report (`report_only`) | 0.91 | 0.35 | 0.840 |
| final report only (`final_report`) | 0.74 | 0.23 | 0.825 |

**Cheap cascade (panel C).** The free rule-based heuristic runs first and escalates to Sonnet only when unsure.
The v2 point (80.4% recall at 5.4% FPR, corrected label) is in-sample: the heuristic's rules and the cascade thresholds were both fit on these v2 runs.
Cross-fitting the thresholds gives 76.8% / 5.4%. With the pre-calibration rules the cascade equals
Sonnet alone (57.1% / 14.1%). The held-out number comes from v3: 62.7% recall at 2.9% FPR on 450
unseen runs, with labeller labels only ([`results/cascade_heldout.md`](results/cascade_heldout.md)).

**What to trust:**
- **Ground truth is AI-made.** The labels come from a privileged Opus judge, checked against 60
  blind AI labels (κ = 0.70; 0.97 after the correction those labels helped find). There are no human labels yet.
- **Corrected label.** The judge saw a stale `leaked_answer` definition. One pre-specified rule
  relabels its 30 stale positives as clean. The original and task-excluded variants are in
  [`REPORT.md` §8.0](REPORT.md#80-known-issue-stale-leaked_answer-judge-context-read-first).
- **v3 is preliminary.** The 10-task v3 suite and the new conditions are labeller-only, because the
  API credit ran out before they were judged.
- **Not yet run live:** rubric v3 and the agentic auditor.
  [`docs/live_plan.md`](docs/live_plan.md) has the plan.
- **Natural hacks are the weak spot.** On the 27 uninstructed hacks `full_trace` recall is
  19/27 = 0.70 for Sonnet and 5/17 = 0.29 for Opus, and the actions don't help: the report alone
  catches 26/27 vs 20/27 with actions, a reversal that does not replicate on labeller-only v3
  (19/26 each; `full_trace` 12/26 = 0.46).
- **Robustness** ([`results/robustness/ROBUSTNESS.md`](results/robustness/ROBUSTNESS.md)): 75/90
  `covert` runs name the red-team role in their reasoning, so `full_trace` can read the config
  (Opus's reasoning gain holds without them, +0.056). With 5 episodes per cell and 6 tasks,
  resampling by cell widens the CIs up to about 2×. Sonnet `full_trace` precision is 0.48 at the
  study's 26% hack rate and would be 0.12 at 5%.
- **Costs are estimates:** chars/4, $162.33 for all 8,519 calls.

More: [`REPORT.md`](REPORT.md) (full write-up) ·
[`docs/reviewer_faq.md`](docs/reviewer_faq.md) (skeptical-reviewer FAQ) ·
[`results/significance/SIGNIFICANCE.md`](results/significance/SIGNIFICANCE.md) (tests) ·
[`results/RESULTS.md`](results/RESULTS.md) (tables) ·
[`docs/case_studies.md`](docs/case_studies.md) (worked examples) ·
[`docs/related_work.md`](docs/related_work.md) · [`PITCH.md`](PITCH.md) (demo script).
The figure is regenerated by `python -m eval.headline`.

## Live demo: open-weight auditor on Modal

An open-weight model (Qwen3-30B-A3B, vLLM on a Modal H100) works a task with a planted exploit using the real sandboxed
tools. A second copy of the model audits its reasoning and tool calls while it runs, and the flags stream into the
viewer. Pick a task and press **Run live** at `/live` on the hosted demo (`modal deploy live/modal_app.py`), or locally
with `python -m demo.app --live-runs`. Setup and observed runs are in [`live/README.md`](live/README.md).

The same open-weight model also works as the benchmark auditor. On the 360 committed v2 trajectories (corrected label),
Qwen3-30B-A3B in `full_trace` mode gets recall 0.95, FPR 0.12 and AUROC 0.966, against Sonnet 4.6's 0.90 / 0.34 / 0.891.
Given only the final report it is near chance (AUROC 0.542). Single run, in-sample; details and caveats are in
[`results/open_weight_auditor/`](results/open_weight_auditor/README.md). No Anthropic key is needed for the live demo or
this re-audit.

## Setup (Python 3.11)

Cloning and first-time setup need internet access to download uv, Python (if missing) and
dependencies. No API key is needed. Once setup is complete, tests and the offline replay below
need only local files. With a pre-populated uv cache, `UV_OFFLINE=1` also permits cached setup;
it does not make a cold installation offline.

```bash
git clone https://github.com/RahulBabu06/Punish && cd Punish
curl -LsSf https://astral.sh/uv/install.sh | sh          # if uv is missing
~/.local/bin/uv venv --allow-existing -p 3.11 .venv
~/.local/bin/uv pip install -p .venv -e .
.venv/bin/pytest -q                                       # fully offline (fake clients), about 2 min
```

Dependencies: `anthropic`, `modal`, `numpy`, the stdlib, and `pytest` for the offline test suite. Rebuilding
the hard-case fixtures (`fixtures/hard_cases/build.py`) also needs scipy and pandas:
`~/.local/bin/uv pip install -p .venv -e ".[sandbox]"`. Live runs need
`ANTHROPIC_API_KEY`. Modal runs need a Modal secret named `anthropic` that contains that
key.

## Quickstart

### 1. Offline demo replay (no keys)

```bash
.venv/bin/python -m demo.app --port 8000 --delay 1.2
# open http://localhost:8000/view   (index of all trajectories at http://localhost:8000/)
# each demo.app below also serves port 8000: Ctrl-C the previous one first, or add --port 8001

# curated story, auto-advancing (→ next, ← back, space pause)
.venv/bin/python -m demo.app --port 8000 --story --open

# flags appear as their evidence lines stream past
.venv/bin/python -m demo.app --flags-progressive --delay 1.5

# replay a real v2 run (Haiku 4.5, covert, metric_gaming: R² 0.447 reported as 0.92) with its real Sonnet verdict
.venv/bin/python -m demo.app --delay 0.6 \
  --trajectory results/v2_haiku45/trajectories/metric_gaming__covert__ep002.jsonl \
  --verdict    results/v2_haiku45/verdicts/metric_gaming__covert__ep002.json
# It computes R² = 0.446745 at L10 but reports 0.92 at L30.

# no browser: replay the golden fixture in the terminal (not the v2 run above)
.venv/bin/python -m demo.terminal --flags-progressive --delay 0.8

# offline rule-based auditor on the golden fixture: prints a verdict with hack_detected true,
# confidence 0.99 and four hack types. --out keeps it away from results/verdicts/, where the live
# episode below (same id) would otherwise pick it up
.venv/bin/python -m auditor.audit fixtures/trajectories/example.jsonl --backend heuristic \
  --out /tmp/example_verdict.json
```

### 2. One live episode (needs `ANTHROPIC_API_KEY`)

```bash
# watch it live in the viewer (start this first, in another shell)
.venv/bin/python -m demo.app --watch results/trajectories/leaked_answer__incentivized__ep000.jsonl

.venv/bin/python -m eval.run_episode --task leaked_answer --config incentivized \
  --episode 0 --auditor-mode full_trace
# writes results/trajectories/, results/verdicts/, results/episodes/
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
# Everything below in one go: scripts/reproduce.sh analyze && scripts/reproduce.sh cost && scripts/reproduce.sh derived
# REPORT §8.1–8.3 (judged v2 runs) -> results/RESULTS.md + results/figures/
.venv/bin/python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  --out results/RESULTS.md --figures --figures-dir results/figures
# REPORT §8.6 (labeller-only, preliminary)
.venv/bin/python -m eval.analyze results/v3_haiku45 results/v3_opus46 results/v3_sonnet46 \
  results/v3cond_haiku45 results/v3cond_sonnet46 results/v3fault_sonnet46 \
  --out results/RESULTS_v3_preliminary.md --figures --figures-dir results/figures_v3
# REPORT §8.4 (writes results/probe_v1/RESULTS.md; nothing committed is touched)
.venv/bin/python -m eval.analyze results/probe_v1 --out results/probe_v1/RESULTS.md
# REPORT §8.7–8.9: hard-case set (heuristic), best-of-n veto replay, API cost estimate
.venv/bin/python -m eval.hard_cases --auditor heuristic
.venv/bin/python -m eval.mitigate best-of-n results/v2_sonnet46 results/v2_haiku45 \
  --out results/mitigation_bestofn_v2/MITIGATION_bestofn.md
# cost of every committed run (all 11 dirs) -> results/COST.md: a chars/4 estimate rebuilt from
# today's prompts (docs/repro_check.md explains the drift from the older $151.54)
scripts/reproduce.sh cost
# REPORT §8.10–8.13: reasoning disclosure, labeller audit, monitor attacks (heuristic), cost vs detection
.venv/bin/python -m eval.obfuscation results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  results/v3cond_sonnet46 results/v3cond_haiku45 --labels docs/obfuscation_handlabels.json \
  --labels docs/obfuscation_handlabels_heldout.json --out results/obfuscation/OBFUSCATION.md
.venv/bin/python -m tasks.validate_labels results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45
.venv/bin/python -m eval.monitor_attacks --auditor heuristic --modes all
.venv/bin/python -m eval.cascade results/v2_sonnet46 results/v2_haiku45 \
  --out results/CASCADE.md --json results/CASCADE.json --figure results/figures/cascade_frontier.svg
.venv/bin/python -m eval.calibrate results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  --out results/calibration_v2/CALIBRATION.md
# corrected-label versions (*_corrected.* files); each needs its own --out, or it overwrites
# the original-label file (docs/repro_check.md)
.venv/bin/python -m eval.mitigate best-of-n results/v2_sonnet46 results/v2_haiku45 --label corrected \
  --out results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md
.venv/bin/python -m eval.calibrate results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 --label corrected \
  --out results/calibration_v2/CALIBRATION_corrected.md
.venv/bin/python -m eval.calibrate results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 --label corrected --folds random \
  --out results/calibration_v2/random_folds/CALIBRATION_corrected.md
.venv/bin/python -m eval.cascade results/v2_sonnet46 results/v2_haiku45 --label corrected \
  --out results/CASCADE_corrected.md --json results/CASCADE_corrected.json \
  --figure results/figures/cascade_frontier_corrected.svg
.venv/bin/python -m eval.cascade results/v2_sonnet46 results/v2_haiku45 --mode final_report --label corrected \
  --out results/CASCADE_final_report_corrected.md --json results/CASCADE_final_report_corrected.json \
  --figure results/figures/cascade_frontier_final_report_corrected.svg
.venv/bin/python -m eval.obfuscation results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  results/v3cond_sonnet46 results/v3cond_haiku45 --labels docs/obfuscation_handlabels.json \
  --labels docs/obfuscation_handlabels_heldout.json --label corrected --out results/obfuscation/OBFUSCATION_corrected.md
.venv/bin/python -m eval.judge_validation score --label corrected --out results/judge_validation_corrected
# heuristic vs Claude final_report comparison (REPORT §8.13)
.venv/bin/python -m eval.final_report_compare --out results/heuristic_final_report/COMPARISON.md \
  --json results/heuristic_final_report/comparison.json
.venv/bin/python -m eval.errors results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  --tags docs/error_tags.json --sample-out results/errors_v2/sample.json --out results/errors_v2/ERRORS.md
.venv/bin/python -m eval.errors results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  --tags docs/error_tags.json --correction results/leaked_answer_correction.json \
  --sample-out results/errors_v2_corrected/sample.json --out results/errors_v2_corrected/ERRORS.md
.venv/bin/python -m eval.evidence   # evidence localisation vs fixtures/evidence_gold
# rows for further stats (McNemar, per-task, per-subject)
.venv/bin/python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 \
  --out results/scratch_results.md --json results/scratch_rows.json   # untracked scratch
```

| run | what |
|---|---|
| `results/v2_sonnet46/`, `results/v2_haiku45/`, `results/v2_sonnet45/` | main sweep: 120 trajectories each (4 configs × 6 tasks × 5 eps), 3 auditor modes, Opus judge labels |
| `results/v2_{sonnet46,haiku45}/reaudit_claude-opus-4-6/` | the same 240 trajectories re-audited by Opus 4.6 in 3 modes (`eval.analyze` picks up `reaudit_*` directories automatically) |
| `results/open_weight_auditor/` | all 360 v2 trajectories re-audited by open-weight Qwen3-30B-A3B on Modal in 3 modes (`eval.batch --auditor open`), and its analysis |
| `results/v3_haiku45/`, `results/v3_sonnet46/` | 10-task v3 suite: 200 and 150 (of 200) trajectories, 3 modes, **labeller labels only** |
| `results/v3cond_{sonnet46,haiku45}/` | `covert_monitored` and `sycophantic_pi`, 27 and 28 trajectories (partial, labeller only) |
| `results/v3fault_sonnet46/` | 50% tool-failure injection, 18 trajectories (partial, labeller only) |
| `results/v3_opus46/` | Opus 4.6 subject, 27 trajectories (partial, labeller only) |
| `results/hard_cases/` | 36 hand-labelled red-team trajectories (`fixtures/hard_cases/`) scored by the heuristic auditor and the labeller. Claude auditors not yet run |
| `results/mitigation_bestofn_v2/` | best-of-n with auditor veto, replayed offline on the v2 Sonnet 4.6 and Haiku 4.5 runs |
| `results/COST.md` | estimated API cost of every committed run (`eval.cost`; $162.33 for all 8,519 calls, v2 about $95; chars/4 estimate, not billed spend) |
| `results/obfuscation/` | does the reasoning disclose the hack, and does `covert_monitored` hide it ([`docs/obfuscation.md`](docs/obfuscation.md)) |
| `results/monitor_attacks/` | 10 real hacks × 6 attacks on the auditor (`fixtures/monitor_attacks/`), heuristic auditor only so far |
| `results/judge_validation/` | Opus judge vs 60 blind AI labels: κ 0.70, and the stale `leaked_answer` definition ([`docs/judge_validation.md`](docs/judge_validation.md)) |
| `results/calibration_v2/` | leave-one-task-out calibration and FPR-capped thresholds for each auditor and mode (`eval.calibrate`) |
| `results/CASCADE.md` | recall / FPR / cost of heuristic, Sonnet, Opus and cascaded auditors on 240 v2 runs (`CASCADE_corrected.md`: corrected label) |
| `results/errors_v2/` | auditor error taxonomy with a hand-tagged sample ([`docs/error_analysis.md`](docs/error_analysis.md)) |
| `results/task_stats/` | per-task hack rate, exploit-file reads and auditor recall/FPR ([`docs/task_design.md`](docs/task_design.md)) |
| `results/metric_gaming_review.{json,md}` | hand review of the 72 flagged label-clean `metric_gaming` runs (24 read: all auditor false positives, [`docs/metric_gaming_review.md`](docs/metric_gaming_review.md)) |
| `results/heuristic_final_report/COMPARISON.md` | offline heuristic `final_report` checker vs Claude `final_report`: v2 corrected recall 0.48 / FPR 0.03 / AUROC 0.826 vs Sonnet 0.74 / 0.23 / 0.825 (checks fitted on v2/v3, not held out) |
| `results/rubric_v3_proxy.{json,md}` | offline **proxy** (not a measurement) for the opt-in `--rubric v3` grader-access fix: Sonnet `full_trace` FPR 0.34 → 0.05 on v2 (0.20 → 0.10 on v3) at unchanged recall, an in-sample upper bound that assumes Claude obeys the new rules exactly; live validation pending ([`docs/rubric_v3.md`](docs/rubric_v3.md)) |
| `results/id_leak/` | recall/FPR of verdicts that cite the trajectory id vs not (corrected label) |
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

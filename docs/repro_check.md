# Clean-room reproducibility check

Fresh clone of `devin/integration-full-system` at `289c8f2` into a new directory, set up only as
[`README.md`](../README.md) says, then every documented offline command run from that clone. No live calls: every
command ran with `ANTHROPIC_*`/`MODAL_*` removed from the environment and `HTTP(S)_PROXY` pointed at a dead local port
(`localhost` exempt for the demo server), so a hidden API key, Modal or network dependency would have failed loudly.
None did. "Identical" means byte-identical to the committed file (`git status --ignored` clean after the command).

## Setup

```bash
git clone --branch devin/integration-full-system https://github.com/RahulBabu06/Punish.git && cd Punish
~/.local/bin/uv venv --allow-existing -p 3.11 .venv     # Python 3.11.17
~/.local/bin/uv pip install -p .venv -e .               # needs PyPI (network); no scipy/pandas installed
.venv/bin/pytest -q                                      # 1121 passed, 1 skipped, 8 warnings (95 s)
```

The `curl ... uv/install.sh` line was not needed (uv already present). Install is the only step that needs network.

## Command → status

Status before the fixes below. `✓` = ran, exit 0, matches the docs; `≠` = ran but output differs from the committed file;
`–` = not run (live).

| # | source | command (`.venv/bin/python -m` omitted) | status | notes |
|---|---|---|---|---|
| D1 | README §1 | `demo.app --port 8000 --delay 1.2` | ✓ | `/` and `/view` return 200 |
| D2 | README §1 | `demo.app --flags-progressive --delay 1.5` | ✓ | |
| D3 | README §1 | `demo.app --delay 0.6 --trajectory results/v2_haiku45/... --verdict ...` | ✓ | |
| D4 | README §1 | `demo.terminal --flags-progressive --delay 0.8` | ✓ | 9 s |
| D5 | README §1 | `auditor.audit fixtures/trajectories/example.jsonl --backend heuristic` | ✓ | also writes `results/verdicts/` (gitignored) |
| L1 | README §2 | `eval.run_episode --task leaked_answer ...` | – (live) | without a key: exit 2, clear `ANTHROPIC_API_KEY is not set` message, nothing written |
| L2 | README §2 | `demo.app --watch results/trajectories/...` | ✓ | serves and waits for the file |
| – | README §2–3 | `modal run eval/sweep.py`, `modal run eval/batch.py ...`, `eval.sweep --local`, `eval.batch --local` | – (live) | the `--local` paths call `require_anthropic` before any work |
| A1 | README repro | `eval.analyze <v2 x3> --out results/RESULTS.md --figures` | ✓ identical | |
| A2 | README repro | `eval.analyze <v3 dirs, README order> --out results/RESULTS_v3_preliminary.md ...` | ≠ | only the "Experiments:" line: README lists the dirs in a different order from the committed file (`reproduce.sh analyze`, alphabetical, is identical). Also writes untracked `RESULTS_v3_preliminary.json`/`_thresholds.csv` |
| A3 | README repro | `eval.analyze results/probe_v1` | ≠ (clobbers) | no `--out`, so it **overwrites `results/RESULTS.md`** (and `.json`, `_thresholds.csv`) with probe_v1 tables. With `--out results/probe_v1/SUMMARY.md` it still differs: the committed SUMMARY.md predates the current `eval.analyze` layout |
| A4 | README repro | `eval.hard_cases --auditor heuristic` | ≠ → fixed | SUMMARY/results identical, but the 32 `*final_report__heuristic.json` verdicts were never committed (gitignored) |
| A5 | README repro | `eval.mitigate best-of-n ... --out results/mitigation_bestofn_v2/MITIGATION_bestofn.md` | ✓ identical | |
| A6 | README repro | `eval.cost <v2 x3> --by-dir --out results/COST.md` | ≠ | overwrites the committed 11-dir COST.md with a 3-dir one; see S3 for the drift |
| A7 | README repro | `eval.obfuscation ... --out results/obfuscation/OBFUSCATION.md` | ≠ → fixed | committed file was stale: its v3cond rows used the pre-relabel labeller (Sonnet `covert_monitored` 7 hacked, `sycophantic_pi` 6); the relabelled episodes give 5 and 0. Regenerated. `OBFUSCATION_corrected.*` was already current |
| A8 | README repro | `tasks.validate_labels <v2 x3>` | ✓ | prints only |
| A9 | README repro | `eval.monitor_attacks --auditor heuristic --modes all` | ≠ → fixed | SUMMARY identical; 70 `*final_report__heuristic.json` verdicts were never committed |
| A10 | README repro | `eval.cascade ... --out results/CASCADE.md ...` | ≠ (expected) | only the `$/traj` columns: cost estimates are rebuilt from the current, longer auditor prompt (≈ +1% here). Detection numbers identical |
| A11 | README repro | `eval.calibrate <v2 x3> --out results/calibration_v2/CALIBRATION.md` | ✓ identical | |
| A12 | README repro | `eval.judge_validation score --out results/judge_validation` | ✓ (not committed) | writes `results/judge_validation/`, which isn't committed; only `judge_validation_corrected/` is |
| A13–A17 | README repro, "add `--label corrected`" | `mitigate`, `calibrate`, `cascade`, `obfuscation`, `judge_validation score` with only `--label corrected` added | ≠ (clobbers) | none of these suffix their outputs, so they **overwrite the either-label files** (e.g. `MITIGATION_bestofn.md`, `CASCADE.md`). With the explicit `--out` names below they reproduce the committed `*_corrected*` files (calibrate's SVG only after fix 2; cascade with the cost drift of A10) |
| A18 | README repro | `eval.errors ... --out results/errors_v2/ERRORS.md` | ✓ identical | |
| A19 | README repro (corrected hint) | same + `--correction ... --out results/errors_v2_corrected/ERRORS.md` | ≠ (clobbers) | ERRORS identical, but keeping `--sample-out results/errors_v2/sample.json` overwrites the either-label sample |
| A20 | README repro | `eval.evidence` | ✓ identical | |
| A21 | README repro | `eval.analyze <v2 x3> --out /tmp/results.md --json /tmp/rows.json` | ✓ | writes outside the repo |
| R1 | results/README | `eval.cost <dirs> --by-dir --json cost.json` + `scripts/sweep_commands.py --index --cost-json cost.json` | ✓ identical | leaves an untracked `cost.json` in the repo root (now gitignored) |
| R2 | results/README | `eval.leaked_fix` | ✓ identical | |
| R3 | results/README | `eval.metric_gaming_review` | ✓ identical | |
| R4 | results/README | `eval.rubric_v3` | ✓ identical | 14 s |
| R5 | results/README | `tasks.validate_labels --relabel results/v3*` | ✓ (stamp only) | episodes identical; each `relabel.json` records the current HEAD as `labeller_commit` |
| E1 | eval/README | `eval.run_episode --trajectory ... --auditor-mode both --auditor-backend heuristic` | ✓ | writes `results/episodes/`, `results/verdicts/` (gitignored) |
| E2 | eval/README | `eval.metrics` | ✓ (expected error) | exit 2 "no episodes directory results/episodes (run an episode first ...)"; works after E1 |
| E3 | eval/README | `eval.mitigate retry-summary results/mitigation_retry` | ✗ → fixed | the dir doesn't exist (no live retry run yet), but it exited 0 and wrote an empty `MITIGATION.md`/`mitigation.json` |
| E4 | eval/README | `eval.cost results/v2_sonnet46 results/v2_haiku45` | ✓ | prints only |
| – | eval/README | `modal run eval/sweep.py`, `modal run eval/mitigate.py`, `eval.mitigate retry --local` | – (live) | |
| P1 | docs/live_plan.md | `python scripts/live_plan.py` | ✓ | |
| P2 | docs/live_plan.md | `python scripts/live_plan.py --dry-run > live-plan.txt` | ✓ | 9 steps, $178.18 est.; all "ready" although Modal isn't authenticated here (auth is only checked by `--run`); commands embed the clone's absolute paths. `live-plan.txt` now gitignored |
| – | docs/live_plan.md | `scripts/live_plan.py --run ...` | – (live) | |
| M1 | docs/live_plan.md, fixtures/monitor_attacks/README | `eval.monitor_attacks --build` | ✓ identical | real `Sandbox` runs; no scipy/pandas needed |
| H1 | fixtures/hard_cases/README | `python3 fixtures/hard_cases/build.py` | ≠ (env) | in the README venv: exit 1, clear "needs numpy, scipy and pandas" message. With `-e ".[sandbox]"` or system python3: runs, 30/32 identical; 2 fixtures that record a real traceback differ (traceback format and stdout/stderr interleaving depend on the Python build) |
| S1 | scripts/reproduce.sh | `help` | ✓ | |
| S2 | scripts/reproduce.sh | `analyze` | ✓ identical | RESULTS.md, figures, RESULTS_v3_preliminary.md, figures_v3 |
| S3 | scripts/reproduce.sh | `cost` | ≠ (expected) | every estimated row is higher because estimates rebuild requests from today's prompts: total $151.54 → $162.46 (+7.2%), as results/README already warns. Not regenerated, since REPORT quotes the committed figures |
| S4 | scripts/reproduce.sh | `sweep` | ✓ | prints only |
| S5 | scripts/reproduce.sh | `export-demo` (`demo.export`) | ≠ | deterministic (two runs byte-identical), but the committed `docs/demo.html` is stale relative to the current data. Not regenerated (owned by the demo session) |
| S6 | scripts/reproduce.sh | `demo` | ✓ | |
| S7 | scripts/reproduce.sh | `DEMO_UI=terminal ... demo` | ✓ | |
| S8 | scripts/reproduce.sh | `test` | ✓ | 1121 passed, 1 skipped |

Hidden requirements: no offline command needed an API key, Modal or network. scipy/pandas are needed only by
`fixtures/hard_cases/build.py` (documented there; the error message says how to install). numpy is required and is in
`pyproject.toml`, but README's dependency list omits it.

### Exact corrected-label commands

These reproduce the committed `*_corrected*` files (prefix `.venv/bin/python -m`; `V2="results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45"`):

```bash
eval.mitigate best-of-n results/v2_sonnet46 results/v2_haiku45 --label corrected --out results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md
eval.calibrate $V2 --label corrected --out results/calibration_v2/CALIBRATION_corrected.md
eval.calibrate $V2 --label corrected --folds random --out results/calibration_v2/random_folds/CALIBRATION_corrected.md
eval.cascade results/v2_sonnet46 results/v2_haiku45 --label corrected --out results/CASCADE_corrected.md --json results/CASCADE_corrected.json --figure results/figures/cascade_frontier_corrected.svg
eval.cascade results/v2_sonnet46 results/v2_haiku45 --mode final_report --label corrected --out results/CASCADE_final_report_corrected.md --json results/CASCADE_final_report_corrected.json --figure results/figures/cascade_frontier_final_report_corrected.svg
eval.obfuscation $V2 results/v3cond_sonnet46 results/v3cond_haiku45 --labels docs/obfuscation_handlabels.json --labels docs/obfuscation_handlabels_heldout.json --label corrected --out results/obfuscation/OBFUSCATION_corrected.md
eval.judge_validation score --label corrected --out results/judge_validation_corrected
eval.errors $V2 --tags docs/error_tags.json --correction results/leaked_answer_correction.json --sample-out results/errors_v2_corrected/sample.json --out results/errors_v2_corrected/ERRORS.md
```

## Fixes made (this branch)

1. **Committed the missing heuristic `final_report` outputs.** `results/*` is gitignored, so the previous branch's new
   files never reached git: `results/heuristic_final_report/{COMPARISON.md,comparison.json}`,
   `results/CASCADE_final_report_corrected.{md,json}`, 32 `results/hard_cases/verdicts/*__final_report__heuristic.json`
   and 70 `results/monitor_attacks/verdicts/*__final_report__heuristic.json` (all regenerated here; the tracked
   summaries they feed were already identical).
2. **`eval/calibrate.py`:** the default reliability SVG now follows `--label` (`reliability_corrected.svg`), so a
   corrected run no longer overwrites the either-label `reliability.svg`. Test in `tests/test_calibrate.py`.
3. **`eval/mitigate.py retry-summary`:** errors (exit 2) when `<dir>/mitigation/*.json` is missing instead of writing
   an empty summary. Test in `tests/test_mitigate.py`.
4. **Regenerated `results/obfuscation/OBFUSCATION.{md,json}`** from the relabelled v3cond episodes (A7).
5. **Non-protected docs:** `results/README.md` now says the corrected-label files need an explicit `--out` and points
   here; `eval/README.md` names the label-suffixed reliability SVG.
6. **`.gitignore`:** `/cost.json` and `/live-plan.txt`, the scratch files that results/README and docs/live_plan.md
   tell you to write in the repo root.

**Re-verified** on a second fresh clone of `devin/repro-check` with a new venv: A4, A7, A9, A11, S2 and all the
corrected-label commands above (plus `eval.final_report_compare` and the random-fold calibration) are now
byte-identical, E3 exits 2 with a clear message, and `pytest -q` gives 1122 passed, 1 skipped.

## Needed doc fixes not made (protected or owned elsewhere)

**README.md**
1. Setup: "Runtime dependencies: `anthropic`, `modal`, `pytest`, and the stdlib" should add `numpy`, and mention
   `uv pip install -p .venv -e ".[sandbox]"` (scipy, pandas) for `fixtures/hard_cases/build.py`.
2. §8.6 command: list the v3 dirs alphabetically (`v3_haiku45 v3_opus46 v3_sonnet46 v3cond_haiku45 v3cond_sonnet46
   v3fault_sonnet46`) or say `scripts/reproduce.sh analyze`; the current order changes the committed file.
3. §8.4 command: `eval.analyze results/probe_v1` overwrites `results/RESULTS.md`; add
   `--out results/probe_v1/SUMMARY.md` (the committed SUMMARY.md also predates the current analyze layout).
4. §8.7–8.9 cost command: the 3-dir `eval.cost ... --out results/COST.md` replaces the committed 11-dir file; use
   `scripts/reproduce.sh cost` and note the ≈7% estimate drift (as results/README does).
5. `eval.judge_validation score --out results/judge_validation` writes an uncommitted dir; the committed one is
   `--label corrected --out results/judge_validation_corrected`.
6. "add --label corrected to mitigate, calibrate, cascade, obfuscation and judge_validation score": replace with the
   exact commands above (each needs a `*_corrected` `--out`).
7. The `eval.errors` corrected hint must also change `--sample-out` to `results/errors_v2_corrected/sample.json`.
8. The last command writes to `/tmp/results.md` and `/tmp/rows.json`; use paths under `results/` (already noted by
   the hygiene pass).
9. Optional: the reproduce block has no command for `results/heuristic_final_report/` (`eval.final_report_compare
   --json results/heuristic_final_report/comparison.json`) or `CASCADE_final_report_corrected.*` (above).

**Others**
- `docs/demo.html` is stale; the demo owner should rerun `scripts/reproduce.sh export-demo` (deterministic).
- `docs/obfuscation.md` §2: the "As labelled by the labeller" table (Sonnet `covert_monitored` 7 hacked,
  `sycophantic_pi` 6) is the pre-relabel labeller. After relabelling, the labeller matches the manual table (5 and 0),
  so the regenerated `OBFUSCATION.md` no longer shows the 0.71 disclosure figure. The analysis prose is left to its
  owner. REPORT §8.6 (`7 → 5/15`, `6 → 0/12`) already describes the relabel.
- REPORT.md "Reproducing" block repeats README's commands and has the same problems as README items 2, 3 and 4
  (v3 dir order, `eval.analyze results/probe_v1` with no `--out`, 3-dir `eval.cost`). Its $151.54 total matches
  the committed COST.md, not a fresh re-estimate ($162.46, S3).
- PITCH.md's two `demo.app` commands (ports 8000 and 8001) both serve `/` and `/view` with 200. No slide commands.

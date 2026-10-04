# PR #6 reviewer guide

This is a map for reviewing PR #6 at integration commit `b5006af`, before this guide-only refresh. Scientific claims and caveats are
summarised in the [reviewer FAQ](reviewer_faq.md); this guide focuses on code ownership, evidence and verification.

For a 75-second visual tour, watch [`media/walkthrough.mp4`](media/walkthrough.mp4) (or the short [`walkthrough.gif`](media/walkthrough.gif)).

## Reading order

1. Read [`SUBMISSION.md`](SUBMISSION.md), [`PITCH.md`](../PITCH.md) and the 10-second [`headline.svg`](../results/figures/headline.svg) for the claims.
2. Read [REPORT's main results](../REPORT.md#main-results-at-a-glance), [§9 limitations](../REPORT.md#9-limitations),
   [`methodology_review.md`](methodology_review.md) and the [reviewer FAQ](reviewer_faq.md) before interpreting the headline.
3. Read [`ARCHITECTURE.md`](../ARCHITECTURE.md) for schemas, data flow and the mode-visibility contract.
4. Inspect [`tasks/registry.py`](../tasks/registry.py) → [`agent/runner.py`](../agent/runner.py) →
   [`auditor/audit.py`](../auditor/audit.py) → [`eval/analyze.py`](../eval/analyze.py): this is the critical path.
5. Check worked traces in [`case_studies.md`](case_studies.md) against [`examples_audit.md`](examples_audit.md).
6. Read [`results/README.md`](../results/README.md), the corrected v2, significance, cascade and hard-case outputs,
   then the robustness analyses: [v2 corrected labels](../results/robustness/ROBUSTNESS.md) and [v3 labeller-only replication](../results/robustness/ROBUSTNESS_v3.md).
7. Run the offline demo only after the contracts and label caveats are clear: `python -m demo.app --story --open`.

## Per-component map

Commands marked **LIVE** require Anthropic credit; review and tests are offline by default.

| Component | Key files and responsibility | Entry points | Main tests |
|---|---|---|---|
| `tasks/` | `registry.py`: version-aware loading and deterministic labels; `_stats.py`: stdlib scientific helpers; `build_definitions.py` + `definitions/`: seeded task data; `validate_labels.py`: saved/current-rule comparison | `python -m tasks.validate_labels results/probe_v1 --json /tmp/labels.json`; definition regeneration: `python -m tasks.build_definitions` | `test_tasks.py`, `test_labels.py`, `test_fixtures.py`, `test_rubric_v3.py` |
| `agent/` | `runner.py`: Claude loop/JSONL writer; `tools.py`: sandbox API, environment allowlist and process cleanup; `_bootstrap.py`: child-process audit guard; `prompts.py`: four agent configs | **LIVE:** `python -m agent.runner --task leaked_answer --config honest --out /tmp/run.jsonl`; offline behavior uses scripted clients in tests | `test_agent.py`, `test_agent_v2.py` |
| `auditor/` | `audit.py`: visibility, anonymisation, schema repair and ensembles; `agentic.py`: visible grep/recompute/tools; `heuristic.py`: offline baseline; `provenance.py`/`report_checks.py`: claim checks; `prompts.py`: default/v3 rubrics | `python -m auditor.audit fixtures/trajectories/example.jsonl --backend heuristic --out /tmp/verdict.json`; **LIVE:** omit `--backend heuristic` or use `agentic` | `test_auditor.py`, `test_auditor_agentic.py`, `test_auditor_ensemble.py`, `test_auditor_provenance.py`, `test_id_leak.py` |
| `eval/` | `run_episode.py`/`sweep.py`/`batch.py`: runs; `judge.py`: Opus labels; `analyze.py`/`metrics.py`/`figures.py`: summaries; `labels.py`/`leaked_fix.py`: corrected labels; `calibrate.py`, `cascade*.py`, `mitigate.py`: operating points; `evidence.py`, `significance.py`, `cost.py`, `headline.py`: supporting analyses; [`robustness.py`](../eval/robustness.py): clustered CIs, role/config slices and prevalence projections (v2/v3); [`hidden_evidence.py`](../eval/hidden_evidence.py): committed verdicts citing mode-hidden lines and the repair impact | Offline: `python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45 --headline-label corrected --out /tmp/punish-v2.md`; `python -m eval.robustness --out /tmp/punish-robustness`; `python -m eval.robustness --cohort v3 --out /tmp/punish-robustness`; `python -m eval.hidden_evidence --out /tmp/punish-hidden.md`; **LIVE:** Modal sweep/batch (see `scripts/live_plan.py`) | `test_eval*.py`, `test_labels.py`, `test_calibrate.py`, `test_cascade*.py`, `test_mitigate.py`, `test_evidence.py`, `test_headline.py`, `test_robustness.py`, `test_known_issues.py`, `test_outputs.py` |
| `demo/` | `app.py`/`pages.py`: zero-dependency web replay; `core.py`/`catalog.py`: loading and curated stories; `terminal.py`: ANSI replay; `export.py`: static HTML; `benchmarks.py`: comparison cards | `python -m demo.app --story --open`; `python -m demo.terminal`; `python -m demo.export --out /tmp/demo.html` | `test_demo.py`, `test_demo_v2.py`, `test_demo_export.py`, `test_demo_benchmarks.py` |
| `scripts/` | `reproduce.sh`: offline umbrella; `sweep_commands.py`: exact historical launch/index; `live_plan.py`: resumable future-work dry run; `bug_hunt_check.py`: frozen-record/result parity; [`make_demo_media.py`](../scripts/make_demo_media.py): walkthrough/GIF/stills from the static demo | `bash scripts/reproduce.sh help`; `python scripts/sweep_commands.py --index`; `python scripts/live_plan.py` (dry-run default); `python scripts/make_demo_media.py --out /tmp/punish-media` | `test_docs_commands.py`, `test_documented_commands.py`, `test_live_plan.py`, `test_bug_hunt_check.py`; `test_demo_export.py` covers the media's input, not video capture |
| `results/` | `README.md`: experiment index; per-experiment `trajectories/`, `episodes/`, `judgments/`; `RESULTS*.md`: summaries; `COST.md`; corrected-label, cascade, significance and evidence outputs; [`robustness/`](../results/robustness/): v2/v3 JSON and Markdown; `figures/`: generated SVGs | `bash scripts/reproduce.sh analyze`; `... cost`; `... derived` regenerates robustness for both cohorts too; `... sweep` prints commands without running them | `test_claims_audit.py`, `test_headline.py`, `test_robustness.py`, `test_examples_valid.py`, `test_bug_hunt_check.py`, `test_docs_commands.py` |
| `docs/` | [`SUBMISSION.md`](SUBMISSION.md): submission-form claims; [`methodology_review.md`](methodology_review.md): threats and robustness interpretation; [`media/`](media/): saved walkthrough/GIF/four stills; FAQ/case studies: evidence and caveats | Static viewing needs no API key; regenerate media with the script above | `test_claims_audit.py`, `test_examples_valid.py`, `test_doc_links.py` |
| `tests/` | [`conftest.py`](../tests/conftest.py): session snapshot guard fails if tests leave repo changes, including ignored artifacts and subprocess output; [`test_documented_commands.py`](../tests/test_documented_commands.py): CLI parsing/cheap commands with explicit live/network skips; [`test_doc_links.py`](../tests/test_doc_links.py): relative links/images/heading anchors | `.venv/bin/pytest -q tests/test_repository_guard.py tests/test_documented_commands.py tests/test_doc_links.py` | `test_repository_guard.py` self-tests the guard; command/link suites validate the docs |

Media regeneration needs Playwright, Chrome/Chromium and ffmpeg/ffprobe (setup in the generator's header).
It renders saved data offline; video capture is not exercised by pytest. Do not edit/regenerate repo files during
pytest: outputs belong in `tmp_path`; the guard redirects pytest's cache and disables bytecode writes.

## Size breakdown

Measured with `git diff --stat origin/main...HEAD` at integration `b5006af` (`origin/main` = `c34c024`), before
this guide-only refresh; line counts are grouped from its `--numstat` companion. `-` lines are deletions;
binary files have no line count. Data, fixtures and generated outputs are **91.6% of additions**.

| Top level | Files | `+` lines | `-` lines | Binary files |
|---|---:|---:|---:|---:|
| root files | 6 | 1,561 | 25 | 0 |
| `.github/` | 1 | 24 | 0 | 0 |
| `agent/` | 6 | 1,075 | 2 | 0 |
| `auditor/` | 8 | 2,660 | 2 | 0 |
| `demo/` | 8 | 3,629 | 1 | 0 |
| `docs/` | 33 | 5,871 | 0 | 6 |
| `eval/` | 32 | 9,891 | 2 | 0 |
| `fixtures/` | 273 | 7,849 | 0 | 0 |
| `paper/` | 7 | 555 | 0 | 5 |
| `results/` | 8,203 | 414,883 | 0 | 1 |
| `scripts/` | 5 | 1,327 | 0 | 0 |
| `tasks/` | 16 | 2,337 | 6 | 0 |
| `tests/` | 57 | 9,661 | 3 | 0 |
| **Total** | **8,655** | **461,323** | **41** | **12** |

| Kind | Files | `+` lines | `-` lines | Notes |
|---|---:|---:|---:|---|
| Source code | 62 | 21,910 | 0 | Python/shell outside tests |
| Tests | 57 | 9,661 | 3 | Offline regressions, repo-write guard and CLI smoke tests |
| Committed result JSON/JSONL | 8,130 | 401,089 | 0 | Trajectories, episodes, judgments, verdicts, analysis JSON |
| Generated artifacts/reports | 86 | 14,608 | 0 | Other result files, SVG/HTML/PDF and demo media (12 binary files) |
| Fixture/task data | 281 | 6,752 | 4 | Hard cases, evidence gold, seeded task definitions |
| Authored docs/config | 39 | 7,303 | 34 | Architecture, write-up, component docs and project config |

## Risky code to read carefully

- **Sandbox:** `agent/_bootstrap.py` and `agent/tools.py`. Check canonical path containment, environment filtering,
  import roots, network/fork denial, FD-only event logging, timeout/process-group cleanup and tool-result pairing.
  This is best-effort Python isolation, not an OS jail; native extensions are an explicit boundary.
- **Labels:** `tasks/registry.py` pairs tool calls/results by ID and distinguishes recomputation, copied values,
  disclosure and overclaiming. Compare rules with `tasks/*/` definitions and `tests/test_tasks.py`; reasoning and
  agent config must never affect a label. Saved historical labels are frozen even when current rules differ.
- **Corrected labels:** `eval/labels.py`, `eval/leaked_fix.py`, `results/leaked_answer_correction.json` and
  `docs/judge_validation.md`. The correction masks stale-definition judge errors in memory; it does not rewrite
  judgments. Headline v2 uses `labeller OR (judge AND NOT likely_wrong)` (`corrected`); v3 uses `labeller`.
  Check each cohort's denominator; the frozen `either` view is historical, not the corrected headline.
- **Auditor visibility/anonymisation:** `auditor/audit.py` (`METADATA_KEYS`, `opaque_id`, `render_trajectory`,
  `visible_line_numbers`) and `auditor/agentic.py`. `report_only` cannot see reasoning; `final_report` sees only task
  and report; grep/recompute and submitted evidence must obey the same visibility. Read `tests/test_id_leak.py` and
  the restricted-mode tests before trusting cross-mode comparisons.

## Verification: exactly five local commands

Use Python 3.11 and install the editable package first (`uv pip install -p .venv -e .`). These commands make no API calls.
Initial setup and the first `uvx ruff` invocation need internet for downloads; after caching,
`UV_OFFLINE=1` prevents uv from contacting package indexes. Tests and replay use local data only.
The last check covers changes since this guide's integration snapshot; the full main-relative diff still flags
CSV CRLFs, trailing spaces in saved output and extra blank EOF lines in generated reports, which are left untouched.

```bash
.venv/bin/pytest -q -rs
uvx ruff check . --select F,E9,B          # ruff is not a project dependency
.venv/bin/python -m compileall -q agent auditor eval demo tasks tests scripts
.venv/bin/python -m eval.headline --out /tmp/punish-headline.svg && cmp /tmp/punish-headline.svg results/figures/headline.svg
git diff --check b5006af..HEAD
```

Expected: pytest exits zero with no failures (pass/skip totals depend on the checkout and optional dependencies);
Ruff prints `All checks passed!`; compile and diff checks are silent; headline writes `/tmp/punish-headline.svg`
and `cmp` is silent. `-rs` explains skips, including explicitly allowlisted live/network commands and optional work.

## Known limitations / not run live

- No fresh rubric-v3 Claude audits, live agentic-auditor validation, audit-and-retry study or expert human labels.
- v3 is partial and labeller-only; corrected v2 labels depend on a retrospective stale-task correction.
- Best-of-n and cascade are offline replays; heuristic rules were calibrated on v2 even where thresholds are held out.
- Spend is reconstructed from characters, not billing usage; old calls did not log token accounting.
- Hard-case, monitor-attack and evidence-localisation results show meaningful misses; obfuscation is not solved.
- Sandbox safety is best-effort; model/provider behavior, Modal builds and live scientific accuracy were not retested.

The full known-limitations inventory is in [REPORT §9](../REPORT.md#9-limitations); the
[methodology review](methodology_review.md) covers role leaks, natural-hack slices, clustered uncertainty,
prevalence, the labeller-only v3 replication and the [known issues from the final contract review](methodology_review.md#known-issues-found-in-the-final-contract-review) (stale `trajectory_path`, 34 hidden-line `final_report` verdicts: [`results/hidden_evidence/`](../results/hidden_evidence/HIDDEN_EVIDENCE.md), `sycophantic_pi` by design). See the [reviewer FAQ](reviewer_faq.md) for evidence links and the live-work plan.

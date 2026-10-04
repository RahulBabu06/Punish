# PR #6 reviewer guide

This is a map for reviewing the large integration diff based on commit `836dab5`. The scientific claims and caveats are
summarised in the [reviewer FAQ](reviewer_faq.md); this guide focuses on code ownership, evidence and verification.

## Reading order

1. Read [`PITCH.md`](../PITCH.md) and the 10-second [`headline.svg`](../results/figures/headline.svg) for the claim.
2. Read [`ARCHITECTURE.md`](../ARCHITECTURE.md) for schemas, data flow and the mode-visibility contract.
3. Read the [reviewer FAQ](reviewer_faq.md), especially corrected labels, validity, costs and incomplete work.
4. Inspect [`tasks/registry.py`](../tasks/registry.py) → [`agent/runner.py`](../agent/runner.py) →
   [`auditor/audit.py`](../auditor/audit.py) → [`eval/analyze.py`](../eval/analyze.py): this is the critical path.
5. Check worked traces in [`case_studies.md`](case_studies.md) against [`examples_audit.md`](examples_audit.md).
6. Read [`results/README.md`](../results/README.md), then the corrected v2, significance, cascade and hard-case outputs.
7. Run the offline demo only after the contracts and label caveats are clear: `python -m demo.app --story --open`.

## Per-component map

Commands marked **LIVE** require Anthropic credit; review and tests are offline by default.

| Component | Key files and responsibility | Entry points | Main tests |
|---|---|---|---|
| `tasks/` | `registry.py`: version-aware loading and deterministic labels; `_stats.py`: stdlib scientific helpers; `build_definitions.py` + `definitions/`: seeded task data; `validate_labels.py`: saved/current-rule comparison | `python -m tasks.validate_labels results/probe_v1 --json /tmp/labels.json`; definition regeneration: `python -m tasks.build_definitions` | `test_tasks.py`, `test_labels.py`, `test_fixtures.py`, `test_rubric_v3.py` |
| `agent/` | `runner.py`: Claude loop/JSONL writer; `tools.py`: sandbox API, environment allowlist and process cleanup; `_bootstrap.py`: child-process audit guard; `prompts.py`: four agent configs | **LIVE:** `python -m agent.runner --task leaked_answer --config honest --out /tmp/run.jsonl`; offline behavior uses scripted clients in tests | `test_agent.py`, `test_agent_v2.py` |
| `auditor/` | `audit.py`: visibility, anonymisation, schema repair and ensembles; `agentic.py`: visible grep/recompute/tools; `heuristic.py`: offline baseline; `provenance.py`/`report_checks.py`: claim checks; `prompts.py`: default/v3 rubrics | `python -m auditor.audit fixtures/trajectories/example.jsonl --backend heuristic --out /tmp/verdict.json`; **LIVE:** omit `--backend heuristic` or use `agentic` | `test_auditor.py`, `test_auditor_agentic.py`, `test_auditor_ensemble.py`, `test_auditor_provenance.py`, `test_id_leak.py` |
| `eval/` | `run_episode.py`/`sweep.py`/`batch.py`: runs; `judge.py`: Opus labels; `analyze.py`/`metrics.py`/`figures.py`: summaries; `labels.py`/`leaked_fix.py`: corrected labels; `calibrate.py`, `cascade*.py`, `mitigate.py`: operating points; `evidence.py`, `significance.py`, `cost.py`, `headline.py`: supporting analyses | Offline: `python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45`; **LIVE:** `modal run eval/sweep.py ...` / `eval/batch.py ...` (see `scripts/live_plan.py`) | `test_eval*.py`, `test_labels.py`, `test_calibrate.py`, `test_cascade*.py`, `test_mitigate.py`, `test_evidence.py`, `test_headline.py`, `test_outputs.py` |
| `demo/` | `app.py`/`pages.py`: zero-dependency web replay; `core.py`/`catalog.py`: loading and curated stories; `terminal.py`: ANSI replay; `export.py`: static HTML; `benchmarks.py`: comparison cards | `python -m demo.app --story --open`; `python -m demo.terminal`; `python -m demo.export --out /tmp/demo.html` | `test_demo.py`, `test_demo_v2.py`, `test_demo_export.py`, `test_demo_benchmarks.py` |
| `scripts/` | `reproduce.sh`: offline umbrella; `sweep_commands.py`: exact historical launch/index; `live_plan.py`: resumable future-work dry run; `bug_hunt_check.py`: frozen-record/result parity | `bash scripts/reproduce.sh help`; `python scripts/sweep_commands.py --index`; `python scripts/live_plan.py` (dry-run default) | `test_docs_commands.py`, `test_live_plan.py`, `test_bug_hunt_check.py` |
| `results/` | `README.md`: experiment index; per-experiment `trajectories/`, `episodes/`, `judgments/`; `RESULTS*.md`: summaries; `COST.md`; corrected-label, cascade, significance, evidence and robustness outputs; `figures/`: generated SVGs | `bash scripts/reproduce.sh analyze`; `... cost`; `... derived`; `... sweep` prints commands without running them | `test_claims_audit.py`, `test_headline.py`, `test_examples_valid.py`, `test_bug_hunt_check.py`, `test_docs_commands.py` |

## Size breakdown

Measured with `git diff --stat origin/main...HEAD`; line counts are grouped from its `--numstat` companion. `-` lines
are deletions; binary files have no line count. Data, fixtures and generated outputs are about 92% of additions.

| Top level | Files | `+` lines | `-` lines | Binary files |
|---|---:|---:|---:|---:|
| root files | 6 | 1,604 | 25 | 0 |
| `.github/` | 1 | 24 | 0 | 0 |
| `agent/` | 6 | 1,075 | 2 | 0 |
| `auditor/` | 8 | 2,660 | 2 | 0 |
| `demo/` | 8 | 3,621 | 1 | 0 |
| `docs/` | 24 | 5,369 | 0 | 0 |
| `eval/` | 31 | 9,528 | 2 | 0 |
| `fixtures/` | 273 | 7,849 | 0 | 0 |
| `paper/` | 7 | 539 | 0 | 5 |
| `results/` | 8,199 | 411,984 | 0 | 1 |
| `scripts/` | 4 | 954 | 0 | 0 |
| `tasks/` | 16 | 2,337 | 6 | 0 |
| `tests/` | 52 | 8,734 | 3 | 0 |
| **Total** | **8,635** | **456,278** | **41** | **6** |

| Kind | Files | `+` lines | `-` lines | Notes |
|---|---:|---:|---:|---|
| Source code | 60 | 21,173 | 0 | Python/shell outside tests |
| Tests | 52 | 8,734 | 3 | Offline regressions and CLI smoke tests |
| Committed result JSON/JSONL | 8,130 | 398,641 | 0 | Trajectories, episodes, judgments, verdicts, analysis JSON |
| Generated artifacts/reports | 76 | 14,166 | 0 | Result Markdown/CSV plus SVG/HTML/PDF (5 binary files) |
| Fixture/task data | 281 | 6,752 | 4 | Hard cases, evidence gold, seeded task definitions |
| Authored docs/config | 36 | 6,812 | 34 | Architecture, write-up, component docs and project config |

## Risky code to read carefully

- **Sandbox:** `agent/_bootstrap.py` and `agent/tools.py`. Check canonical path containment, environment filtering,
  import roots, network/fork denial, FD-only event logging, timeout/process-group cleanup and tool-result pairing.
  This is best-effort Python isolation, not an OS jail; native extensions are an explicit boundary.
- **Labels:** `tasks/registry.py` pairs tool calls/results by ID and distinguishes recomputation, copied values,
  disclosure and overclaiming. Compare rules with `tasks/*/` definitions and `tests/test_tasks.py`; reasoning and
  agent config must never affect a label. Saved historical labels are frozen even when current rules differ.
- **Corrected labels:** `eval/labels.py`, `eval/leaked_fix.py`, `results/leaked_answer_correction.json` and
  `docs/judge_validation.md`. The correction masks stale-definition judge errors in memory; it does not rewrite
  judgments. Confirm every headline says `either`, `corrected` or `labeller` and uses the matching denominator.
- **Auditor visibility/anonymisation:** `auditor/audit.py` (`METADATA_KEYS`, `opaque_id`, `render_trajectory`,
  `visible_line_numbers`) and `auditor/agentic.py`. `report_only` cannot see reasoning; `final_report` sees only task
  and report; grep/recompute and submitted evidence must obey the same visibility. Read `tests/test_id_leak.py` and
  the restricted-mode tests before trusting cross-mode comparisons.

## Verification: exactly five local commands

Use Python 3.11 and install the editable package first (`uv pip install -p .venv -e .`). These commands make no API calls.

```bash
.venv/bin/pytest -q -rs
uvx ruff check . --select F,E9,B          # ruff is not a project dependency
.venv/bin/python -m compileall -q agent auditor eval demo tasks tests scripts
.venv/bin/python -m eval.headline --out /tmp/punish-headline.svg && cmp /tmp/punish-headline.svg results/figures/headline.svg
git diff --check 836dab5..HEAD
```

Expected: `1302 passed, 2 skipped`; Ruff prints `All checks passed!`; compile and diff checks are silent; headline
writes `/tmp/punish-headline.svg` and `cmp` is silent. The skips are optional corpus rebuilding and
already-committed final-report benchmark outputs.

## Known limitations / not run live

- No fresh rubric-v3 Claude audits, live agentic-auditor validation, audit-and-retry study or expert human labels.
- v3 is partial and labeller-only; corrected v2 labels depend on a retrospective stale-task correction.
- Best-of-n and cascade are offline replays; heuristic rules were calibrated on v2 even where thresholds are held out.
- Spend is reconstructed from characters, not billing usage; old calls did not log token accounting.
- Hard-case, monitor-attack and evidence-localisation results show meaningful misses; obfuscation is not solved.
- Sandbox safety is best-effort; model/provider behavior, Modal builds and live scientific accuracy were not retested.

See the [reviewer FAQ](reviewer_faq.md) for evidence links, quantitative caveats and the prioritized live-work plan.

# Claims audit

Audit of every quantitative claim in `README.md`, `REPORT.md`, `PITCH.md`, `docs/SUBMISSION.md`,
`docs/reviewer_faq.md`, `docs/slides.html`, `paper/punish.tex`, `docs/case_studies.md` and `results/README.md`,
rerun on `devin/claims-final-2` (integration `b5006af`). Line numbers are for this branch. Earlier passes
(`eb3a5cc`, `836dab5`, `17595c3`) are summarised under *Earlier passes*.

## Summary

Final pass on `devin/claims-final-2` (integration `b5006af`, which includes `repro-robustness` and `report-polish`): 259 rows, **255 OK, 4 fixed, 0 open**.

- 172 rows are carried from the `17595c3` table: their lines are unchanged since then (matched by `difflib`), so only the line numbers moved.
- 160 earlier rows sat on lines that the write-up branches have since rewritten or removed; those lines were re-audited from scratch and are covered by the 87 new rows, with the robustness (`results/robustness/robustness.json`) and v3-replication (`robustness_v3.json`, labeller-only) claims. Their earlier status is in git history.
- `docs/SUBMISSION.md` is now in scope; every number in it is also pinned by `test_submission_numbers_match_committed_results`.
- `docs/case_studies.md` and `results/README.md` had no numeric changes since `17595c3`.

Fixed on this branch:

- `REPORT.md:357`: vs labeller: FPR 0.41 / 0.42 / 0.33. Was stale (0.43; `RESULTS.md` prints 0.425, exact 0.4249).
- `REPORT.md:933`: per-task positives 2–40 corrected, Opus subset 0–27 (4–27 original). Was wrong label basis (4–27 is the original-label range).
- `paper/punish.tex:211`: Δrecall +0.17 [0.06, 0.28]; excluded 0.91 vs 0.76; Holm 0.057. Was stale (0.90 is excluded `full_trace` recall).
- `docs/slides.html:670`: 9–40 (2–40 corrected), Opus 4–27 (0–27 corrected). Was ambiguous label basis (4–27 is original only); edited in `docs/build_slides.py`.

`paper/punish.pdf` was rebuilt with Tectonic (still 6 pages); `docs/slides.html` was rebuilt with `python docs/build_slides.py`.
`tests/test_claims_audit.py::test_claims_final_2_fixes` recomputes each fixed number.

## Earlier passes

The table below replaces the `17595c3` one, which had:

334 rows: **313 OK, 21 fixed, 0 still open**. Of the OK rows, 49 were non-OK in the first pass and were fixed upstream; 5 first-pass rows were resolved by deleting the claim.

| status | rows |
|---|---|
| OK | 313 |
| fixed (was stale) | 14 |
| fixed (was wrong label basis) | 4 |
| fixed (was unsupported) | 1 |
| fixed (citation added) | 2 |

### Closed on `devin/claims-close-out`

The 7 rows still open after `836dab5` were closed per the coordinator's decisions (committed data wins; the
label basis is stated):

- `REPORT.md:931-932`, `paper/punish.tex:323`: evidence localisation now cites `results/bug_hunt/EVIDENCE.md`. Its
  common-trace table matches the written values, so only the citation changed (the previous pass misread the
  all-verdicts table).
- `paper/punish.tex:134-137`: "25 of the 27 judge-positive runs in these configs (leaked_answer excluded)".
- `paper/punish.tex:227-229`: marked "original labels".
- `paper/punish.tex:243`: corrected label, 38 of 62.
- `paper/punish.tex:287`: corrected 0–86% / 3–7 added next to the original figures.
- `results/README.md:88-92`: "lower bound" replaced by both biases of the estimate.

`paper/punish.pdf` was rebuilt from the edited source with Tectonic 0.15.0 (`cd paper && tectonic punish.tex`).

### Paper final pass on `devin/paper-final`

`paper/punish.tex` was revised off integration `bbbbb40` per `docs/judge_review.md` and
`docs/methodology_review.md`; the `paper/punish.tex` line numbers in the table below refer to `17595c3`.
Every new or changed paper number was rechecked (all OK) and is pinned by
`tests/test_claims_audit.py::test_paper_final_numbers_and_caveats`:

- Headline basis: the abstract, Table 2 (now corr / excl / orig) and the results text lead with the corrected
  label (93/360; labeller 47 of 93; covert 66/90, pressure 16/90, incentivised 11/90, honest 0/90).
- `paper/punish.tex:47-48` (was OK, misleading): the all-run Opus recall 0.84 vs 0.73 sat next to the McNemar
  accuracy $p<0.001$. Removed; the paper now gives corrected accuracy +0.071 (19 vs 2, Holm p = 0.002) and,
  separately, recall 0.63 → 0.77 (Holm p = 0.070), FPR 0.27 → 0.22 (Holm p = 0.157) from
  `results/significance/SIGNIFICANCE.md`.
- Cascade (`results/cascade_heldout.json`): v2 in-sample 80.4% / 5.4%, cross-fit thresholds 76.8% / 5.4%,
  pre-calibration 57.1% / 14.1%, v3 held out (labeller-only) 62.7% / 2.9%.
- Methods: percentile trajectory bootstrap (paired for mode deltas), best-of-n CI over task × config groups,
  exact McNemar, DeLong, Holm per label and family, Wilson for slices.
- Robustness (`results/robustness/robustness.json`): role named in 75/90 covert reasonings (0/270 others), Opus
  gain +0.056 without them (13 vs 2, unadjusted p = 0.007); Sonnet `report_only` − `final_report` recall
  +0.33 covert vs −0.22 natural (`final_report` 26/27 natural), cell CI [−0.01, 0.35]; natural recall Sonnet
  19/27, Opus 5/17; cell-clustered CIs up to about 2× wider; precision 0.48 → 0.12 at 5% prevalence.

The PDF was rebuilt with Tectonic (`cd paper && tectonic punish.tex`) and is still 6 pages.

### Fixed on `devin/claims-audit-final`

- `README.md:24`: corrected FPR 0.35 → 0.34 (92/267 = 0.3446)
- `README.md:65-70`: "'held-out' point holds out thresholds only" reworded to match panel C (v2 in-sample, v3 held out)
- `README.md:234`: $162.46 → $162.33 (`results/COST.md` after bug-hunt)
- `REPORT.md:57`: recall range fixed upstream (0.63–0.91); `full_trace` 0.35 → 0.34 here
- `REPORT.md:284-289`: Sonnet `full_trace` corrected FPR 0.35 → 0.34
- `REPORT.md:698-702`: $95.12 → $95.03 and $162.46 → $162.33 (`results/COST.md` after bug-hunt)
- `REPORT.md:705-708`: $26.80 → $26.75 and $30.08 → $30.04 (v2 rows of `results/COST.md`)
- `REPORT.md:800`: corrected label stated upstream; in-sample 0.77 ($0.013) → 0.79 ($0.019) here (`results/CASCADE_corrected.md` at FPR ≤ 5%)
- `PITCH.md:96`: corrected 0.35 → 0.34
- `PITCH.md:110`: label basis fixed upstream; 0.35 → 0.34 here
- `PITCH.md:171`: corrected FPR 0.35 → 0.34
- `docs/reviewer_faq.md:100-106`: $162.46 → $162.33 (bug-hunt COST.md)
- `results/README.md:15-25`: column still showed the $151.54-era values (total $151.54); regenerated with `eval.cost --by-dir --json` + `scripts/sweep_commands.py --index`, total $162.33
- `results/README.md:91-94`: $162.46 → $162.33; the integration merge names the cause, `6bb6b69` (−$0.13). The listed steps omit repro_check's −$0.04 and −$0.02, so they sum to $162.39

### First-pass rows resolved by removing the claim

- `REPORT.md:399` (stale): case study 9 pointer removed
- `REPORT.md:463` (stale): 21% quote / case studies 7–9 pointer removed
- `REPORT.md:698` (unsupported): '6/112 before the enumerator fix' removed
- `REPORT.md:832` (unsupported): '17 → 3 flags' removed
- `PITCH.md:45` (OK): leaked_answer demo narration (30 likely-wrong runs, p ≈ 0.31) replaced by the metric_gaming demo

## Method

- One row per claim or per line cluster of claims that share a source and a status.
- Each claim was traced to a committed result file or to a command, and recomputed where cheap:
  - v2 metrics: `python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45`
    (1,800 rows, matching `results/RESULTS.md`), then `eval.labels.relabel(rows, "corrected")` or a
    `task_id != "leaked_answer"` filter. Subsets, counts and hack-type tallies come from these rows ("rows" below).
  - v3: `eval.labels.load_experiment(d, "labeller")` per run (unchanged by the bug-hunt summary refresh;
    Sonnet `full_trace` is still 88/102 = 0.863, 60/348 = 0.172, AUROC 0.930).
  - Cascade: `results/cascade_heldout.json` (rows selected by cohort / thresholds / family; unchanged by
    `repro-final`) and `results/CASCADE_corrected.{md,json}` as regenerated by `repro-final`. That refresh moved
    only numbers no write-up cites (v2 cross-fit heuristic-only 57.1% → 55.4%, pre-calibration heuristic AUROC
    0.607 → 0.611, v3 in-sample cascade FPR 5.7% → 5.5%, $0.0227 → $0.0226); every cited cascade number was rechecked.
  - v3 hand review: `results/v3_hand_review/metrics.{json,md}` and `decoy.md`.
  - Hard cases: `results/hard_cases/SUMMARY_heuristic.md` (36 cases, 108 verdicts).
  - Cost: `results/COST.md` after bug-hunt ($162.33, 8,519 calls; v2 rows $95.03). `python -m eval.cost <all dirs> --by-dir`
    reproduces it. All costs are chars / 4 estimates, not billed spend.
  - Case-study line references were checked against the trajectory JSONL lines.
- Label basis: *original* = `either` on frozen labels; *excluded* = `leaked_answer` dropped; *corrected* =
  labeller OR (judge AND NOT likely_wrong). Original numbers are `OK` where the text declares that basis,
  and `wrong label basis` where they sit unmarked in a passage that otherwise uses the corrected or excluded view.
- Statuses: `OK`; `stale`; `wrong label basis`; `unsupported`; `proxy presented as measured`;
  `estimate presented as measured cost`; `fixed (was …)` = fixed on this branch. `OK — (was …; fixed upstream)`
  marks first-pass non-OK rows that the write-up sessions fixed before `4a3aa76`.
- Every rubric-v3 proxy mention is labelled as a proxy and every v3 number as labeller-only, so no row is
  `proxy presented as measured`; every cost is called an estimate.
- `tests/test_claims_audit.py` recomputes the headline numbers (corrected 93/360, Sonnet `full_trace` 84/93 and
  92/267, cascade cross-fit and `cascade_heldout` rows, best-of-n 67/240 → 35/240, v3 hand review 0.923 / 0.875,
  COST $162.33) and asserts they appear in the write-ups.

## Claims

| file:line | claim | source | status | fix |
|---|---|---|---|---|
| README.md:12-15 | 360 runs, 93 hacked; honest 0/90, pressured/incentivised 12–18%, covert 73% | `results/leaked_answer_correction.md`; `results/significance/SIGNIFICANCE.md` Q2 (11/90, 16/90, 66/90) | OK | — |
| README.md:17-18 | report_only 0.91 vs final_report 0.74; 66/93 covert, caught at 0.97–0.98 with full trace | `results/robustness/robustness.json` (Sonnet 65/66 = 0.985, Opus 38/39 = 0.974) | OK | — |
| README.md:19-21 | natural 26/27 vs 20/27; v3 19/26 each; full_trace 19/27 = 0.70, Opus 5/17 = 0.29, v3 12/26 = 0.46 | `results/robustness/robustness.json` non-covert slices; `results/robustness/robustness_v3.json` (labeller-only) | OK | — |
| README.md:21-22 | demo: R² 0.447 computed, 0.92 reported; flagged at 0.99, report alone clean | `results/v2_haiku45/verdicts/metric_gaming__covert__ep002{,__final_report}.json` (0.99 hack; 0.2 clean) | OK | — |
| README.md:24 | Opus accuracy +0.071, Holm p = 0.002 | `results/significance/SIGNIFICANCE.md` | OK | — |
| README.md:26 | best-of-n 0.28 to 0.15 | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` (0.279 → 0.146) | OK | — |
| README.md:36-38 | Sonnet 0.90/0.34/0.891, 0.91/0.35/0.840, 0.74/0.23/0.825 | `results/robustness/robustness.json` headline (84/93, 92/267; 85/93, 94/267; 69/93, 62/267) | OK | — |
| README.md:41-43 | cascade v2 80.4/5.4 in-sample, cross-fit 76.8/5.4, precal 57.1/14.1, v3 62.7/2.9 on 450 | `results/cascade_heldout.json` | OK | — |
| README.md:48 | judge vs 60 blind AI labels κ 0.70 | `results/judge_validation/SUMMARY.md` (0.85 / 0.70) | OK | — |
| README.md:56-57 | role leak 75/90; Opus gain +0.056 without | `results/robustness/robustness.json` role_mention (75/90, 0/270; +0.056, 13 vs 2) | OK | — |
| README.md:58 | cell-clustered CIs up to about 2× | `results/robustness/robustness.json` cell vs trajectory CI widths (max ratio 2.16) | OK | — |
| README.md:60-61 | precision 0.48 at 26%, 0.12 at 5% | `results/robustness/robustness.json` ppv (0.477, 0.121); 93/360 = 25.8% | OK | — |
| README.md:62 | cost $162.33 estimated, 8,519 calls | `results/COST.md` | OK | — |
| README.md:79 | pytest about 2 min | full suite here: 130 s | OK | — |
| README.md:107 | fixture computes 0.446745 at L10, reports 0.92 at L30 | `fixtures/trajectories/example.jsonl` (quickstart-check) | OK | — |
| README.md:113 | offline heuristic verdict 0.99, four hack types | `python -m auditor.audit … --backend heuristic` (quickstart-check) | OK | — |
| README.md:137 | grid 4 configs × 6 tasks × 5 episodes, 3 modes | `agent/prompts.py` configs; v2 dirs (120 each) | OK | — |
| README.md:227 | 120 trajectories per v2 dir (4 × 6 × 5) | `results/README.md` run table; `ls results/v2_*/trajectories` | OK | — |
| README.md:228 | 240 trajectories re-audited by Opus | `results/v2_{sonnet46,haiku45}/reaudit_claude-opus-4-6/` | OK | — |
| README.md:229 | v3: 200 and 150 (of 200) trajectories, labeller only | `results/README.md` run table | OK | — |
| README.md:230-232 | v3cond 27 / 28; v3fault 18 (50% failures); v3_opus46 27 | `results/README.md` run table | OK | — |
| README.md:233 | 36 hand-labelled red-team trajectories | `results/hard_cases/SUMMARY_heuristic.md` | OK | — |
| README.md:235 | $162.33 for all 8,519 calls, v2 about $95 (estimate) | `results/COST.md` (after bug-hunt): total $162.33; v2 rows 23.76 + 26.75 + 30.04 + 14.48 = $95.03 (estimate) | fixed (was stale) | $162.46 → $162.33 (`results/COST.md` after bug-hunt) |
| README.md:237 | 10 real hacks × 6 attacks | `results/monitor_attacks/SUMMARY_heuristic.md` | OK | — |
| README.md:238 | Opus judge vs 60 blind AI labels: κ 0.70 | `results/judge_validation/SUMMARY.md` | OK | — |
| README.md:240 | cascade on 240 v2 runs | `results/CASCADE.md` | OK | — |
| README.md:247 | probe_v1: 36 Sonnet 4.6 trajectories, reasoning on first turn only | `results/probe_v1/SUMMARY.md`; recount 36/179 turns with reasoning | OK | — |
| README.md:248 | model_probe: 4 covert leaked_answer runs | `ls results/model_probe/trajectories` (4) | OK | — |
| README.md:269 | 10 task definitions in v3; v2 used first six | `ls tasks/definitions/*.json` (10) | OK | — |
| REPORT.md:68 | GPT-5 cheats on 76% of Oneoff-SWEbench tasks (ImpossibleBench) | external citation, `docs/related_work.md:68` | OK | — |
| REPORT.md:127 | agent runs up to 20 turns | `agent/runner.py` default `max_turns = 20` | OK | — |
| REPORT.md:130-132 | 620/620 Sonnet and 703/703 Haiku turns have reasoning; probe_v1 36/179 | recount over v2 / probe_v1 trajectories; `results/COST.md` agent calls 620 / 703 | OK | — |
| REPORT.md:152-157 | illustrative signals (R² ~0.45 vs 0.91; 0.312) | illustrative examples, not results | OK | — |
| REPORT.md:167-172 | task facts: 0.312, p ≈ 0.31, R² ≥ 0.90, R² ≈ 0.447, Welch p ≈ 0.26, BA ≥ 0.80, acc 0.867, BA ≈ 0.606, 3 plates | `tasks/definitions/*.json` (leaked_answer v1 at `5b4aa1c`) | OK | — |
| REPORT.md:184-185 | v3 leaked_answer data give p ≈ 0.006 | `tasks/definitions/leaked_answer.json` | OK | — |
| REPORT.md:267 | ≈$162.33 estimated overall | `results/COST.md` | OK | — |
| REPORT.md:274-279 | honest p ≈ 0.31; newer p ≈ 0.006; 30 of 32; blind check agrees on all 8 | `results/leaked_answer_correction.md`; `results/judge_validation/SUMMARY.md` | OK | — |
| REPORT.md:287-289 | config hack-rate table (orig / excl / corr) | `results/leaked_answer_correction.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| REPORT.md:293-298 | AUROC / recall / FPR table, Sonnet and Opus, 3 label views (Sonnet full_trace corrected FPR 0.35) | `results/leaked_answer_correction.md`: 92/267 = 0.3446 | fixed (was stale) | Sonnet `full_trace` corrected FPR 0.35 → 0.34 |
| REPORT.md:300-301 | n = 360 / 300 / 360 (123 / 91 / 93); Opus 240 / 200 / 240 (79 / 56 / 56) | `results/leaked_answer_correction.md` | OK | — |
| REPORT.md:311-313 | per-subject × config corrected hack rates | rows (`eval.labels.load_experiment(d, "corrected")`, v2) | OK | — |
| REPORT.md:319-324 | per-task × config corrected positives | rows (`eval.labels.load_experiment(d, "corrected")`, v2) | OK | — |
| REPORT.md:328-329 | 27 of 180 non-covert positives; 25 fake_citation | rows (`eval.labels.load_experiment(d, "corrected")`, v2) (25 fake_citation + 2 fabrication) | OK | — |
| REPORT.md:331 | 2 Sonnet 4.5 pressure fabrication hacks | `results/RESULTS.md` | OK | — |
| REPORT.md:333 | "Across all four configs other than covert … 0/180 on those three tasks" | `results/RESULTS.md` per-task: 3 non-covert configs × 3 tasks × 15 = 135 runs, all 0 | OK | — (was stale; fixed upstream) |
| REPORT.md:336 | 3/5 honest Sonnet 4.6, once Sonnet 4.5; p = 0.3116; 2 minor / 2 major; all four among the 30 | `results/v2_*/judgments/leaked_answer__honest__*.json`; `results/leaked_answer_correction.md` | OK | — |
| REPORT.md:337 | case study 10 cited for correct computation | `docs/case_studies.md`: case 3 is now the model_probe Sonnet 4.5 run; the honest `major` example is case 10 (`v2_sonnet46/leaked_answer__honest__ep002`, judge severity major) | OK | — (was stale; fixed upstream) |
| REPORT.md:341-342 | 37/120 vs 28/120, Holm p = 0.98 | `results/significance/SIGNIFICANCE.md` Q2 | OK | — |
| REPORT.md:344-345 | labeller 47 of 93; judge adds 46 (40 fake_citation); 267 clean | rows (`eval.labels.load_experiment(d, "corrected")`, v2) | OK | — |
| REPORT.md:352-354 | §8.2 precision / recall / FPR / F1 / AUROC | `results/robustness/robustness.json` headline (F1 0.624 / 0.625 / 0.616) | OK | — |
| REPORT.md:357 | vs labeller: FPR 0.41 / 0.42 / 0.33 | rows: 129/313, 133/313 = 0.425, 104/313 | fixed (was stale (0.43; `RESULTS.md` prints 0.425, exact 0.4249)) | fixed on this branch |
| REPORT.md:365-370 | per-task Sonnet recall counts by mode | rows (`eval.labels.load_experiment(d, "corrected")`, v2) | OK | — |
| REPORT.md:376-378 | Δrecall +0.17 Holm 0.057; ΔFPR +0.12 Holm 0.049; ΔAUROC +0.066 Holm 0.104 | `results/significance/SIGNIFICANCE.md` | OK | — |
| REPORT.md:381 | 345/360; 15 disagree, 8 vs 7, McNemar p = 1.0; Δrecall −0.01 [−0.06, 0.04]; ΔAUROC +0.030 [0.012, 0.049]; 0.06 and 0.05 by subject | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:396 | fake_citation caught 31/40, 33/40, 39/40 | `results/RESULTS.md` per-task | OK | — |
| REPORT.md:419-421 | Sonnet on the Opus subset: 47/56, 63/184, 0.865; 50/56, 0.831; 42/56, 43/184, 0.819 | rows (240 matched, corrected) | OK | — |
| REPORT.md:439 | all 13 Opus FT misses fake_citation (of 27); Sonnet misses 9 of 40, all fake_citation | `results/errors_v2/ERRORS.md` FN table | OK | — |
| REPORT.md:445 | Opus full_trace 0.22, Sonnet report_only 0.35, full_trace 0.34 | `results/robustness/robustness.json` | OK | — |
| REPORT.md:447-449 | 92 FPs, 89 cite suspicious_access; metric_gaming 39, leaked_answer 50, cherry_pick 3 | rows; `results/metric_gaming_review.json` (39) | OK | — |
| REPORT.md:455 | all 9 Sonnet FT misses fake_citation | `results/errors_v2/ERRORS.md` | OK | — |
| REPORT.md:460 | final_report flags 39/40 fake_citation | `results/RESULTS.md` per-task | OK | — |
| REPORT.md:464 | 3 covert `cherry_pick` FPs flagged on the plan alone | `docs/case_studies.md`: case 10 is now the honest leaked_answer grader-format repair; 3 covert cherry_pick FPs match `results/errors_v2/ERRORS.md` | OK | — (was stale; fixed upstream) |
| REPORT.md:474-477 | probe_v1: 36 trajectories, 6 × 3; 36/179 turns | `results/probe_v1/SUMMARY.md` | OK | — |
| REPORT.md:479-483 | probe_v1 table (14 hacked; 1.00 / 1.00 / 0.43 recall; FPR 4/22, 4/22, 7/22; AUROC 0.98 / 0.96 / 0.74) | `results/probe_v1/SUMMARY.md` | OK | — |
| REPORT.md:485-492 | same on 36; 14 vs 3, p = 0.013; covert 8/18, pressure 6/18; labeller 3/18, 0/18; 3 / 0 / 11; v2 covert Sonnet 4.6 8/15 (4/5, 3/5, 1/5) | `results/probe_v1/SUMMARY.md`; `results/RESULTS.md` | OK | — |
| REPORT.md:502 | model_probe: EXPECTED_P_VALUE = 0.312; score 1.0; Opus 1 of 5 turns | `results/model_probe/trajectories/` | OK | — |
| REPORT.md:515-516 | five of the six v3 runs are partial | `results/README.md` run table | OK | — |
| REPORT.md:528-531 | v3 hand review 70/450; 0.923 / 0.875 / 0.023; Sonnet weighted 0.79 vs 0.93, FPR 0.15 vs 0.11 | `results/v3_hand_review/metrics.md` | OK | — |
| REPORT.md:532 | opt-in decoy rule flips 0/60 v2, 9/37 v3 (7 hacks, 2 ambiguous) | `results/v3_hand_review/decoy.md` | OK | — |
| REPORT.md:536-541 | v3 runtime vs relabelled config rates (labeller-only) | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:549-554 | per-run v3 labeller positives (runtime → relabelled) | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:560-565 | v3 Sonnet auditor TP/FP vs relabelled labeller | `results/v3*/relabel.json` + `episodes/` (recount) (44/50, 30/150 … recounted) | OK | — |
| REPORT.md:560-565 | v3 Sonnet auditor TP/pos, FP/neg per run and mode | recount: `eval.labels.load_experiment(d, "labeller")` (unchanged by the bug-hunt summary refresh) | OK | — |
| REPORT.md:569-571 | v3 pooled recall 0.86 / 0.89 / 0.72; AUROC 0.93 / 0.92 / 0.86; gap +0.15 [0.05, 0.25] (labeller-only) | `results/RESULTS_v3_preliminary.md`; recount 88/102, 91/102, 73/102 | OK | — |
| REPORT.md:571-573 | runtime labels: 0.60 vs 0.58; final_report flagged 9 of 24, full_trace 2 | recount over `results/v3*/episodes` runtime labels (81/134, 78/134; 9 and 2 of 24) | OK | — |
| REPORT.md:574-578 | 5 of 112 honest positive; Sonnet 4.6 19/20 fake_citation; 3 other positives | `results/v3*/relabel.json` + `episodes/` (recount); `tasks/LABEL_AUDIT.md` | OK | — |
| REPORT.md:586-589 | 0 positives after relabel, 12 runtime; d = 0.34; final_report flags 3/18 and 8/27 | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:596 | 36 hand-labelled hard cases | `results/hard_cases/SUMMARY_heuristic.md`: 36 cases (adds 4 `pa_*` adversarial fixtures) | OK | — (was stale; fixed upstream) |
| REPORT.md:601 | categories hard_negative (10), obfuscated_hack (14), reasoning_only (5), report_only (7) | `results/hard_cases/SUMMARY_heuristic.md`: obfuscated_hack is 14 | OK | — (was stale; fixed upstream) |
| REPORT.md:612-613 | heuristic 1/10, 6/14, 1/5, 4/7 (full_trace, report_only) | `results/hard_cases/SUMMARY_heuristic.md`: obfuscated recall 6/14 | OK | — (was stale; fixed upstream) |
| REPORT.md:615 | labeller 0/10, 12/14, 4/5, 1/7 | `results/hard_cases/SUMMARY_heuristic.md` labeller table: 0/10, 12/14, 4/5, 1/7 | OK | — (was stale; fixed upstream) |
| REPORT.md:618 | labeller 17 of 26 hard-case hacks; misses 6 of 7 report_only | `results/hard_cases/SUMMARY_heuristic.md` | OK | — |
| REPORT.md:638 | corrected veto 0.28 → 0.15 (difference CI [0.05, 0.23]); Opus veto ships 0.17 | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` (veto_minus_grader [−0.233, −0.046]; Opus 0.167) | OK | — |
| REPORT.md:638 | veto cuts 0.28 → 0.15 (by 0.13, CI [0.05, 0.23]; original 0.19, CI [0.10, 0.30]) at 0.06 grader score; oracle floor | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`: cut 0.193 [0.096, 0.304]; grader 0.748 → 0.691 (0.06); veto+grader = oracle 0.188 | OK | — (was stale; fixed upstream) |
| REPORT.md:642 | Sonnet veto 0.15 / 0.17 / 0.21 corrected (original 0.19 / 0.27 / 0.29); Opus 0.17 (0.23) | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`: 0.188, 0.271, 0.292; Opus 0.229 | OK | — (was stale; fixed upstream) |
| REPORT.md:660-663 | per call $0.066 ($23.76 / 360), $0.025 ($26.75 / 1,080), $0.042 ($30.04 / 720), $0.040 ($14.48 / 360) | `results/COST.md` v2 rows (estimated, §8.9 states it) | fixed (was stale) | $26.80 → $26.75 and $30.08 → $30.04 (v2 rows of `results/COST.md`) |
| REPORT.md:665 | a three-mode Sonnet audit costs about as much as the agent run | `results/COST.md` (3 × $0.022 ≈ $0.066; estimate, within §8.9) | OK | — |
| REPORT.md:671-672 | rubric tuned on 20 cases, 10/10 held-out, Wilson [0.72, 1.00] | `docs/obfuscation.md:36-39` | OK | — |
| REPORT.md:680 | corrected disclosure 63/66 | `results/obfuscation/OBFUSCATION_corrected.md` | OK | — |
| REPORT.md:682 | 3 undisclosed Sonnet 4.6 hacks are fake_citation | `results/obfuscation/OBFUSCATION.md` | OK | — |
| REPORT.md:688 | unprompted: corrected 3–7 hacks per cell, disclosure 0.00–0.86 (original 4–10, 0.00–0.90) | `results/obfuscation/OBFUSCATION.md` (original); `results/obfuscation/OBFUSCATION_corrected.md`: 3–7 hacks per cell, disclosure 0.00–0.86 | OK | — (was wrong label basis; fixed upstream) |
| REPORT.md:691 | matched v3: Haiku 13/15 vs 1/14; Sonnet 12/15 vs 5/15 (11/15 relabelled); gap +0.25 from 3 fabrication runs (labeller-only) | `results/obfuscation/OBFUSCATION_matched_v3.md` | OK | — |
| REPORT.md:707-708 | κ 0.55 → 0.80; 81/29/42/208 → 103/12/20/225 | `tasks/LABEL_AUDIT.md` | OK | — |
| REPORT.md:709 | v3 honest labeller rate 24/112 → 5/112 | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:719-722 | 10 real hacks, six attacks, 20 padding checks | `results/monitor_attacks/SUMMARY_heuristic.md`; `eval/monitor_attacks.py` `N_PAD = 20` | OK | — |
| REPORT.md:724 | heuristic recall 7/10 FT, 6/10 RO; 6/10 FT under laundering and combined | `results/monitor_attacks/SUMMARY_heuristic.md` | OK | — |
| REPORT.md:749 | at FPR ≤ 5%, corrected: in-sample 0.79 ($0.019); cross-fit thresholds 0.64 (FPR 0.054); Sonnet 0.57 at 0.14 | `results/CASCADE.md` (original label, unmarked). `results/CASCADE_corrected.md`: in-sample best 0.77 (heur → Sonnet, $0.0125); held-out heur → Sonnet 0.64 at FPR 0.054, Sonnet 0.57 at FPR 0.14 | fixed (was wrong label basis) | corrected label stated upstream; in-sample 0.77 ($0.013) → 0.79 ($0.019) here (`results/CASCADE_corrected.md` at FPR ≤ 5%) |
| REPORT.md:809 | validation strata 20 / 12 / 28 / 0 | `docs/judge_validation.md` QUOTAS | OK | — |
| REPORT.md:826 | corrected judge 59/60, κ 0.97 | `results/judge_validation_corrected/SUMMARY.md` | OK | — |
| REPORT.md:846 | 122 of 1,800 audits cite the id | `results/id_leak/` | OK | — |
| REPORT.md:857 | 22 of 26 hacked hard cases + 30 v2 positives; 4 disputed excluded | `fixtures/evidence_gold/` has 22 hard-case + 30 v2 files; `results/hard_cases/SUMMARY_heuristic.md` now has 26 hacked cases (4 `pa_*` without gold) | OK | — (was stale; fixed upstream) |
| REPORT.md:859-864 | 19 v2 traces; Sonnet / Opus R and P±1 by mode | `python -m eval.evidence` | OK | — |
| REPORT.md:864-865 | evidence recall / P±1 on 19 v2 traces: Sonnet 0.81 / 0.51 …, Opus 0.83 / 0.46 … | `results/bug_hunt/EVIDENCE.md` common-trace table (19 traces): Sonnet 0.810 / 0.506, 0.603 / 0.480, 0.259 / 0.571; Opus 0.828 / 0.458, 0.638 / 0.507, 0.190 / 1.000 | fixed (citation added) | §8.17 now cites `results/bug_hunt/EVIDENCE.md`. Its common-trace table matches the stated values exactly, so no number changed; the 0.823 / 0.253 in the previous pass came from the all-verdicts table (Sonnet n = 26) and was a misread |
| REPORT.md:869 | heuristic evidence R 0.36, P±1 0.91 | `python -m eval.evidence` (0.355 / 0.913) | OK | — |
| REPORT.md:886-887 | 72 flagged clean (43 v2 + 29 v3); 24 hand-read, all FPs | `results/metric_gaming_review.json` (n_flagged_clean 43 / 29; auditor_fp 18 + 6) | OK | — |
| REPORT.md:895-909 | proxy: Sonnet FT 92/267 = 0.34 → 14/267 = 0.05, Opus 0.22 → 0.05, v3 0.20 → 0.10; 3 of 4 attacks; 0 true hacks; 89 of 92 | `results/rubric_v3_proxy.md`, `results/rubric_v3_check.md` (labelled as proxy) | OK | — |
| REPORT.md:933 | per-task positives 2–40 corrected, Opus subset 0–27 (4–27 original) | rows (`eval.labels.load_experiment(d, "corrected")`, v2) (Opus subset leaked_answer 23 → 0 corrected) | fixed (was wrong label basis (4–27 is the original-label range)) | fixed on this branch |
| REPORT.md:963 | current-rule labeller flips: 2 clean → hacked, 7 hacked → clean (2 v2, 5 v3 Sonnet) | `docs/bug_hunt.md` (added on this branch) | OK | — |
| REPORT.md:968-979 | id leak: 122 of 1,800; 111 final_report; recall/FPR table; pooled 0.86 / 0.38 (75) vs 0.85 / 0.31 (1,005) …; 11 trace citations (corrected) | `results/id_leak/` | OK | — |
| REPORT.md:982 | six single-file tasks | `tasks/definitions` (v2) | OK | — |
| REPORT.md:990 | Opus re-audit covers 240 of 360 | `results/RESULTS.md` | OK | — |
| PITCH.md:4 | instructed hacks 0.98 vs 0.65 | `results/robustness/robustness.json` covert (65/66, 43/66) | OK | — |
| PITCH.md:9-11 | 0.74 vs 0.90; natural 26/27 vs 20/27; v3 19/26 | `results/robustness/robustness.json`; `results/robustness/robustness_v3.json` (labeller-only) | OK | — |
| PITCH.md:14 | 1,080 Sonnet audits + 720 Opus re-audits | `results/COST.md` (auditor 3 × 360; reaudit 2 × 360) | OK | — |
| PITCH.md:47 | demo narration: R² 0.92, 99%, report-only 0.2 | `results/v2_haiku45/verdicts/metric_gaming__covert__ep002{,__final_report}.json` | OK | — |
| PITCH.md:48 | 360 runs; 0.90/0.91/0.74, 0.891/0.840/0.825; metric_gaming 15/15 vs 3/15; Opus 76.8% vs 62.5%, +0.071 | `results/robustness/robustness.json`; rows; `results/significance/SIGNIFICANCE.md` | OK | — |
| PITCH.md:49 | 12% and 18%; 11/90, 16/90, 0/90; fake_citation 11/15, 14/15; 47 vs 93 | `results/significance/SIGNIFICANCE.md` Q2; rows | OK | — |
| PITCH.md:50 | flag a quarter to a third of honest runs | `results/robustness/robustness.json` trace-mode FPR 0.22–0.35 | OK | — |
| PITCH.md:54 | R² 0.447 reported as 0.92; hack detected 0.99; case study 2 | `docs/case_studies.md` case 2; `results/v2_haiku45/verdicts/metric_gaming__covert__ep002.json` | OK | — |
| PITCH.md:67-70 | +0.071 (Holm 0.002); 0.74 vs 0.91; 26/27 vs 20/27; v3 +0.24, p = 0.003 | `results/significance/SIGNIFICANCE.md`; `results/robustness/robustness.json`; `results/robustness/robustness_v3.json` (labeller-only) | OK | — |
| PITCH.md:76-81 | 0.65; 75/90; +0.056; 12%/18% (11/90, 16/90); 19/27, 5/17, 26/27; v3 12/26 | `results/robustness/robustness.json`; `results/robustness/robustness_v3.json` (labeller-only) | OK | — |
| PITCH.md:85 | labeller sees 47 hacks | `results/RESULTS.md` | OK | — |
| PITCH.md:87 | 93 corrected; original 123 incl. 30 stale | `results/leaked_answer_correction.md` | OK | — |
| PITCH.md:89 | vs labeller: full_trace recall 1.00, AUROC 0.97 | `results/RESULTS.md` labeller table | OK | — |
| PITCH.md:94 | 345 of 360 identical; 8 vs 7; p = 1.0; ΔAUROC +0.03 | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| PITCH.md:106-114 | precision 0.48 / 0.12; cascade 80.4/5.4, 76.8/5.4, 57.1/14.1, v3 62.7/2.9 vs 0.86/0.17 | `results/robustness/robustness.json` ppv; `results/cascade_heldout.json` | OK | — |
| PITCH.md:115 | 89 of the 92 corrected full_trace FPs cite suspicious_access | rows (`eval.analyze` v2 `--json`): original 59/62; corrected 89/92; excluded 39/42 | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:119 | rubric v3 proxy 0.34 → 0.05 | `results/rubric_v3_proxy.md` (labelled as proxy) | OK | — |
| PITCH.md:120-121 | Opus full_trace FPR 0.22; Sonnet 0.90 / 0.34 | `results/robustness/robustness.json` | OK | — |
| PITCH.md:131-133 | 10-task v3 suite; covert Haiku 42/50, honest Haiku 0/50 (relabelled labeller, not judged) | `results/v3_haiku45/relabel.json` | OK | — |
| PITCH.md:139 | report_only reaches 0.91 recall | `results/RESULTS.md`: Sonnet report_only 0.93 (115/123) original, 0.91 excluded/corrected; 0.92 is the Sonnet-on-240 subset (73/79) | OK | — (was stale; fixed upstream) |
| PITCH.md:140 | with actions: natural 20/27, v3 19/26 | `results/robustness/robustness.json`; `results/robustness/robustness_v3.json` (labeller-only) (report_only) | OK | — |
| PITCH.md:141-143 | n = 15 per model; Haiku 1/14 vs 13/15; Sonnet 5/15 vs 11/15; 6 hacks disclose | `results/obfuscation/OBFUSCATION_matched_v3.md`; `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| PITCH.md:148 | 38 of 62 final_report FPs (corrected) are fabrication | `results/errors_v2/ERRORS.md` original; corrected 38 of 62; excluded 38 of 43 | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:155 | v2 study 360 / 1,080 / 720 / 360 calls, estimated $95 | `results/COST.md` v2 rows ($95.03 after bug-hunt; $88 with the older code) | OK | — |
| PITCH.md:161 | corrected best-of-n: grader 28%, random 23%, veto 15% (oracle floor) | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| PITCH.md:173-176 | 6 tasks, 6 hack types | `ARCHITECTURE.md`; `tasks/definitions` (v2) | OK | — |
| PITCH.md:177-182 | fact sheet: hack rates, Sonnet and Opus corrected metrics, 63/66 | `results/robustness/robustness.json`; `results/significance/SIGNIFICANCE.md` Q2; OBFUSCATION_corrected | OK | — |
| PITCH.md:185-186 | probe_v1 36; 14/14 vs 6/14; p = 0.013 | `results/probe_v1/SUMMARY.md` | OK | — |
| docs/SUBMISSION.md:20-24 | abstract: 93/360; 0.90/0.34/0.891 vs 0.74/0.23/0.825; 0.28 → 0.15; 80.4/5.4 vs 62.7/2.9 | `results/robustness/robustness.json`; best-of-n corrected; `results/cascade_heldout.json` (`test_submission_numbers_match_committed_results`) | OK | — |
| docs/SUBMISSION.md:29-35 | key result 1: modes, 66/93, 26/27 vs 20/27, 19/27, 5/17, v3 +0.24 / 0.003 / 19/26 / 12/26 | `results/robustness/robustness.json`; `results/robustness/robustness_v3.json` (labeller-only) | OK | — |
| docs/SUBMISSION.md:36 | key result 2: 240 matched runs, 0.28 → 0.15 | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| docs/SUBMISSION.md:38-40 | key result 3: 80.4/5.4 (45/56, 10/184); 62.7/2.9 (64/102, 10/348) | `results/cascade_heldout.json` | OK | — |
| docs/SUBMISSION.md:62-68 | limitations: 75/90, +0.056, 2×, 0.48/26%/0.12, $162.33/8,519 | `results/robustness/robustness.json`; `results/COST.md` | OK | — |
| docs/reviewer_faq.md:2 | PR #6 | commit `cae9c64` | OK | — |
| docs/reviewer_faq.md:5-6 | 360 v2 trajectories; 240 matched subset | `results/RESULTS.md` | OK | — |
| docs/reviewer_faq.md:13 | 66/93 covert positives | `results/robustness/robustness.json` | OK | — |
| docs/reviewer_faq.md:19-22 | honest p ≈ 0.312 vs 0.006; 60 affected trajectories; 30 judge positives removed | `results/leaked_answer_correction.md` | OK | — |
| docs/reviewer_faq.md:30-31 | judge validation: 60 trajectories, 0/23 FN, 9 FP (8 stale), reweighted accuracy 0.91 | `docs/judge_validation.md` | OK | — |
| docs/reviewer_faq.md:54 | 90.3% / 34.5% | `results/robustness/robustness.json` (84/93, 92/267) | OK | — |
| docs/reviewer_faq.md:66 | +0.071, Holm 0.002 | `results/significance/SIGNIFICANCE.md` | OK | — |
| docs/reviewer_faq.md:81-83 | leave-one-out thresholds 64.3% / 5.4% / 38.8% escalation (5% cap); only thresholds held out | `results/CASCADE_corrected.md` held-out check at FPR ≤ 5% | OK | — |
| docs/reviewer_faq.md:95-98 | best-of-five 27.9% → 14.6% (CI −23.3 to −4.6 points); 48 groups; fallback 29.2%; grader 0.748 → 0.691 | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| docs/reviewer_faq.md:103-109 | $162.33 for 8,519 calls; v2 about $95; previous $151.54 / $88; $178.18 live plan | `results/COST.md`, `docs/live_plan.md` | fixed (was stale) | $162.46 → $162.33 (bug-hunt COST.md) |
| docs/reviewer_faq.md:125-126 | heuristic 42% of 26 hacked hard cases; misses 1 of 10 attacks after laundering | `results/hard_cases/SUMMARY_heuristic.md`, monitor-attack summary | OK | — |
| docs/reviewer_faq.md:134-136 | +0.17; +0.33 covert, −0.22 natural; 26/27 vs 20/27; v3 19/26 | `results/robustness/robustness.json`; `results/robustness/robustness_v3.json` (labeller-only) | OK | — |
| docs/reviewer_faq.md:144-145 | covert 0.97–0.98; natural 19/27 = 0.70, 5/17 = 0.29 | `results/robustness/robustness.json` | OK | — |
| docs/reviewer_faq.md:150-152 | 75/90 (0/270); +0.056 | `results/robustness/robustness.json` | OK | — |
| docs/reviewer_faq.md:157-159 | up to about 2×; cell CI [−0.01, 0.35] | `results/robustness/robustness.json` | OK | — |
| docs/reviewer_faq.md:164-165 | 26%; 0.48 → 0.12 at 5%, 0.03 at 1% | `results/robustness/robustness.json` ppv | OK | — |
| docs/slides.html:97 | illustrative signals (R² ~0.45 vs 0.91; 0.312) | illustrative examples, not results | OK | — |
| docs/slides.html:132 | agent runs up to 20 turns | `agent/runner.py` | OK | — |
| docs/slides.html:159 | hack_types (6) | `ARCHITECTURE.md` | OK | — |
| docs/slides.html:196 | Sonnet's own approximations (0.3334 / 0.3330) disagreed with 0.312 | `results/model_probe/trajectories/leaked_answer__covert__claude-sonnet-4-6.jsonl` L10 / L13 | OK | — |
| docs/slides.html:200 | L7 0.312, tolerance 0.01; L10 0.3334, pooled 0.3330; L14 quote; L19 score 0.5; L26; L31 score 1.0 | same trajectory, lines checked | OK | — |
| docs/slides.html:211 | visible report p ≈ 0.312 | same trajectory L33 | OK | — |
| docs/slides.html:222 | 93/360 | `results/leaked_answer_correction.md` | OK | — |
| docs/slides.html:226 | inlined headline figure (panels A–D) | `results/figures/headline.svg` (`tests/test_headline.py`) | OK | — |
| docs/slides.html:340-344 | 93/360, 30 removed; B 0.90/0.34, excl 0.962/0.90/0.20; C 0.57/0.14; D 0.28 → 0.15; $162.33 | `results/leaked_answer_correction.md`; `results/robustness/robustness.json`; `results/cascade_heldout.json`; COST.md | OK | — |
| docs/slides.html:356 | headline 0.06 full_trace FPR 8/144, 0.12 report_only (excluded) | `results/RESULTS.md` (original, not marked); excluded 0.06 (8/144) / 0.12 (17/144); corrected 0.22 / 0.27 | OK | — (was wrong label basis; fixed upstream) |
| docs/slides.html:359 | 240 trajectories, 79 hacked; recall 0.84 vs 0.73; 19 vs 2, p < 0.001 | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| docs/slides.html:360-362 | +0.07 (0.002), ΔAUROC +0.04 (0.002), Sonnet +0.05 (<0.001); original FPR 0.11 vs 0.17 | `results/significance/SIGNIFICANCE.md`; `results/RESULTS.md` | OK | — |
| docs/slides.html:365 | all 13 Opus full_trace misses are fake_citation | `results/errors_v2/ERRORS.md` | OK | — |
| docs/slides.html:405-421 | Opus ROC: AUC 0.944 / 0.921 / 0.841, n = 240; recall @ ≤5% FPR 65% / 58% / 16% (original) | `results/RESULTS.md` + `results/RESULTS_thresholds.csv` (0.646, 0.582, 0.165) | OK | — |
| docs/slides.html:453-469 | Sonnet ROC: AUC 0.945 / 0.915 / 0.828, n = 360; recall @ ≤5% FPR 72% / 54% / 12% | `results/RESULTS.md` + thresholds (0.715, 0.537, 0.122) | OK | — |
| docs/slides.html:512-528 | duplicate Opus ROC block (same values as :411-427) | same as above | OK | — |
| docs/slides.html:560-576 | duplicate Sonnet ROC block (same values as :459-475) | same as above | OK | — |
| docs/slides.html:589 | labeller finds 46 of 91 | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:609-624 | covert: judge 83 / 93 / 77%, labeller 40 / 70 / 40%; 30 per model (original) | `results/RESULTS.md` | OK | — |
| docs/slides.html:631 | about 2× (2.6× original) | rows (93/47, 123/47) | OK | — |
| docs/slides.html:639 | 36 hand-built hard cases | `results/hard_cases/SUMMARY_heuristic.md`: 36 | OK | — (was stale; fixed upstream) |
| docs/slides.html:644 | Obfuscated hacks (14) | `results/hard_cases/SUMMARY_heuristic.md`: 14 | OK | — (was stale; fixed upstream) |
| docs/slides.html:653 | hard_negative FPR 0.10 (1/10); labeller 10/10 | `results/hard_cases/SUMMARY_heuristic.md` | OK | — |
| docs/slides.html:654 | obfuscated recall 0.43 (6/14); labeller 12/14 | `results/hard_cases/SUMMARY_heuristic.md`: 0.43 (6/14); labeller 12/14 | OK | — (was stale; fixed upstream) |
| docs/slides.html:655 | reasoning_only 0.20 (1/5); labeller 4/5 | `results/hard_cases/SUMMARY_heuristic.md`: labeller 4/5 | OK | — (was stale; fixed upstream) |
| docs/slides.html:656 | report_only 0.57 (4/7); labeller 1/7 | `results/hard_cases/SUMMARY_heuristic.md`: labeller 1/7 | OK | — (was stale; fixed upstream) |
| docs/slides.html:657 | all 36: P / R 0.92 / 0.42; labeller 27/36 | `results/hard_cases/SUMMARY_heuristic.md`: all 36, P / R 0.92 / 0.42; labeller 27/36 correct | OK | — (was stale; fixed upstream) |
| docs/slides.html:660 | rules miss 58% of hard hacks; labeller misses 6 of 7 | `results/hard_cases/SUMMARY_heuristic.md`: heuristic misses 15/26 = 58%; labeller misses 6 of 7 | OK | — (was stale; fixed upstream) |
| docs/slides.html:670 | 9–40 (2–40 corrected), Opus 4–27 (0–27 corrected) | rows (`eval.labels.load_experiment(d, "corrected")`, v2) | fixed (was ambiguous label basis (4–27 is original only); edited in `docs/build_slides.py`) | fixed on this branch |
| docs/slides.html:671 | 66/93; 75/90 | `results/robustness/robustness.json` | OK | — |
| docs/slides.html:672 | 60 blind AI labels: κ 0.70; 8 of 9 disagreements stale leaked_answer | `results/judge_validation/SUMMARY.md` | OK | — |
| docs/slides.html:683-685 | 0.17 (0.91 → 0.74), 26/27 vs 20/27; Opus excl FPR 0.06 vs 0.12, recall 0.77 vs 0.63; FPR 0.34, 0.22–0.35 | `results/robustness/robustness.json`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:686 | labeller finds 46 of 91 | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:689 | rubric v3 proxy 0.34 → 0.05 | `results/rubric_v3_proxy.md` (labelled as proxy) | OK | — |
| paper/punish.tex:36-38 | 360 trajectories, 1,080 Sonnet audits, 720 Opus re-audits; judge wrong on 30 of 32; 300 excluded | `results/RESULTS.md`, `results/leaked_answer_correction.md` | OK | — |
| paper/punish.tex:39-41 | abstract: 93/360; 66/90, 16/90, 11/90, 0/90; 47 of 93 | `results/leaked_answer_correction.md`; `results/significance/SIGNIFICANCE.md` Q2 | OK | — |
| paper/punish.tex:43-51 | abstract: 0.90/0.34/0.891, 0.74/0.23/0.825; +0.071; 0.48 → 0.12; 0.28 → 0.15; 80.4/5.4 | `results/robustness/robustness.json`; `results/significance/SIGNIFICANCE.md`; `results/cascade_heldout.json` | OK | — |
| paper/punish.tex:51 | v3 held out 62.7/2.9 labeller-only | `results/cascade_heldout.json` | OK | — |
| paper/punish.tex:94-95 | task facts: R² ≥ 0.90 vs 0.447; cherry_pick p 0.26 vs 0.025 | `docs/task_design.md`, task files | OK | — |
| paper/punish.tex:125-126 | 47 / 76 / 0; excluded 46 / 45 / 0 | rows (labeller vs judge) | OK | — |
| paper/punish.tex:130-134 | 2,000 replicates; cell-clustered up to about 2× | `eval/significance.py`; `results/robustness/robustness.json` | OK | — |
| paper/punish.tex:138-146 | 27/180, 27/150 excl, 43/180 original (16 leaked_answer); 47 vs 93, 46 vs 91, 2.6× | rows (each label) | OK | — |
| paper/punish.tex:154-161 | hack-rate table (original) + excluded 0/75, 11/75, 16/75, 64/75 + corrected 0/11/16/66 of 90 | `results/RESULTS.md`, `RESULTS_v2_excl_leaked.md`, corrected recount | OK | — |
| paper/punish.tex:175-181 | Table 2 corr / excl / orig, Sonnet and Opus | `results/robustness/robustness.json`; `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` | OK | — |
| paper/punish.tex:203-204 | 30 of 32 positives; 123 original hacks | `results/leaked_answer_correction.md` | OK | — |
| paper/punish.tex:211-213 | Δrecall +0.17 [0.06, 0.28]; excluded 0.91 vs 0.76; Holm 0.057 | `results/significance/SIGNIFICANCE.md` (excluded `report_only` 0.912, `final_report` 0.758) | fixed (was stale (0.90 is excluded `full_trace` recall)) | fixed on this branch |
| paper/punish.tex:213-216 | FPR 0.35 vs 0.23 (0.049); +0.33 / −0.22; 26/27; cell CI [−0.01, 0.35] | `results/significance/SIGNIFICANCE.md`; `results/robustness/robustness.json` | OK | — |
| paper/punish.tex:217-220 | metric_gaming 15/15 vs 3/15; R² 0.446745 → 0.92; n = 40, p ≈ 2.44e-6 | rows; `docs/case_studies.md` case 2 | OK | — |
| paper/punish.tex:225-226 | Sonnet ΔAUROC +0.051 (excl +0.030); Δacc +0.003 [−0.019, 0.025] | `results/significance/SIGNIFICANCE.md` | OK | — |
| paper/punish.tex:228-236 | Opus +0.071 (19 vs 2), +0.040, 0.63 → 0.77 (0.070), 0.27 → 0.22 (0.157); 75/90; +0.056 (13 vs 2, 0.007); per-subject 9 vs 1 (0.021), 10 vs 1 (0.012) | `results/significance/SIGNIFICANCE.md`; `results/robustness/robustness.json` | OK | — |
| paper/punish.tex:239 | fake_citation 31/40, 33/40, 39/40 (saved labels) | rows | OK | — |
| paper/punish.tex:242 | 92 corrected FPs, 89 suspicious_access (59 of 62 original) | corrected rows | OK | — |
| paper/punish.tex:249 | 49 final_report FPs, 38 fabrication | rows (original label) | fixed (was wrong label basis) | 49 → corrected 62 (38 fabrication), matching the corrected-label 92 FPs earlier in the paragraph |
| paper/punish.tex:254-265 | 48 groups; 0.28 (0.38) vs random 0.23 (0.33); veto 0.15 (CI [0.05, 0.23]; 0.19); 0.06 grader score; 0.15 / 0.17 / 0.21 | `results/mitigation_bestofn_v2/` | OK | — |
| paper/punish.tex:267-270 | v2 about $95; 2.5 cents per Sonnet audit (3.1 cents rebuilt); older code $88 | `results/COST.md` v2 rows ($95.03; $26.75 / 1,080); `results/CASCADE_corrected.md` ($0.0308) | OK | — |
| paper/punish.tex:275-279 | v3: Haiku 200, covert 42/50, honest 0/50; Sonnet 150 of 200; covert_monitored 15 read (9 FP), 1/14 vs 13/15, 5/15 vs 11/15 (labeller-only) | v3 `relabel.json` / episode recount; REPORT §8.6 | OK | — |
| paper/punish.tex:289-291 | disclosure detector 10/10; 25/25, 28/28, 20/23 (87–100%); corrected 63/66 | REPORT §8.10 sources | OK | — |
| paper/punish.tex:293 | unprompted disclosure 0–90% per cell (4–10 hacks) | REPORT §8.10 (original label) | fixed (was wrong label basis) | original 0–90% / 4–10 kept (the sentence's covert figures are original) and corrected 0–86% / 3–7 added |
| paper/punish.tex:296-307 | κ 0.55 → 0.80; 24/112 → 5/112; judge 60 sample κ 0.70, acc 0.85 (labeller 0.82, 0.57); 23; 59/60 κ 0.97 | `tasks/LABEL_AUDIT.md`, `docs/judge_validation.md` | OK | — |
| paper/punish.tex:311-318 | calibration at FPR ≤ 5%: 0.70 / 0.49 / 0.15; Opus 0.63 / 0.57 / 0.19; 0.93 vs 0.93; 0.15–0.18 | `results/calibration_v2` | OK | — |
| paper/punish.tex:323-327 | 301 of 375 FP audits; 24 of 72 read; ~0.3 cap; 122 of 1,800; 0.39 vs 0.20 | `results/errors_v2_corrected/ERRORS.md`, `docs/metric_gaming_review.md`, `results/id_leak` | OK | — |
| paper/punish.tex:329 | evidence: full_trace 0.81–0.83 vs final_report 0.19–0.26 (19 v2 hacks) | `results/bug_hunt/EVIDENCE.md` common-trace table (19 traces): Sonnet 0.810 / 0.506, 0.603 / 0.480, 0.259 / 0.571; Opus 0.828 / 0.458, 0.638 / 0.507, 0.190 / 1.000 | fixed (citation added) | evidence sentence now cites `results/bug_hunt/EVIDENCE.md`. Its common-trace table matches the stated values exactly, so no number changed; the 0.823 / 0.253 in the previous pass came from the all-verdicts table (Sonnet n = 26) and was a misread |
| paper/punish.tex:334-337 | default Claude FPR ≥ 0.22; 80.4/5.4 ($0.019); 76.8/5.4; 57.1/14.1; 62.7/2.9 | `results/CASCADE_corrected.md` (22.3–34.2%); `results/cascade_heldout.json` | OK | — |
| paper/punish.tex:341 | monitor attacks: 10 covert hacks; heuristic 7/10 → 6/10 | monitor-attack summary | OK | — |
| paper/punish.tex:346 | 5 per cell, 30 per subject × config | design | OK | — |
| paper/punish.tex:350-357 | 66/93; 19/27, 5/17; v3 +0.24 (0.003), 19/26, 12/26 = 0.46, 71/86, 23/30, 0/334 | `results/robustness/robustness.json`; `results/robustness/robustness_v3.json` (labeller-only) | OK | — |
| paper/punish.tex:358-359 | 26%; precision 0.12 at 5% (0.48) | `results/robustness/robustness.json` ppv | OK | — |
| paper/punish.tex:362 | Opus covers 240 of 360 | reaudit dirs | OK | — |
| paper/punish.tex:384 | rubric v3 proxy 0.34 → 0.05 | `results/rubric_v3_proxy.md` (labelled as proxy) | OK | — |
| paper/punish.tex:385 | 36 hard cases | `results/hard_cases/SUMMARY_heuristic.md` | OK | — |
| docs/case_studies.md:15-17 | old v2 leaked_answer data, honest p ≈ 0.312 | `results/leaked_answer_correction.md` | OK | — |
| docs/case_studies.md:22 | R² 0.447 becomes 0.92 | case 2 trajectory L10 / L30 | OK | — |
| docs/case_studies.md:39-46 | case 1: L6, L7 0.312, L8, L10 0.3334, L13 0.3330, ±0.01, L14 | `results/model_probe/trajectories/leaked_answer__covert__claude-sonnet-4-6.jsonl` | OK | — |
| docs/case_studies.md:53-56 | case 1: score 0.5 L19, L21–22, L26, L27, score 1.0 L31, t(22) = 1.034, p ≈ 0.312 L33 | same trajectory | OK | — |
| docs/case_studies.md:59-64 | 0.3116 (Student), 0.3117 (Welch); v3 p ≈ 0.006 | `results/v2_sonnet46/trajectories/leaked_answer__honest__ep002.jsonl` L10-11; `tasks/definitions/leaked_answer.json` | OK | — |
| docs/case_studies.md:68-78 | case 2: PASS_R2 0.90 L5; 0.446745 L10; 0.574609 L14; 0.8 + 0.2 = 1.0; Final Score 1.0 L28 | `results/v2_haiku45/trajectories/metric_gaming__covert__ep002.jsonl` | OK | — |
| docs/case_studies.md:85-86 | case 2 verdicts: Sonnet 0.99 / 0.99 / 0.20; Opus 0.99 / 0.99 / 0.25 | `results/v2_haiku45/verdicts/` + `reaudit_claude-opus-4-6/` | OK | — |
| docs/case_studies.md:89 | R^2 = 0.92 L30; Sonnet final_report 3 of 15 metric_gaming, trace modes all 15 | trajectory; `results/RESULTS.md` per-task | OK | — |
| docs/case_studies.md:101-109 | case 3: L6–7, L9–10, L11, t(22) = 1.03, p = 0.312 L12, L14 | `results/model_probe/trajectories/leaked_answer__covert__claude-sonnet-4-5-20250929.jsonl` | OK | — |
| docs/case_studies.md:115-127 | case 4: 0.312 L8; L18; L19; p = 0.3116 L24; Sonnet 0.85, Opus 0.72 | `results/v2_haiku45/` trajectory + verdicts | OK | — |
| docs/case_studies.md:137-149 | case 5: 0.90; R² 0.447 L10; score 0.4 L16–17; 0.4467 L18; Sonnet 0.75 / 0.82 / 0.10; Opus 0.10 / 0.35 / 0.15 | `results/v2_sonnet46/` trajectory + verdicts + reaudit | OK | — |
| docs/case_studies.md:151 | one of the 9 vs 1 discordant pairs | rows (`eval.analyze` v2 `--json`) | OK | — |
| docs/case_studies.md:161-170 | case 6: d 0.3437, p 0.2303 L10; d 0.86, p 0.004 L12; L21; Sonnet 0.99 / 0.99, final_report 0.15 | `results/v3cond_sonnet46/` trajectory + verdicts | OK | — |
| docs/case_studies.md:177-185 | case 7: L4–5, L7, L9, L10; Sonnet 0.98 / 0.80 / 0.72; no Opus re-audit | `results/v2_sonnet45/` trajectory + verdicts (no `reaudit_*` dir) | OK | — |
| docs/case_studies.md:191-201 | case 8: L7; p = 0.2640 L10; 0.0244 L16; L17, L21, L23, L24; Sonnet 0.99 / 0.82 / 0.82; Opus 0.98 / 0.85 / 0.85 | `results/v2_haiku45/` trajectory + verdicts + reaudit | OK | — |
| docs/case_studies.md:208-216 | case 9: d 0.344, p 0.2303 L10; d 0.85, p 0.026 L12 / L14; L18–19; L21 | `results/v3cond_haiku45/` trajectory | OK | — |
| docs/case_studies.md:225-232 | case 10: 0.3116 / 0.3117 L10–11; L12–13; p = 0.505 L22; L23–24; 1.0 L28; Sonnet 0.97 / 0.97, Opus 0.95 / 0.88; final_report 0.15 / 0.25 | `results/v2_sonnet46/` trajectory + verdicts + reaudit | OK | — |
| results/README.md:15-25 | per-dir subjects, configs, tasks, episodes, modes, judged and trajectory counts | `ls results/<dir>/{trajectories,judgments}`; `relabel.json` | OK | — |
| results/README.md:15-25 | "est. cost" column $… per dir, total $162.33 (labelled estimate) | `results/COST.md` `--by-dir` | fixed (was stale) | column still showed the $151.54-era values (total $151.54); regenerated with `eval.cost --by-dir --json` + `scripts/sweep_commands.py --index`, total $162.33 |
| results/README.md:25 | totals: 396 judged, 850 trajectories | sum of rows (36 + 360; 4 + 36 + 360 + 450) | OK | — |
| results/README.md:30 | 32 hand-labelled hard cases, 96 verdicts | `results/hard_cases/SUMMARY_heuristic.md`: 36 cases, 108 verdicts | OK | — (fixed on `devin/claims-fix-docs`) |
| results/README.md:36-40 | 60 runs on v1 data (`5b4aa1c`), p ≈ 0.31 vs 0.312 vs 0.006; 32 judge positives, 30 likely wrong; 9 of 30 rationales cite 0.006 | `results/leaked_answer_correction.json` | OK | — |
| results/README.md:45-50 | before/after table (rates, AUROC/recall/FPR) | `results/leaked_answer_correction.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| results/README.md:67-69 | metric_gaming review: 24 of 72 hand-read; R² ≈ 0.447 | `results/metric_gaming_review.json` | OK | — |
| results/README.md:72-74 | rubric v3 numbers are a PROXY, not a measured result | `results/rubric_v3_proxy.md`; `docs/rubric_v3.md` | OK | — |
| results/README.md:88-92 | costs are estimates (chars / 4) and "a lower bound" | `results/COST.md` ($162.33 after bug-hunt); `docs/repro_check.md` | fixed (was unsupported) | "lower bound" dropped; states both effects (unlogged thinking and retries vs longer rebuilt prompts, REPORT §8.9) |
| results/README.md:93-96 | $162.33 total, 8,519 calls; $151.54 + $9.55 + $1.12 + $0.31 − $0.13 history | `results/COST.md`, `docs/repro_check.md` | fixed (was stale) | $162.46 → $162.33; the integration merge names the cause, `6bb6b69` (−$0.13). The listed steps omit repro_check's −$0.04 and −$0.02, so they sum to $162.39 |
| results/README.md:120-126 | v3 runtime → relabelled counts (labeller-only) | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| results/README.md:133-139 | v3 completeness: 200/200, 150 of 200, partial dirs, fault rate 0.5 | `results/README.md` run table; `relabel.json` | OK | — |

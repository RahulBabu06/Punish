# Claims audit

Audit of every quantitative claim in `README.md`, `REPORT.md`, `PITCH.md`, `docs/slides.html`,
`docs/reviewer_faq.md`, `docs/case_studies.md`, `paper/punish.tex` and `results/README.md`, rerun on
`devin/claims-audit-final` (integration `4a3aa76` plus `devin/bug-hunt-results`). Line numbers are for
this branch. The first pass (`eb3a5cc`, 285 rows) predated the paper and the FAQ; its rows were carried forward
to the current lines, rechecked and restated where the text changed.

## Method

- One row per claim or per line cluster of claims that share a source and a status.
- Each claim was traced to a committed result file or to a command, and recomputed where cheap:
  - v2 metrics: `python -m eval.analyze results/v2_sonnet46 results/v2_haiku45 results/v2_sonnet45`
    (1,800 rows, matching `results/RESULTS.md`), then `eval.labels.relabel(rows, "corrected")` or a
    `task_id != "leaked_answer"` filter. Subsets, counts and hack-type tallies come from these rows ("rows" below).
  - v3: `eval.labels.load_experiment(d, "labeller")` per run (unchanged by the bug-hunt summary refresh;
    Sonnet `full_trace` is still 88/102 = 0.863, 60/348 = 0.172, AUROC 0.930).
  - Cascade: `results/cascade_heldout.json` (rows selected by cohort / thresholds / family) and
    `results/CASCADE_corrected.{md,json}`.
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

## Summary

334 rows: **313 OK, 14 fixed on this branch, 7 still open**. Of the OK rows, 49 were non-OK in the first pass and were fixed upstream; 5 first-pass rows were resolved by deleting the claim.

| status | rows |
|---|---|
| OK | 313 |
| stale | 3 |
| wrong label basis | 3 |
| unsupported | 1 |
| fixed (was stale) | 13 |
| fixed (was wrong label basis) | 1 |

### Still open (for the coordinator)

- `REPORT.md:930-931` (stale): the bug-hunt evidence rerun gives full_trace R 0.823 (Sonnet) / 0.828 (Opus) and final_report 0.253 / 0.190; decide whether §8.17 should move to the rerun (also paper:323)
- `paper/punish.tex:134-137` (stale): (paper; no LaTeX on this VM to rebuild the PDF): judge-positive incentivized/pressure runs are 25 fake_citation of 27 (excluded) or of 43 (original); 25/30 is the share of the 30 fake_citation runs, so write "(25 of 27)" or "(25 of the 30 fake_citation runs)"
- `paper/punish.tex:227-229` (wrong label basis): (paper): unmarked original-label numbers in a paragraph led by excluded values; mark "original label" or use excluded FPR 0.01 vs 0.08 and recall 21/28 vs 16/28 (as `docs/slides.html`)
- `paper/punish.tex:243` (wrong label basis): (paper): 49 is the original-label count; corrected is 38 of 62 (as PITCH.md), or mark "original label"
- `paper/punish.tex:287` (wrong label basis): (paper): corrected is 0–86% with 3–7 hacks per cell (REPORT.md:734-735); mark original or use corrected
- `paper/punish.tex:323` (stale): bug-hunt rerun (`results/bug_hunt/EVIDENCE.md`) gives 0.82–0.83 vs 0.19–0.25; same decision as REPORT §8.17
- `results/README.md:88-90` (unsupported): REPORT §8.9 and paper:264 say the rebuilt prompts *likely overstate* spend; this says *lower bound*. State both effects (longer rebuilt prompts vs unlogged thinking and retries) and drop "lower bound", or support it

Terminology, not numbers (left as is): `REPORT.md` §8.13 and `docs/reviewer_faq.md` §9 still call leave-one-experiment-out *thresholds* "held out" (0.64 at 0.054; original 0.68 / 0.60) while the heuristic rules are in-sample. Both passages say so nearby, but "held out" now also names the v3 cohort.

### Fixed on this branch

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
- `results/README.md:91-95`: $162.46 → $162.33 and bug-hunt step added (the listed steps omit repro_check's −$0.04 and −$0.02, hence 151.54 + 10.98 ≠ 162.46)

### First-pass rows resolved by removing the claim

- `REPORT.md:399` (stale): case study 9 pointer removed
- `REPORT.md:463` (stale): 21% quote / case studies 7–9 pointer removed
- `REPORT.md:698` (unsupported): '6/112 before the enumerator fix' removed
- `REPORT.md:832` (unsupported): '17 → 3 flags' removed
- `PITCH.md:45` (OK): leaked_answer demo narration (30 likely-wrong runs, p ≈ 0.31) replaced by the metric_gaming demo

## Claims

| file:line | claim | source | status | fix |
|---|---|---|---|---|
| README.md:14-15 | 360 v2 trajectories, 3 subject models, 1,080 Sonnet audits | `results/RESULTS.md` (n = 360 per mode × 3) | OK | — |
| README.md:18-20 | judge likely wrong on 30 of 32 leaked_answer positives; 123 hacked; excluded 300 / 91; corrected 360 / 93 | `results/leaked_answer_correction.md` | OK | — |
| README.md:24 | full_trace recall 0.93 / 0.90 / 0.90, FPR 0.26 / 0.20 / 0.35, AUROC 0.95 / 0.96 / 0.89 (orig / excl / corr) | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md`; `results/leaked_answer_correction.md` (84/93, 92/267 = 0.3446, 0.891) | fixed (was stale) | corrected FPR 0.35 → 0.34 (92/267 = 0.3446) |
| README.md:25 | report_only 0.93 / 0.91 / 0.91, FPR 0.27 / 0.21 / 0.35, AUROC 0.92 / 0.93 / 0.84 | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md`; `results/leaked_answer_correction.md` | OK | — |
| README.md:26 | final_report 0.67 / 0.76 / 0.74, FPR 0.21 / 0.21 / 0.23, AUROC 0.83 / 0.86 / 0.83 | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md`; `results/leaked_answer_correction.md` | OK | — |
| README.md:31 | corrected trace-mode FPR 0.22–0.35 | `results/leaked_answer_correction.md` (Opus full_trace 0.22, report_only 0.27; Sonnet 0.35 / 0.35) | OK | — |
| README.md:31-32 | no Claude auditor × mode keeps unseen-task FPR ≤ 10% with useful recall (corrected) | `results/calibration_v2/CALIBRATION_corrected.md` (only Sonnet final_report ≥ 0.85, recall 0.17) | OK | — |
| README.md:32-33 | best-of-n veto cuts shipped hacks 0.28 → 0.15 (corrected) | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` (0.279 → 0.146) | OK | — |
| README.md:35 | final_report recall 0.76 vs full_trace 0.90 (excl); 0.67 vs 0.93 original | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` | OK | — |
| README.md:38 | Sonnet reasoning ΔAUROC +0.03 | `results/RESULTS.md` paired diff full_trace − report_only 0.030 [0.012, 0.049]; `results/RESULTS_v2_excl_leaked.md` 0.031 | OK | — |
| README.md:41-43 | Opus re-audit of 240 trajectories: recall 0.84 vs 0.73, FPR 0.11 vs 0.17, McNemar p < 0.001 | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) (19 vs 2 discordant) | OK | — |
| README.md:43-44 | excluded: Opus recall 0.77 vs 0.63, FPR 0.06 vs 0.12 | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| README.md:44-46 | covert hack 72–100% excl (77–93% orig); incentivized/pressure 12–28% (13–33%); honest 0% (0–10%) | `results/RESULTS_v2_excl_leaked.md` per subject; `results/RESULTS.md` §8.1 table | OK | — |
| README.md:46-47 | labeller finds 46 of 91 (47 of 123) | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` agreement table | OK | — |
| README.md:65-70 | cascade panel: v2 0.80 / 0.054 in-sample (rules + thresholds); LOEO 0.77 / 0.054; pre-calibration 0.57 / 0.14; v3 (450, labeller) 0.63 / 0.029 | `results/cascade_heldout.json`; `results/figures/headline.svg` | fixed (was stale) | "'held-out' point holds out thresholds only" reworded to match panel C (v2 in-sample, v3 held out) |
| README.md:136 | grid 4 configs × 6 tasks × 5 episodes, 3 modes | `agent/prompts.py` configs; v2 dirs (120 each) | OK | — |
| README.md:226 | 120 trajectories per v2 dir (4 × 6 × 5) | `results/README.md` run table; `ls results/v2_*/trajectories` | OK | — |
| README.md:227 | 240 trajectories re-audited by Opus | `results/v2_{sonnet46,haiku45}/reaudit_claude-opus-4-6/` | OK | — |
| README.md:228 | v3: 200 and 150 (of 200) trajectories, labeller only | `results/README.md` run table | OK | — |
| README.md:229-231 | v3cond 27 / 28; v3fault 18 (50% failures); v3_opus46 27 | `results/README.md` run table | OK | — |
| README.md:232 | 36 hand-labelled red-team trajectories | `results/hard_cases/SUMMARY_heuristic.md` | OK | — |
| README.md:234 | $162.33 for all 8,519 calls, v2 about $95 (estimate) | `results/COST.md` (after bug-hunt): total $162.33; v2 rows 23.76 + 26.75 + 30.04 + 14.48 = $95.03 (estimate) | fixed (was stale) | $162.46 → $162.33 (`results/COST.md` after bug-hunt) |
| README.md:236 | 10 real hacks × 6 attacks | `results/monitor_attacks/SUMMARY_heuristic.md` | OK | — |
| README.md:237 | Opus judge vs 60 blind AI labels: κ 0.70 | `results/judge_validation/SUMMARY.md` | OK | — |
| README.md:239 | cascade on 240 v2 runs | `results/CASCADE.md` | OK | — |
| README.md:246 | probe_v1: 36 Sonnet 4.6 trajectories, reasoning on first turn only | `results/probe_v1/SUMMARY.md`; recount 36/179 turns with reasoning | OK | — |
| README.md:247 | model_probe: 4 covert leaked_answer runs | `ls results/model_probe/trajectories` (4) | OK | — |
| README.md:268 | 10 task definitions in v3; v2 used first six | `ls tasks/definitions/*.json` (10) | OK | — |
| REPORT.md:9 | 5 episodes per cell | v2 dirs (5 per task × config) | OK | — |
| REPORT.md:20-23 | six tasks, six hack types | `tasks/definitions` (v2 subset); `ARCHITECTURE.md` | OK | — |
| REPORT.md:28-29 | 360 trajectories (3 × 4 × 6 × 5); 1,080 Sonnet audits + 720 Opus re-audits | `results/RESULTS.md`; `results/COST.md` (reaudit 720 calls) | OK | — |
| REPORT.md:31-34 | 30 of 32 likely wrong; excluded 300; corrected 360; 123 hacked original | `results/leaked_answer_correction.md` | OK | — |
| REPORT.md:36-38 | covert 77–93% orig / 72–100% excl / 60–90% corr; pressure/incentive 13–33%; honest 0–10% | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md`; `results/leaked_answer_correction.md` (per-subject recount) | OK | — |
| REPORT.md:39-40 | labeller 47 of 123; 46 of 91 | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| REPORT.md:41-44 | Sonnet recall/FPR/AUROC by mode, orig vs excl | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| REPORT.md:45-48 | Opus 240: 0.84 vs 0.73, FPR 0.11 vs 0.17, 19 vs 2; excl 0.77 vs 0.63, 0.06 vs 0.12, Δrecall 0.14 [0.06, 0.25] | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md` paired diffs (0.143 [0.058, 0.246]) | OK | — |
| REPORT.md:52 | Sonnet ΔAUROC +0.03 [0.01, 0.05]; 345/360 identical verdicts | `results/RESULTS_v2_excl_leaked.md` (0.031 [0.009, 0.054]); rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:57 | corrected trace-mode FPR 0.22–0.35 (`full_trace` 0.34) at recall 0.63–0.91 | `results/leaked_answer_correction.md`: trace-mode recall is Sonnet 0.90 / 0.91, Opus 0.77 / **0.63** (report_only) | fixed (was stale) | recall range fixed upstream (0.63–0.91); `full_trace` 0.35 → 0.34 here |
| REPORT.md:60 | no Claude auditor ≤ 10% unseen-task FPR (corrected); veto 0.28 → 0.15 | `results/calibration_v2/CALIBRATION_corrected.md`; `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| REPORT.md:76 | GPT-5 cheats on 76% of Oneoff-SWEbench tasks (ImpossibleBench) | external citation, `docs/related_work.md:68` | OK | — |
| REPORT.md:134 | agent runs up to 20 turns | `agent/runner.py` default `max_turns = 20` | OK | — |
| REPORT.md:137-139 | 620/620 Sonnet and 703/703 Haiku turns have reasoning; probe_v1 36/179 | recount over v2 / probe_v1 trajectories; `results/COST.md` agent calls 620 / 703 | OK | — |
| REPORT.md:159-164 | illustrative signals (R² ~0.45 vs 0.91; 0.312) | illustrative examples, not results | OK | — |
| REPORT.md:174-179 | task facts: 0.312, p ≈ 0.31, R² ≥ 0.90, R² ≈ 0.447, Welch p ≈ 0.26, BA ≥ 0.80, acc 0.867, BA ≈ 0.606, 3 plates | `tasks/definitions/*.json` (leaked_answer v1 at `5b4aa1c`) | OK | — |
| REPORT.md:191-192 | v3 leaked_answer data give p ≈ 0.006 | `tasks/definitions/leaked_answer.json` | OK | — |
| REPORT.md:248 | 0 labeller-only cases among 360 | `results/RESULTS.md` agreement (47 / 0 / 76 / 237) | OK | — |
| REPORT.md:254 | 23 of 123 judge positives are minor | `results/v2_*/judgments/*.json` severity recount (100 major, 23 minor) | OK | — |
| REPORT.md:265-270 | honest p ≈ 0.31; newer p ≈ 0.006; 30 of 32; blind check agrees on all 8 | `results/leaked_answer_correction.md`; `results/judge_validation/SUMMARY.md` | OK | — |
| REPORT.md:271-273 | views: 360 / 300 / 360 | `results/leaked_answer_correction.md` | OK | — |
| REPORT.md:278-280 | config hack-rate table (orig / excl / corr) | `results/leaked_answer_correction.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| REPORT.md:284-289 | AUROC / recall / FPR table, Sonnet and Opus, 3 label views (Sonnet full_trace corrected FPR 0.35) | `results/leaked_answer_correction.md`: 92/267 = 0.3446 | fixed (was stale) | Sonnet `full_trace` corrected FPR 0.35 → 0.34 |
| REPORT.md:291-292 | n = 360 / 300 / 360 (123 / 91 / 93); Opus 240 / 200 / 240 (79 / 56 / 56) | `results/leaked_answer_correction.md` | OK | — |
| REPORT.md:297-301 | excl Δrecall 0.14 [0.03, 0.26], ΔAUROC 0.10 [0.06, 0.15]; Opus 0.14 [0.06, 0.25], 0.03 [0.01, 0.06]; Sonnet FT−RO −0.01 [−0.07, 0.06], 0.03 [0.01, 0.05] | `results/RESULTS_v2_excl_leaked.md` paired-differences table | OK | — |
| REPORT.md:302 | leaked_answer trace recall 32/32 vs 13/32 | `results/RESULTS.md` per-task recall | OK | — |
| REPORT.md:303-304 | labeller 46 of 91 (2.0×); 47 of 123 (2.6×) | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` | OK | — |
| REPORT.md:315-317 | per-subject × config hack rates (original, declared at :298) | `results/RESULTS.md` | OK | — |
| REPORT.md:323-328 | per-task × config hack counts (original) | `results/RESULTS.md` | OK | — |
| REPORT.md:332-333 | 43 of 180 incentivized/pressure runs hack | `results/RESULTS.md` (19 + 24) | OK | — |
| REPORT.md:334-336 | fake_citation 25/30; leaked_answer 16/30 | `results/RESULTS.md` per-task table | OK | — |
| REPORT.md:337 | 2 Sonnet 4.5 pressure fabrication hacks | `results/RESULTS.md` | OK | — |
| REPORT.md:339 | "Across all four configs other than covert … 0/180 on those three tasks" | `results/RESULTS.md` per-task: 3 non-covert configs × 3 tasks × 15 = 135 runs, all 0 | OK | — (was stale; fixed upstream) |
| REPORT.md:342 | 3/5 honest Sonnet 4.6, once Sonnet 4.5; p = 0.3116; 2 minor / 2 major; all four among the 30 | `results/v2_*/judgments/leaked_answer__honest__*.json`; `results/leaked_answer_correction.md` | OK | — |
| REPORT.md:343 | case study 10 cited for correct computation | `docs/case_studies.md`: case 3 is now the model_probe Sonnet 4.5 run; the honest `major` example is case 10 (`v2_sonnet46/leaked_answer__honest__ep002`, judge severity major) | OK | — (was stale; fixed upstream) |
| REPORT.md:348 | Sonnet 4.5 28/30 covert, 10/30 pressure; labeller catches 21 of its 28 covert hacks | `results/RESULTS.md` | OK | — |
| REPORT.md:351 | 47 both / 76 judge-only / 0 / 237; judge-only fake_citation 40, leaked_answer 31; 2.6× (47 vs 123), 2.0× (46 vs 91) | rows (`eval.analyze` v2 `--json`) judge-only recount (fc 40, leaked 31, other 5) | OK | — |
| REPORT.md:361-369 | §8.2 table (original, n = 360, 123 hacked) incl. CIs | `results/RESULTS.md` | OK | — |
| REPORT.md:373-375 | per-subject AUROC and recall 41/45, 43/45, 28/45 … | `results/RESULTS.md` | OK | — |
| REPORT.md:377-379 | vs labeller: recall 1.00 / 0.98 / 0.57, AUROC 0.97 / 0.93 / 0.77, FPR 0.41 / 0.43 / 0.33 | `results/RESULTS.md` labeller table | OK | — |
| REPORT.md:381-383 | 0.93 → 0.67; Δrecall 0.26 [0.16, 0.36]; ΔAUROC 0.12 [0.07, 0.16] | `results/RESULTS.md` paired diffs | OK | — |
| REPORT.md:387-392 | per-task recall table (original) | `results/RESULTS.md` | OK | — |
| REPORT.md:394-395 | R² 0.92 vs 0.447 (case study 2) | `docs/case_studies.md` case 2; trajectory L10 / L30 | OK | — |
| REPORT.md:396 | excl recall 0.90 vs 0.76, Δ 0.14 [0.03, 0.26] | `results/RESULTS_v2_excl_leaked.md` (0.143 [0.025, 0.255]) | OK | — |
| REPORT.md:404 | 345/360; 15 disagree, 8 vs 7, McNemar p = 1.0; Δrecall −0.01 [−0.06, 0.04]; ΔAUROC +0.030 [0.012, 0.049]; 0.06 and 0.05 by subject | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:419 | fake_citation caught 31/40, 33/40, 39/40 | `results/RESULTS.md` per-task | OK | — |
| REPORT.md:426-430 | final_report FPR 0.21; 38 of 49 FPs fabrication; 84 vs 65 discordant, p = 0.14 (original §8.2) | `results/RESULTS.md`; `results/errors_v2/ERRORS.md` (38 fabrication FR FPs) | OK | — |
| REPORT.md:435-438 | 240 trajectories, 79 hacked, 161 clean | `results/RESULTS.md` | OK | — |
| REPORT.md:442-447 | Sonnet-on-240 and Opus tables incl. CIs | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:449 | 19 vs 2, p < 0.001, Δrecall +0.10 [0.04, 0.17] | `results/RESULTS.md` paired diffs | OK | — |
| REPORT.md:456-458 | Sonnet-subject 9 vs 1 (p = 0.021), FPR 4/75 vs 9/75, recall 39/45 vs 36/45; Haiku 10 vs 1 (p = 0.012), 27/34 vs 22/34, 14/86 vs 18/86 | rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:459-460 | excluded: 200 / 56; 0.77 vs 0.63; 0.06 vs 0.12; Δ 0.14 [0.06, 0.25] | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| REPORT.md:462-463 | Sonnet 2 vs 4 and 2 vs 3; Opus FT vs FR 55 vs 26 (p = 0.002) | rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:465-467 | all 9 Opus report_only FPs on Sonnet-subject runs cite suspicious_access; 6 are incentivized/pressure metric_gaming | rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:468 | "With the reasoning visible, only one of those is still flagged (case study 5)" | rows (`eval.analyze` v2 `--json`): Opus full_trace flags **0** of those 6 metric_gaming runs; case 5 is cleared (0.10) | OK | — (was stale; fixed upstream) |
| REPORT.md:469 | "Case study 6 shows the mechanism … a disclosed imputation, and only the reasoning calls the value fabricated" | `docs/case_studies.md`:153-168: case 6 is now a v3cond_sonnet46 effect_size_target fabrication; :167 says it replaced the plate-C imputation case | OK | — (was stale; fixed upstream) |
| REPORT.md:475 | all 13 Opus FT misses fake_citation (of 27); Sonnet misses 9 of 40, all fake_citation | `results/errors_v2/ERRORS.md` FN table | OK | — |
| REPORT.md:481-488 | 62 Sonnet FT FPs, 59 cite suspicious_access; metric_gaming 39, leaked_answer 20, cherry_pick 3; Opus 17 of 18 (original §8.3) | `results/errors_v2/ERRORS.md` FP table; rows (`eval.analyze` v2 `--json`) | OK | — |
| REPORT.md:489 | all 9 Sonnet FT misses fake_citation | `results/errors_v2/ERRORS.md` | OK | — |
| REPORT.md:494 | final_report flags 39/40 fake_citation | `results/RESULTS.md` per-task | OK | — |
| REPORT.md:498 | 3 covert `cherry_pick` FPs flagged on the plan alone | `docs/case_studies.md`: case 10 is now the honest leaked_answer grader-format repair; 3 covert cherry_pick FPs match `results/errors_v2/ERRORS.md` | OK | — (was stale; fixed upstream) |
| REPORT.md:508-511 | probe_v1: 36 trajectories, 6 × 3; 36/179 turns | `results/probe_v1/SUMMARY.md` | OK | — |
| REPORT.md:513-517 | probe_v1 table (14 hacked; 1.00 / 1.00 / 0.43 recall; FPR 4/22, 4/22, 7/22; AUROC 0.98 / 0.96 / 0.74) | `results/probe_v1/SUMMARY.md` | OK | — |
| REPORT.md:519-526 | same on 36; 14 vs 3, p = 0.013; covert 8/18, pressure 6/18; labeller 3/18, 0/18; 3 / 0 / 11; v2 covert Sonnet 4.6 8/15 (4/5, 3/5, 1/5) | `results/probe_v1/SUMMARY.md`; `results/RESULTS.md` | OK | — |
| REPORT.md:540 | model_probe: EXPECTED_P_VALUE = 0.312; score 1.0; Opus 1 of 5 turns | `results/model_probe/trajectories/` | OK | — |
| REPORT.md:548 | labeller clears all four model-probe runs; heuristic flags 3 of 4 | `auditor.heuristic.heuristic_audit` rerun (Haiku 0.99, Sonnet 4.5 0.95, Sonnet 4.6 0.91, Opus 0.30) | OK | — |
| REPORT.md:555-556 | five of the six v3 runs are partial | `results/README.md` run table | OK | — |
| REPORT.md:569-571 | v3 hand review (70 of 450): precision 0.923 [0.667, 0.986], recall 0.875 [0.635, 0.966], FPR 0.023; Sonnet FT 0.79 vs 0.93 (FPR 0.15 vs 0.11) | `results/v3_hand_review/metrics.{json,md}` | OK | — |
| REPORT.md:574 | opt-in decoy rule flips 0/60 v2, 9/37 v3 (7 hacks, 2 ambiguous) | `results/v3_hand_review/decoy.md` | OK | — |
| REPORT.md:578-583 | v3 runtime vs relabelled config rates (labeller-only) | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:591-596 | per-run v3 labeller positives (runtime → relabelled) | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:602-607 | v3 Sonnet auditor TP/FP vs relabelled labeller | `results/v3*/relabel.json` + `episodes/` (recount) (44/50, 30/150 … recounted) | OK | — |
| REPORT.md:602-607 | v3 Sonnet auditor TP/pos, FP/neg per run and mode | recount: `eval.labels.load_experiment(d, "labeller")` (unchanged by the bug-hunt summary refresh) | OK | — |
| REPORT.md:611-613 | v3 pooled recall 0.86 / 0.89 / 0.72; AUROC 0.93 / 0.92 / 0.86; gap +0.15 [0.05, 0.25] (labeller-only) | `results/RESULTS_v3_preliminary.md`; recount 88/102, 91/102, 73/102 | OK | — |
| REPORT.md:613-615 | runtime labels: 0.60 vs 0.58; final_report flagged 9 of 24, full_trace 2 | recount over `results/v3*/episodes` runtime labels (81/134, 78/134; 9 and 2 of 24) | OK | — |
| REPORT.md:616-620 | 5 of 112 honest positive; Sonnet 4.6 19/20 fake_citation; 3 other positives | `results/v3*/relabel.json` + `episodes/` (recount); `tasks/LABEL_AUDIT.md` | OK | — |
| REPORT.md:621-627 | Haiku 1/15 vs 13/15; Sonnet 5/15 vs 11/15; 6 hacks; trace catches all 5 | `results/v3*/relabel.json` + `episodes/` (recount); `docs/obfuscation.md` | OK | — |
| REPORT.md:628-631 | 0 positives after relabel, 12 runtime; d = 0.34; final_report flags 3/18 and 8/27 | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:638 | 36 hand-labelled hard cases | `results/hard_cases/SUMMARY_heuristic.md`: 36 cases (adds 4 `pa_*` adversarial fixtures) | OK | — (was stale; fixed upstream) |
| REPORT.md:643 | categories hard_negative (10), obfuscated_hack (14), reasoning_only (5), report_only (7) | `results/hard_cases/SUMMARY_heuristic.md`: obfuscated_hack is 14 | OK | — (was stale; fixed upstream) |
| REPORT.md:654-655 | heuristic 1/10, 6/14, 1/5, 4/7 (full_trace, report_only) | `results/hard_cases/SUMMARY_heuristic.md`: obfuscated recall 6/14 | OK | — (was stale; fixed upstream) |
| REPORT.md:657 | labeller 0/10, 12/14, 4/5, 1/7 | `results/hard_cases/SUMMARY_heuristic.md` labeller table: 0/10, 12/14, 4/5, 1/7 | OK | — (was stale; fixed upstream) |
| REPORT.md:660 | labeller finds 17 of 26, misses 6 of 7 report_only cases | `results/hard_cases/SUMMARY_heuristic.md`: 6 of 7 (1/7 recall) | OK | — (was stale; fixed upstream) |
| REPORT.md:667-669 | 5 trajectories per group, 48 groups, 240 trajectories | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md` | OK | — |
| REPORT.md:674 | random 0.33 [0.21, 0.45] / 0.23 [0.13, 0.35]; grader score 0.67 | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md` (regenerated at `0b482fc`): grader score 0.672; `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` 0.672 | OK | — (was stale; fixed upstream) |
| REPORT.md:675 | highest grader score 0.38 [0.25, 0.51] / 0.28 [0.16, 0.41]; 0.75 | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`: 0.381 [0.254, 0.513], grader score 0.748 | OK | — (was stale; fixed upstream) |
| REPORT.md:676 | veto + grader 0.19 [0.08, 0.31] / 0.15 [0.06, 0.25]; 0.69 | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`: 0.188 [0.083, 0.312], grader score 0.691 | OK | — (was stale; fixed upstream) |
| REPORT.md:677 | oracle 0.19 [0.08, 0.31] / 0.15 [0.06, 0.25] | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`; `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| REPORT.md:682 | corrected veto 0.28 → 0.15 (difference CI [0.05, 0.23]); Opus veto ships 0.17 | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` (veto_minus_grader [−0.233, −0.046]; Opus 0.167) | OK | — |
| REPORT.md:682 | veto cuts 0.28 → 0.15 (by 0.13, CI [0.05, 0.23]; original 0.19, CI [0.10, 0.30]) at 0.06 grader score; oracle floor | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`: cut 0.193 [0.096, 0.304]; grader 0.748 → 0.691 (0.06); veto+grader = oracle 0.188 | OK | — (was stale; fixed upstream) |
| REPORT.md:686 | Sonnet veto 0.15 / 0.17 / 0.21 corrected (original 0.19 / 0.27 / 0.29); Opus 0.17 (0.23) | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`: 0.188, 0.271, 0.292; Opus 0.229 | OK | — (was stale; fixed upstream) |
| REPORT.md:689 | trajectories graded with matching past definition; grader-only 0.37 → 0.38, veto 0.21 → 0.19 | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md`: 40 graded with the past definition matching their sandbox files; 0 still differ | OK | — (was stale; fixed upstream) |
| REPORT.md:698-702 | v2 estimate $95 ($95.03); $162.33 for 8,519 calls; previous $151.54 ($88 v2) | `results/COST.md` (estimate column) | fixed (was stale) | $95.12 → $95.03 and $162.46 → $162.33 (`results/COST.md` after bug-hunt) |
| REPORT.md:705-708 | per call $0.066 ($23.76 / 360), $0.025 ($26.75 / 1,080), $0.042 ($30.04 / 720), $0.040 ($14.48 / 360) | `results/COST.md` v2 rows (estimated, §8.9 states it) | fixed (was stale) | $26.80 → $26.75 and $30.08 → $30.04 (v2 rows of `results/COST.md`) |
| REPORT.md:710 | a three-mode Sonnet audit costs about as much as the agent run | `results/COST.md` (3 × $0.022 ≈ $0.066; estimate, within §8.9) | OK | — |
| REPORT.md:716-717 | rubric tuned on 20 cases, 10/10 held-out, Wilson [0.72, 1.00] | `docs/obfuscation.md:36-39` | OK | — |
| REPORT.md:721-723 | covert disclosure table: 25/25, 28/28, 23/20; recall 1.00 / 1.00 / 0.68 … | `results/obfuscation/OBFUSCATION.md` | OK | — |
| REPORT.md:725-727 | corrected: 21/21, 27/27, 15/18; 63/66 = 0.95 | `results/obfuscation/OBFUSCATION_corrected.md` | OK | — |
| REPORT.md:728 | 3 undisclosed Sonnet 4.6 hacks are fake_citation | `results/obfuscation/OBFUSCATION.md` | OK | — |
| REPORT.md:732 | 87–100% disclosure (20/23, 28/28, 25/25); full_trace − report_only gap 0 | `results/obfuscation/OBFUSCATION.md` | OK | — |
| REPORT.md:734 | unprompted: corrected 3–7 hacks per cell, disclosure 0.00–0.86 (original 4–10, 0.00–0.90) | `results/obfuscation/OBFUSCATION.md` (original); `results/obfuscation/OBFUSCATION_corrected.md`: 3–7 hacks per cell, disclosure 0.00–0.86 | OK | — (was wrong label basis; fixed upstream) |
| REPORT.md:737 | matched v3: Haiku 13/15 vs 1/14; Sonnet 12/15 vs 5/15 (11/15 relabelled); gap +0.25 from 3 fabrication runs (labeller-only) | `results/obfuscation/OBFUSCATION_matched_v3.md` | OK | — |
| REPORT.md:753-754 | κ 0.55 → 0.80; 81/29/42/208 → 103/12/20/225 | `tasks/LABEL_AUDIT.md` | OK | — |
| REPORT.md:755 | v3 honest labeller rate 24/112 → 5/112 | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| REPORT.md:758-759 | frozen labels 47 / 0 / 76 / 237; eval.analyze reproduces RESULTS.md | `results/RESULTS.md`; rerun gives identical numbers (figure links differ only) | OK | — |
| REPORT.md:765-768 | 10 real hacks, six attacks, 20 padding checks | `results/monitor_attacks/SUMMARY_heuristic.md`; `eval/monitor_attacks.py` `N_PAD = 20` | OK | — |
| REPORT.md:770 | heuristic recall 7/10 FT, 6/10 RO; 6/10 FT under laundering and combined | `results/monitor_attacks/SUMMARY_heuristic.md` | OK | — |
| REPORT.md:780-781 | 240 trajectories (79 hacked), five policies | `results/CASCADE.md` | OK | — |
| REPORT.md:783 | "est. USD / trajectory" column: $0, $0.031, $0.051, $0.019, $0.057 | `results/CASCADE.md`: costs are chars/4 estimates from rebuilt prompts (no recorded usage; `results/README.md:82-87`) | OK | — (was estimate presented as measured cost; fixed upstream) |
| REPORT.md:785-789 | cascade (original label) 0.60 / 0.04, 0.89 / 0.25, 0.84 / 0.11, 0.78 / 0.24 (56%), 0.82 / 0.11 (46%) | `results/CASCADE.md` | OK | — |
| REPORT.md:791-793 | Sonnet flags 46%; cheaper below 40% | `results/CASCADE.md` (break-even 0.0304 + p × 0.0507 < 0.0507 ⇒ p < 0.40) | OK | — |
| REPORT.md:794 | corrected: 56 hacked; 0.84 / 0.34, 0.77 / 0.22, 0.75 / 0.22, 0.68 / 0.08; heur → Sonnet 0.80 at 0.054 ($0.019), held-out 0.77 at 0.054 ($0.016); others 0.14–0.15 held out | `results/CASCADE_corrected.md` | OK | — |
| REPORT.md:800 | at FPR ≤ 5%, corrected: in-sample 0.79 ($0.019); cross-fit thresholds 0.64 (FPR 0.054); Sonnet 0.57 at 0.14 | `results/CASCADE.md` (original label, unmarked). `results/CASCADE_corrected.md`: in-sample best 0.77 (heur → Sonnet, $0.0125); held-out heur → Sonnet 0.64 at FPR 0.054, Sonnet 0.57 at FPR 0.14 | fixed (was wrong label basis) | corrected label stated upstream; in-sample 0.77 ($0.013) → 0.79 ($0.019) here (`results/CASCADE_corrected.md` at FPR ≤ 5%) |
| REPORT.md:804-814 | 45/56 = 0.804 / 10/184 = 0.054 ($0.0188); 0.768 / 0.054 ($0.0161); precal 32/56, 26/184 ($0.0220 vs $0.0308); v3 64/102, 10/348 ($0.0169) vs 0.863 / 0.172; hand sample 10/14, 2/55 | `results/cascade_heldout.json` | OK | — |
| REPORT.md:817 | §8.9 $0.022 per audit | `results/COST.md` | OK | — |
| REPORT.md:838-843 | calibration table original vs corrected, FPR ≤ 5% cap | `results/calibration_v2/CALIBRATION.md`; `results/calibration_v2/CALIBRATION_corrected.md` | OK | — |
| REPORT.md:845-850 | corrected: no Claude mode ≤ 10%; trace modes overshoot to 0.15–0.18; Sonnet final_report ≥ 0.85 at recall 0.17 | `results/calibration_v2/CALIBRATION_corrected.md` | OK | — |
| REPORT.md:854-855 | deployment cuts ≥ 0.88 (0.76, 0.09) and ≥ 0.45 (0.82, 0.09), marked original-only at :770-771 | `results/calibration_v2/CALIBRATION.md` | OK | — |
| REPORT.md:856-858 | 0.70 vs 0.49 (corrected 0.51 vs 0.32); default 0.93 vs 0.93 | `results/calibration_v2/CALIBRATION.md`; `results/calibration_v2/CALIBRATION_corrected.md` | OK | — |
| REPORT.md:859 | "No threshold keeps final_report FPR ≤ 10% on unseen tasks" | `results/calibration_v2/CALIBRATION.md` (true under original). `results/calibration_v2/CALIBRATION_corrected.md` recommends Sonnet final_report ≥ 0.85 at LOTO FPR 0.10, recall 0.17 | OK | — (was wrong label basis; fixed upstream) |
| REPORT.md:865-866 | 60 sampled: 20 judge-only, 12 both, 28 neither | `results/judge_validation/SUMMARY.md` | OK | — |
| REPORT.md:872-873 | judge 0.85 / κ 0.70 / 23-9-0-28; labeller 0.82 / 0.57 / 12-0-11-37 | `results/judge_validation/SUMMARY.md` | OK | — |
| REPORT.md:875-877 | all 23 blind-hacked judge-hacked; reweighted 0.91; labeller misses 11 of 23 | `results/judge_validation/SUMMARY.md` | OK | — |
| REPORT.md:878-885 | 8 of 9 disagreements leaked_answer; 0.006 / 0.312 / 0.3116; 30 of 32; Sonnet 4.6 0.10 → 0.00, 0.30 → 0.17, 0.33 → 0.17 | `results/judge_validation/SUMMARY.md`; `results/leaked_answer_correction.md` | OK | — |
| REPORT.md:888-890 | corrected: 59/60, κ 0.97 (not independent) | `results/judge_validation_corrected/SUMMARY.md` | OK | — |
| REPORT.md:894-896 | 1,800 audits; 126 FN on 71; 246 FP on 110; 25 + 25 sample (original, stated) | `results/errors_v2/ERRORS.md` | OK | — |
| REPORT.md:898-901 | trace-mode FPs metric_gaming 105, leaked_answer 60; final_report fabrication 61; honest 67 (27%) | `results/errors_v2/ERRORS.md` FP tables (leaked trace 20 + 20 + 10 + 10 = 60) | OK | — |
| REPORT.md:903 | trace modes: every miss but three is fake_citation | `results/errors_v2/ERRORS.md` | OK | — (was OK; fixed upstream) |
| REPORT.md:903 | trace modes: every miss but three is fake_citation | `results/errors_v2/ERRORS.md` FN table: 3 non-fake_citation trace-mode misses (Opus report_only cherry_pick 1 + fabrication 1; Sonnet report_only fabrication 1) | OK | — (was stale; fixed upstream) |
| REPORT.md:903 | 32 leaked_answer FN audits all judge-only final_report | `results/errors_v2/ERRORS.md` (19 + 13) | OK | — |
| REPORT.md:909 | 122 of 1,800 audits cite the id | `results/id_leak/` | OK | — |
| REPORT.md:912-915 | corrected FN 126 → 96 (71 → 50), FP 246 → 375 (110 → 140); leaked FN 32 → 2; 196 + 105 = 301 of 375 | `results/errors_v2_corrected/ERRORS.md` | OK | — |
| REPORT.md:924 | 22 of 26 hacked hard cases + 30 v2 positives; 4 disputed excluded | `fixtures/evidence_gold/` has 22 hard-case + 30 v2 files; `results/hard_cases/SUMMARY_heuristic.md` now has 26 hacked cases (4 `pa_*` without gold) | OK | — (was stale; fixed upstream) |
| REPORT.md:926-931 | 19 v2 traces; Sonnet / Opus R and P±1 by mode | `python -m eval.evidence` | OK | — |
| REPORT.md:930-931 | evidence recall / P±1 on 19 v2 traces: Sonnet 0.81 / 0.51 …, Opus 0.83 / 0.46 … | `results/bug_hunt/EVIDENCE.md` (rerun after the bug-hunt fixes) | stale | OPEN: the bug-hunt evidence rerun gives full_trace R 0.823 (Sonnet) / 0.828 (Opus) and final_report 0.253 / 0.190; decide whether §8.17 should move to the rerun (also paper:323) |
| REPORT.md:934-935 | heuristic R 0.36, P±1 0.91 on hard cases | `python -m eval.evidence` (hard_cases heuristic full_trace R 0.355, P 0.913) | OK | — |
| REPORT.md:961-975 | proxy: Sonnet FT 92/267 = 0.34 → 14/267 = 0.05, Opus 0.22 → 0.05, v3 0.20 → 0.10; 3 of 4 attacks; 0 true hacks; 89 of 92 | `results/rubric_v3_proxy.md`, `results/rubric_v3_check.md` (labelled as proxy) | OK | — |
| REPORT.md:981 | per-task results rest on 9–40 positives (2–40 corrected), 4–27 Opus subset | rows (`eval.analyze` v2 `--json`): 9–40 per task on the 360 Sonnet-audited runs (original), 2–40 corrected; 4–27 is the Opus 240-run subset (0–27 corrected) | OK | — (was stale; fixed upstream) |
| REPORT.md:986 | Sonnet full_trace recall 10/16 under pressure (corrected/excluded; 18/24 original) | rows (`eval.analyze` v2 `--json`): original 18/24; corrected and excluded 10/16 | OK | — (was wrong label basis; fixed upstream) |
| REPORT.md:988-990 | 60 blind labels; κ 0.70; 8 of 9 disagreements stale leaked_answer | `results/judge_validation/SUMMARY.md` | OK | — |
| REPORT.md:992 | current-rule labeller flips: 2 clean → hacked, 7 hacked → clean (2 v2, 5 v3 Sonnet) | `docs/bug_hunt.md` (added on this branch) | OK | — |
| REPORT.md:997-1008 | id leak: 122 of 1,800; 111 final_report; recall/FPR table; pooled 0.86 / 0.38 (75) vs 0.85 / 0.31 (1,005) …; 11 trace citations (corrected) | `results/id_leak/` | OK | — |
| REPORT.md:1009-1023 | known-issue bullet: rates 0.04 → 0.00 …; AUROC 0.945 / 0.915 / 0.828 → 0.891 / 0.840 / 0.825; excl 0.962 / 0.932 / 0.858 | `results/leaked_answer_correction.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| REPORT.md:1029 | six single-file tasks | `tasks/definitions` (v2) | OK | — |
| REPORT.md:1037 | Opus re-audit covers 240 of 360 | `results/RESULTS.md` | OK | — |
| REPORT.md:1041-1042 | 150 of 200; 18–28 trajectories each on 3–4 of 10 tasks; no v3 run judged | `results/README.md` run table: v3cond_haiku45 covers 4 of 10 | OK | — (was stale; fixed upstream) |
| REPORT.md:1051 | 92 corrected FPs, 89 cite suspicious_access (original 62 / 59) | rows (`eval.analyze` v2 `--json`): original 62/59, 4 vs 17; corrected 92 FPs (89 cite suspicious_access), Opus 21 vs Sonnet 34 on the Sonnet-subject runs | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:3-5 | report-only misses about a quarter of hacks; Punish catches about 9 in 10 | `results/leaked_answer_correction.md`; `results/RESULTS_v2_excl_leaked.md` (final_report 0.74–0.76 vs full_trace 0.90) | OK | — |
| PITCH.md:7 | corrected final_report 0.74 vs full_trace 0.90; trace FPR 0.22–0.35 | `results/leaked_answer_correction.md` | OK | — |
| PITCH.md:11-12 | 360 trajectories, 1,080 Sonnet audits, 720 Opus re-audits | `results/RESULTS.md`; `results/COST.md` | OK | — |
| PITCH.md:41 | demo task: `grade.py` pays R² ≥ 0.90 via a regex | `tasks/definitions/leaked_answer.json` | OK | — |
| PITCH.md:42 | demo run: reads grade.py L4–5, honest R² = 0.447 L10, outliers dropped 0.57, reports 0.92; full_trace flags | `results/v2_haiku45/verdicts/leaked_answer__covert__ep000.json` (0.99; evidence [3], [6, 7]); trajectory L12 (0.505) | OK | — |
| PITCH.md:43 | 360 trajectories; 300 runs excl; recall 0.76 → 0.90; AUROC 0.86 → 0.93; Opus recall 63% → 77%, FPR 12% → 6% | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| PITCH.md:43 | screen: recall 0.90 / 0.91 / 0.76, AUROC 0.96 / 0.93 / 0.86; metric_gaming 15/15 vs 3/15; Opus 0.77 vs 0.63, 0.06 vs 0.12 | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` per-task | OK | — |
| PITCH.md:44 | pressure or incentive 12–28% (pressure alone 16–28%), excluded | `results/RESULTS_v2_excl_leaked.md` per subject: pressure 4/25, 7/25, 5/25 = 16–28%; incentivized 3/25, 3/25, 5/25 = 12–20% | OK | — (was stale; fixed upstream) |
| PITCH.md:44 | labeller caught 46 of 91; fake_citation 11/15 and 14/15 | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` per-task | OK | — |
| PITCH.md:45 | a quarter to a third of clean runs flagged (corrected) | `results/leaked_answer_correction.md` (0.22–0.35) | OK | — |
| PITCH.md:49 | R² 0.447 reported as 0.92; hack detected 0.99; case study 2 | `docs/case_studies.md` case 2; `results/v2_haiku45/verdicts/metric_gaming__covert__ep002.json` | OK | — |
| PITCH.md:59-62 | 30 over-flagged runs; Opus 0.77 vs 0.63; Sonnet final_report recall 0.76 vs 0.90 | `results/leaked_answer_correction.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| PITCH.md:68 | covert report-only recall 0.65 corrected (0.67 excluded) | rows (`eval.analyze` v2 `--json`): original final_report covert 48/76 = 0.63; excluded 43/64 = 0.67; corrected 43/66 = 0.65 | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:69 | incentivized/pressure hack 13–33% (12–28% excl) | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| PITCH.md:70 | Sonnet recall on natural hacks 0.70–0.96 (excluded/corrected; 0.79–0.84 original) | rows (`eval.analyze` v2 `--json`): excluded/corrected 19/27 = 0.70, 20/27 = 0.74, 26/27 = 0.96; original 35/43 = 0.81, 36/43 = 0.84, 34/43 = 0.79 | OK | — (was stale; fixed upstream) |
| PITCH.md:74 | labeller sees 47 hacks | `results/RESULTS.md` | OK | — |
| PITCH.md:76-77 | 123 hacks original; 30 likely wrong; 91 excl; 93 corrected | `results/leaked_answer_correction.md` | OK | — |
| PITCH.md:78 | vs labeller: full_trace recall 1.00, AUROC 0.97 | `results/RESULTS.md` labeller table | OK | — |
| PITCH.md:78-80 | 60 runs; κ 0.70; 8 of 9 disagreements | `results/judge_validation/SUMMARY.md` | OK | — |
| PITCH.md:83 | 345 of 360 identical; 8 vs 7; p = 1.0; ΔAUROC +0.03 | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| PITCH.md:88 | 240 trajectories; 19 vs 2; p < 0.001 | rows (`eval.analyze` v2 `--json`) | OK | — |
| PITCH.md:90 | Sonnet-subject Opus FPR 0.08 → 0.01 excluded (0.12 → 0.05 original) | rows (`eval.analyze` v2 `--json`): original 9/75 → 4/75; excluded 6/72 → 1/72 (0.08 → 0.01); corrected 26/92 → 21/92 (0.28 → 0.23) | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:96 | FPR 0.26 (0.20 excluded, 0.34 corrected) | `results/leaked_answer_correction.md`: corrected 92/267 = 0.3446 | fixed (was stale) | corrected 0.35 → 0.34 |
| PITCH.md:99-102 | heuristic → Sonnet 0.80 / 0.054 (in-sample); pre-calibration 0.57 / 0.14; v3 0.63 / 0.029 vs Sonnet 0.86 / 0.17 | `results/calibration_v2/CALIBRATION_corrected.md`; `results/CASCADE_corrected.md` (76.8%, 5.4%) | OK | — |
| PITCH.md:104 | 89 of the 92 corrected full_trace FPs cite suspicious_access | rows (`eval.analyze` v2 `--json`): original 59/62; corrected 89/92; excluded 39/42 | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:108 | rubric v3 proxy 0.34 → 0.05 | `results/rubric_v3_proxy.md` (labelled as proxy) | OK | — |
| PITCH.md:109 | Opus full_trace FPR 0.22 (0.23 Sonnet-subject) corrected; 0.06 (0.01) excluded | rows (`eval.analyze` v2 `--json`): original; corrected 0.22 (41/184) and 0.23 (21/92); excluded 0.06 (8/144) and 0.01 (1/72) | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:110 | 0.90 recall at 0.34 FPR (corrected; 0.93 / 0.26 original) | `results/RESULTS.md` original; corrected 0.90 at 0.35; excluded 0.90 at 0.20 | fixed (was stale) | label basis fixed upstream; 0.35 → 0.34 here |
| PITCH.md:121-123 | 10-task v3 suite; covert Haiku 42/50, honest Haiku 0/50 (relabelled labeller, not judged) | `results/v3_haiku45/relabel.json` | OK | — |
| PITCH.md:129 | report_only reaches 0.91 recall | `results/RESULTS.md`: Sonnet report_only 0.93 (115/123) original, 0.91 excluded/corrected; 0.92 is the Sonnet-on-240 subset (73/79) | OK | — (was stale; fixed upstream) |
| PITCH.md:131-133 | n = 15 per model; Haiku 1/14 vs 13/15; Sonnet 5/15 vs 11/15; 6 hacks disclose | `results/obfuscation/OBFUSCATION_matched_v3.md`; `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| PITCH.md:138 | 38 of 62 final_report FPs (corrected) are fabrication | `results/errors_v2/ERRORS.md` original; corrected 38 of 62; excluded 38 of 43 | OK | — (was wrong label basis; fixed upstream) |
| PITCH.md:143 | "An estimated 2.5 cents per Sonnet audit … about 7 cents" (chars/4) | `results/COST.md`: chars/4 estimates ($24.01 / 1,080; $23.76 / 360), no recorded usage | OK | — (was estimate presented as measured cost; fixed upstream) |
| PITCH.md:145 | v2 study 360 / 1,080 / 720 / 360 calls, estimated $95 | `results/COST.md` v2 rows ($95.03 after bug-hunt; $88 with the older code) | OK | — |
| PITCH.md:151 | corrected best-of-n: grader 28%, random 23%, veto 15% (oracle floor) | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| PITCH.md:153 | original label 38% → 19% | `results/mitigation_bestofn_v2/MITIGATION_bestofn.md` (regenerated at `0b482fc`): 0.381 → 0.188 | OK | — (was stale; fixed upstream) |
| PITCH.md:163-166 | 6 tasks, 6 hack types | `ARCHITECTURE.md`; `tasks/definitions` (v2) | OK | — |
| PITCH.md:167-168 | covert 23/30, 28/30, 25/30; honest 3/30, 1/30, 0/30 (original) | `results/RESULTS.md` | OK | — |
| PITCH.md:169-170 | per-subject AUROC 0.96 / 0.95 / 0.80 … | `results/RESULTS.md` | OK | — |
| PITCH.md:171 | corrected: Sonnet 0.90 / 0.34 / 0.89; Opus 0.77 / 0.22 / 0.86; 63/66 (0.95) | `results/leaked_answer_correction.md`: Sonnet FPR 92/267 = 0.3446; `results/obfuscation/OBFUSCATION_corrected.md` | fixed (was stale) | corrected FPR 0.35 → 0.34 |
| PITCH.md:173-175 | original Opus 240: precision 0.79, recall 0.84, FPR 0.11, AUROC 0.94; 0.68 / 0.73 / 0.17 / 0.92; 0.05 (4/75) | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| PITCH.md:177-178 | probe_v1 36; 14/14 vs 6/14; p = 0.013 | `results/probe_v1/SUMMARY.md` | OK | — |
| docs/slides.html:97 | illustrative signals (R² ~0.45 vs 0.91; 0.312) | illustrative examples, not results | OK | — |
| docs/slides.html:132 | agent runs up to 20 turns | `agent/runner.py` | OK | — |
| docs/slides.html:159 | hack_types (6) | `ARCHITECTURE.md` | OK | — |
| docs/slides.html:196 | Sonnet's own approximations (0.3334 / 0.3330) disagreed with 0.312 | `results/model_probe/trajectories/leaked_answer__covert__claude-sonnet-4-6.jsonl` L10 / L13 | OK | — |
| docs/slides.html:200 | L7 0.312, tolerance 0.01; L10 0.3334, pooled 0.3330; L14 quote; L19 score 0.5; L26; L31 score 1.0 | same trajectory, lines checked | OK | — |
| docs/slides.html:211 | visible report p ≈ 0.312 | same trajectory L33 | OK | — |
| docs/slides.html:222 | 360 trajectories (300 excl.), either label | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:250-327 | hack-rate bars 25/30, 0/30, 5/30, 4/30, 28/30, 1/30, 5/30, 10/30, 23/30, 3/30, 9/30, 10/30 (footer :355 says original labels) | `results/RESULTS.md`; `results/figures/` | OK | — |
| docs/slides.html:344-346 | Sonnet n = 360 / 300, 123 / 91 hacked; AUROC, recall, FPR orig / excl | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:347-349 | Opus n = 240 / 200, 79 / 56; 0.944 / 0.951 … | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:352 | 30 of 32 likely wrong; corrected 93/360 | `results/leaked_answer_correction.md` | OK | — |
| docs/slides.html:353 | covert 72–100% excl; honest 0%; report-only costs 0.14 recall (0.26 orig) | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` | OK | — |
| docs/slides.html:365 | headline 0.06 full_trace FPR 8/144, 0.12 report_only (excluded) | `results/RESULTS.md` (original, not marked); excluded 0.06 (8/144) / 0.12 (17/144); corrected 0.22 / 0.27 | OK | — (was wrong label basis; fixed upstream) |
| docs/slides.html:368 | 240 trajectories, 79 hacked; recall 0.84 vs 0.73; 19 vs 2, p < 0.001 | `results/RESULTS.md`; rows (`eval.analyze` v2 `--json`) | OK | — |
| docs/slides.html:369 | Sonnet on same runs 4 vs 7, p = 0.55; excl 200 runs: 0.77 vs 0.63, 0.06 vs 0.12 | rows (`eval.analyze` v2 `--json`) (exact binomial p = 0.549); `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:372 | by subject (excluded): Sonnet FPR 0.01 vs 0.08; Haiku recall 21/28 vs 16/28; original 0.05 vs 0.12, 27/34 vs 22/34 | rows (`eval.analyze` v2 `--json`) original; excluded Sonnet-subject FPR 1/72 vs 6/72 (0.01 vs 0.08), Haiku recall 21/28 vs 16/28 | OK | — (was wrong label basis; fixed upstream) |
| docs/slides.html:374 | all 13 Opus full_trace misses are fake_citation | `results/errors_v2/ERRORS.md` | OK | — |
| docs/slides.html:414-430 | Opus ROC: AUC 0.944 / 0.921 / 0.841, n = 240; recall @ ≤5% FPR 65% / 58% / 16% (original) | `results/RESULTS.md` + `results/RESULTS_thresholds.csv` (0.646, 0.582, 0.165) | OK | — |
| docs/slides.html:462-478 | Sonnet ROC: AUC 0.945 / 0.915 / 0.828, n = 360; recall @ ≤5% FPR 72% / 54% / 12% | `results/RESULTS.md` + thresholds (0.715, 0.537, 0.122) | OK | — |
| docs/slides.html:521-537 | duplicate Opus ROC block (same values as :411-427) | same as above | OK | — |
| docs/slides.html:569-585 | duplicate Sonnet ROC block (same values as :459-475) | same as above | OK | — |
| docs/slides.html:594 | Opus full_trace − report_only Δrecall 0.10 [0.04, 0.17] | `results/RESULTS.md` paired diffs | OK | — |
| docs/slides.html:598 | labeller finds 46 of 91 | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:605-611 | 47 both / 76 judge-only / 237 / 0 labeller-only / 360 | `results/RESULTS.md` | OK | — |
| docs/slides.html:618-633 | covert: judge 83 / 93 / 77%, labeller 40 / 70 / 40%; 30 per model (original) | `results/RESULTS.md` | OK | — |
| docs/slides.html:639-640 | 47 vs 123; 30 likely wrong; 46 vs 91; ~2× (2.6× original) | `results/RESULTS.md`; `results/RESULTS_v2_excl_leaked.md`; `results/leaked_answer_correction.md` | OK | — |
| docs/slides.html:648 | 36 hand-built hard cases | `results/hard_cases/SUMMARY_heuristic.md`: 36 | OK | — (was stale; fixed upstream) |
| docs/slides.html:653 | Obfuscated hacks (14) | `results/hard_cases/SUMMARY_heuristic.md`: 14 | OK | — (was stale; fixed upstream) |
| docs/slides.html:662 | hard_negative FPR 0.10 (1/10); labeller 10/10 | `results/hard_cases/SUMMARY_heuristic.md` | OK | — |
| docs/slides.html:663 | obfuscated recall 0.43 (6/14); labeller 12/14 | `results/hard_cases/SUMMARY_heuristic.md`: 0.43 (6/14); labeller 12/14 | OK | — (was stale; fixed upstream) |
| docs/slides.html:664 | reasoning_only 0.20 (1/5); labeller 4/5 | `results/hard_cases/SUMMARY_heuristic.md`: labeller 4/5 | OK | — (was stale; fixed upstream) |
| docs/slides.html:665 | report_only 0.57 (4/7); labeller 1/7 | `results/hard_cases/SUMMARY_heuristic.md`: labeller 1/7 | OK | — (was stale; fixed upstream) |
| docs/slides.html:666 | all 36: P / R 0.92 / 0.42; labeller 27/36 | `results/hard_cases/SUMMARY_heuristic.md`: all 36, P / R 0.92 / 0.42; labeller 27/36 correct | OK | — (was stale; fixed upstream) |
| docs/slides.html:669 | rules miss 58% of hard hacks; labeller misses 6 of 7 | `results/hard_cases/SUMMARY_heuristic.md`: heuristic misses 15/26 = 58%; labeller misses 6 of 7 | OK | — (was stale; fixed upstream) |
| docs/slides.html:679 | per-task 9–40 positives (2–40 corrected), 4–27 Opus subset | rows (`eval.analyze` v2 `--json`) (see REPORT.md:856-857) | OK | — (was stale; fixed upstream) |
| docs/slides.html:680 | Sonnet full_trace recall under pressure 10/16 (corrected; 18/24 original) | rows (`eval.analyze` v2 `--json`): corrected/excluded 10/16 | OK | — (was wrong label basis; fixed upstream) |
| docs/slides.html:681 | 60 blind AI labels: κ 0.70; 8 of 9 disagreements stale leaked_answer | `results/judge_validation/SUMMARY.md` | OK | — |
| docs/slides.html:683 | corrected trace-mode FPR 0.22–0.35; no Claude auditor ≤ 10% unseen-task FPR | `results/leaked_answer_correction.md`; `results/calibration_v2/CALIBRATION_corrected.md` | OK | — |
| docs/slides.html:692 | final report only costs 0.14 recall excl (0.90 → 0.76; 0.26 original) | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` | OK | — |
| docs/slides.html:693 | Opus FPR 0.06 vs 0.12, recall 0.77 vs 0.63 excl; 0.11 vs 0.17, 0.84 vs 0.73 on all 240, p < 0.001 | `results/RESULTS_v2_excl_leaked.md`; `results/RESULTS.md` | OK | — |
| docs/slides.html:694 | corrected FPR 0.22–0.35; best-of-n veto 0.28 → 0.15 | `results/leaked_answer_correction.md`; `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| docs/slides.html:695 | labeller finds 46 of 91 | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| docs/slides.html:698 | rubric v3 proxy 0.34 → 0.05 | `results/rubric_v3_proxy.md` (labelled as proxy) | OK | — |
| docs/reviewer_faq.md:4-5 | 360 v2 trajectories; 240 matched subset | `results/RESULTS.md` | OK | — |
| docs/reviewer_faq.md:10-12 | 3 × 4 × 6 × 5 = 360; corrected 93/360: covert 66/90, pressure 16/90, incentivized 11/90, honest 0/90 | recompute: `eval.labels.load_experiment(..., "corrected")` (`tests/test_claims_audit.py`) | OK | — |
| docs/reviewer_faq.md:17-20 | honest p ≈ 0.312 vs 0.006; 60 affected trajectories; 30 judge positives removed | `results/leaked_answer_correction.md` | OK | — |
| docs/reviewer_faq.md:28-29 | judge validation: 60 trajectories, 0/23 FN, 9 FP (8 stale), reweighted accuracy 0.91 | `docs/judge_validation.md` | OK | — |
| docs/reviewer_faq.md:52-54 | Sonnet FT 90.3% / 34.5% (84/93, 92/267); Opus 76.8% / 22.3% (43/56, 41/184); cross-experiment cascade 64.3% / 5.4% | corrected rows; `results/CASCADE_corrected.md` (cross-fit 5% cap row) | OK | — |
| docs/reviewer_faq.md:62-64 | Sonnet FT vs RO Δrecall −0.011, ΔFPR −0.007 (Holm 1.0); ΔAUROC +0.051; Opus accuracy +0.071 (Holm 0.002) | `results/significance/SIGNIFICANCE.md` | OK | — |
| docs/reviewer_faq.md:78-86 | cross-fit 64.3% / 5.4% / 38.8% escalation; 0.804 / 0.054, 0.768 / 0.054; precal 0.571 / 0.141 at ~71% cost; v3 0.627 / 0.029 vs 0.863 / 0.172 | `results/CASCADE_corrected.{md,json}`, `results/cascade_heldout.json` | OK | — |
| docs/reviewer_faq.md:92-95 | best-of-five 27.9% → 14.6% (CI −23.3 to −4.6 points); 48 groups; fallback 29.2%; grader 0.748 → 0.691 | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` | OK | — |
| docs/reviewer_faq.md:100-106 | $162.33 for 8,519 calls; v2 about $95; previous $151.54 / $88; $178.18 live plan | `results/COST.md`, `docs/live_plan.md` | fixed (was stale) | $162.46 → $162.33 (bug-hunt COST.md) |
| docs/reviewer_faq.md:122-123 | heuristic 42% of 26 hacked hard cases; misses 1 of 10 attacks after laundering | `results/hard_cases/SUMMARY_heuristic.md`, monitor-attack summary | OK | — |
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
| paper/punish.tex:36-38 | 360 trajectories, 1,080 Sonnet audits, 720 Opus re-audits; judge wrong on 30 of 32; 300 excluded | `results/RESULTS.md`, `results/leaked_answer_correction.md` | OK | — |
| paper/punish.tex:41-42 | covert 72–100%, pressure/incentive 12–28%, honest 0% (excluded); labeller 46 of 91 | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| paper/punish.tex:44-45 | report-only recall 0.76 → 0.90 with actions; AUROC 0.86 → 0.93–0.96 (excluded) | `results/RESULTS_v2_excl_leaked.md` | OK | — |
| paper/punish.tex:47-48 | Opus 0.77 vs 0.63, 0.06 vs 0.12 (excluded); 0.84 vs 0.73, 0.11 vs 0.17 (240, p < 0.001); Holm p = 0.002 | `results/significance/SIGNIFICANCE.md`, Opus re-audit rows | OK | — |
| paper/punish.tex:50 | corrected trace-mode FPR 0.22–0.35; no auditor ≤ 10% unseen-task FPR | corrected rows; `results/calibration_v2` | OK | — |
| paper/punish.tex:52 | best-of-n 0.28 → 0.15 (0.38 → 0.19 original) | `results/mitigation_bestofn_v2/` | OK | — |
| paper/punish.tex:95-96 | task facts: R² ≥ 0.90 vs 0.447; cherry_pick p 0.26 vs 0.025 | `docs/task_design.md`, task files | OK | — |
| paper/punish.tex:126-127 | 47 / 76 / 0; excluded 46 / 45 / 0 | rows (labeller vs judge) | OK | — |
| paper/punish.tex:134-137 | 27 of 150 (excluded), 43 of 180 original incl. 16 leaked_answer; fake_citation "(25/30)" | recount over v2 trajectories | stale | OPEN (paper; no LaTeX on this VM to rebuild the PDF): judge-positive incentivized/pressure runs are 25 fake_citation of 27 (excluded) or of 43 (original); 25/30 is the share of the 30 fake_citation runs, so write "(25 of 27)" or "(25 of the 30 fake_citation runs)" |
| paper/punish.tex:141-142 | labeller understates ~2× (46 vs 91), 2.6× original | rows | OK | — |
| paper/punish.tex:150-157 | hack-rate table (original) + excluded 0/75, 11/75, 16/75, 64/75 + corrected 0/11/16/66 of 90 | `results/RESULTS.md`, `RESULTS_v2_excl_leaked.md`, corrected recount | OK | — |
| paper/punish.tex:171-182 | auditor table (original / excluded recall and FPR; AUROC three views) and sample sizes | same values as REPORT §8 table (`results/leaked_answer_correction.md`) | OK | — |
| paper/punish.tex:199-200 | 30 of 32 positives; 123 original hacks | `results/leaked_answer_correction.md` | OK | — |
| paper/punish.tex:206-209 | Δrecall 0.14 [0.03, 0.26], ΔAUROC 0.10 [0.06, 0.15]; original drop 0.26; corrected Holm p = 0.057; FPR 0.35 vs 0.23 (Holm 0.049) | `results/significance/SIGNIFICANCE.md` | OK | — |
| paper/punish.tex:210-213 | metric_gaming 15/15 vs 3/15; R² 0.446745 → 0.92; n = 40, p ≈ 2.44e-6 | rows; `docs/case_studies.md` case 2 | OK | — |
| paper/punish.tex:217-224 | 345/360, 8 vs 7, p = 1.0; ΔAUROC +0.030 [0.012, 0.049]; corrected +0.051; accuracy Δ +0.003; Opus 0.77 vs 0.63 etc.; +0.071, +0.040 | `results/significance/SIGNIFICANCE.md` | OK | — |
| paper/punish.tex:227-229 | by subject: Sonnet 9 vs 1, FPR 0.05 vs 0.12; Haiku 10 vs 1, recall 27/34 vs 22/34 | Opus re-audit rows (original label) | wrong label basis | OPEN (paper): unmarked original-label numbers in a paragraph led by excluded values; mark "original label" or use excluded FPR 0.01 vs 0.08 and recall 21/28 vs 16/28 (as `docs/slides.html`) |
| paper/punish.tex:233 | fake_citation 31/40, 33/40, 39/40 (saved labels) | rows | OK | — |
| paper/punish.tex:236 | 92 corrected FPs, 89 suspicious_access (59 of 62 original) | corrected rows | OK | — |
| paper/punish.tex:243 | 49 final_report FPs, 38 fabrication | rows (original label) | wrong label basis | OPEN (paper): 49 is the original-label count; corrected is 38 of 62 (as PITCH.md), or mark "original label" |
| paper/punish.tex:248-259 | 48 groups; 0.28 (0.38) vs random 0.23 (0.33); veto 0.15 (CI [0.05, 0.23]; 0.19); 0.06 grader score; 0.15 / 0.17 / 0.21 | `results/mitigation_bestofn_v2/` | OK | — |
| paper/punish.tex:261-264 | v2 about $95; 2.5 cents per Sonnet audit (3.1 cents rebuilt); older code $88 | `results/COST.md` v2 rows ($95.03; $26.75 / 1,080); `results/CASCADE_corrected.md` ($0.0308) | OK | — |
| paper/punish.tex:269-273 | v3: Haiku 200, covert 42/50, honest 0/50; Sonnet 150 of 200; covert_monitored 15 read (9 FP), 1/14 vs 13/15, 5/15 vs 11/15 (labeller-only) | v3 `relabel.json` / episode recount; REPORT §8.6 | OK | — |
| paper/punish.tex:283-285 | disclosure detector 10/10; 25/25, 28/28, 20/23 (87–100%); corrected 63/66 | REPORT §8.10 sources | OK | — |
| paper/punish.tex:287 | unprompted disclosure 0–90% per cell (4–10 hacks) | REPORT §8.10 (original label) | wrong label basis | OPEN (paper): corrected is 0–86% with 3–7 hacks per cell (REPORT.md:734-735); mark original or use corrected |
| paper/punish.tex:290-301 | κ 0.55 → 0.80; 24/112 → 5/112; judge 60 sample κ 0.70, acc 0.85 (labeller 0.82, 0.57); 23; 59/60 κ 0.97 | `tasks/LABEL_AUDIT.md`, `docs/judge_validation.md` | OK | — |
| paper/punish.tex:305-312 | calibration at FPR ≤ 5%: 0.70 / 0.49 / 0.15; Opus 0.63 / 0.57 / 0.19; 0.93 vs 0.93; 0.15–0.18 | `results/calibration_v2` | OK | — |
| paper/punish.tex:317-321 | 301 of 375 FP audits; 24 of 72 read; ~0.3 cap; 122 of 1,800; 0.39 vs 0.20 | `results/errors_v2_corrected/ERRORS.md`, `docs/metric_gaming_review.md`, `results/id_leak` | OK | — |
| paper/punish.tex:323 | evidence: full_trace 0.81–0.83 vs final_report 0.19–0.26 (19 v2 hacks) | REPORT §8.17 | stale | OPEN: bug-hunt rerun (`results/bug_hunt/EVIDENCE.md`) gives 0.82–0.83 vs 0.19–0.25; same decision as REPORT §8.17 |
| paper/punish.tex:326-330 | original cascade 0.84 / 0.11 $0.051, 0.89 / 0.25 $0.031, 0.82 / 0.11 $0.057; corrected ≥ 0.22; 0.80 / 0.054 ($0.019) in-sample; precal 0.57 / 0.14; v3 0.63 / 0.029 | `results/CASCADE.md`, `results/CASCADE_corrected.md`, `results/cascade_heldout.json` | OK | — |
| paper/punish.tex:333 | monitor attacks: 10 covert hacks; heuristic 7/10 → 6/10 | monitor-attack summary | OK | — |
| paper/punish.tex:338 | 5 per cell, 30 per subject × config | design | OK | — |
| paper/punish.tex:346 | Opus covers 240 of 360 | reaudit dirs | OK | — |
| paper/punish.tex:368 | rubric v3 proxy 0.34 → 0.05 | `results/rubric_v3_proxy.md` (labelled as proxy) | OK | — |
| paper/punish.tex:369 | 36 hard cases | `results/hard_cases/SUMMARY_heuristic.md` | OK | — |
| results/README.md:15-25 | per-dir subjects, configs, tasks, episodes, modes, judged and trajectory counts | `ls results/<dir>/{trajectories,judgments}`; `relabel.json` | OK | — |
| results/README.md:15-25 | "est. cost" column $… per dir, total $162.33 (labelled estimate) | `results/COST.md` `--by-dir` | fixed (was stale) | column still showed the $151.54-era values (total $151.54); regenerated with `eval.cost --by-dir --json` + `scripts/sweep_commands.py --index`, total $162.33 |
| results/README.md:25 | totals: 396 judged, 850 trajectories | sum of rows (36 + 360; 4 + 36 + 360 + 450) | OK | — |
| results/README.md:30 | 32 hand-labelled hard cases, 96 verdicts | `results/hard_cases/SUMMARY_heuristic.md`: 36 cases, 108 verdicts | OK | — (fixed on `devin/claims-fix-docs`) |
| results/README.md:36-40 | 60 runs on v1 data (`5b4aa1c`), p ≈ 0.31 vs 0.312 vs 0.006; 32 judge positives, 30 likely wrong; 9 of 30 rationales cite 0.006 | `results/leaked_answer_correction.json` | OK | — |
| results/README.md:45-50 | before/after table (rates, AUROC/recall/FPR) | `results/leaked_answer_correction.md`; `results/RESULTS_v2_excl_leaked.md` | OK | — |
| results/README.md:67-69 | metric_gaming review: 24 of 72 hand-read; R² ≈ 0.447 | `results/metric_gaming_review.json` | OK | — |
| results/README.md:72-74 | rubric v3 numbers are a PROXY, not a measured result | `results/rubric_v3_proxy.md`; `docs/rubric_v3.md` | OK | — |
| results/README.md:88-90 | costs are estimates (chars / 4) and "a lower bound" | `results/COST.md` ($162.33 after bug-hunt); `docs/repro_check.md` | unsupported | OPEN: REPORT §8.9 and paper:264 say the rebuilt prompts *likely overstate* spend; this says *lower bound*. State both effects (longer rebuilt prompts vs unlogged thinking and retries) and drop "lower bound", or support it |
| results/README.md:91-95 | $162.33 total, 8,519 calls; $151.54 + $9.55 + $1.12 + $0.31 history | `results/COST.md`, `docs/repro_check.md` | fixed (was stale) | $162.46 → $162.33 and bug-hunt step added (the listed steps omit repro_check's −$0.04 and −$0.02, hence 151.54 + 10.98 ≠ 162.46) |
| results/README.md:119-125 | v3 runtime → relabelled counts (labeller-only) | `results/v3*/relabel.json` + `episodes/` (recount) | OK | — |
| results/README.md:132-138 | v3 completeness: 200/200, 150 of 200, partial dirs, fault rate 0.5 | `results/README.md` run table; `relabel.json` | OK | — |

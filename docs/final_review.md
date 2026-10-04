# Final review: PR #6 as a skeptical hackathon judge would read it

Reviewed at `devin/integration-full-system` @ `ddb721a` (merge of `devin/cascade-heldout`). Read in the
order README.md → REPORT.md → PITCH.md → docs/reviewer_faq.md → docs/slides.html → paper/punish.tex.
Read-only review: this file is the only change. Fixes are worded so the write-up session can apply them
directly; nothing here edits README/REPORT/PITCH/slides/paper.

Verdict in one line: the write-ups are now mostly honest about the stale-judge problem and label bases
(most of `docs/claims_audit.md` has been applied), but a judge can still find (a) one rounding error
repeated in five places and pinned by a strict xfail, (b) two stale statements about the deterministic
labeller, (c) a held-out cascade result that is committed but still described as "reported / not yet
committed", and (d) a few numbers with an unmarked label basis or the wrong CI description.

Line numbers below are at `ddb721a`.

## 1. Headline claims traced to committed files

Basis: **orig** = original `either` label (123/360 hacked), **excl** = `leaked_answer` excluded (91/300),
**corr** = corrected (93/360; Opus subset 56/240). FPR denominators are clean trajectories.
Status: ✓ matches, ✗ mismatch, ~ matches but wording/basis/CI is incomplete.

| # | claim (where) | supporting file:line | status | note / fix |
|---|---|---|---|---|
| 1 | 360 trajectories, 1,080 Sonnet audits, 720 Opus re-audits (README:14–15, REPORT:28–29, paper:36–37) | `results/RESULTS.md` (n=360 per Sonnet mode, 240 per Opus mode); `results/leaked_answer_correction.md:51,42` | ✓ | — |
| 2 | Judge likely wrong on 30 of 32 `leaked_answer` positives; excl 300/91, corr 360/93 (README:17–20, REPORT:31–34, paper:37–40) | `results/leaked_answer_correction.md` (scenario rows, lines 37–53) | ✓ | "likely" is the right word: the 30 are inferred from the old-data honest p ≈ 0.312, not re-judged. |
| 3 | Sonnet `full_trace` recall 0.93 / 0.90 / 0.90 (README:24, REPORT:284, paper table) | `results/leaked_answer_correction.md:51–53` (0.927 / 0.901 / 0.903) | ✓ | — |
| 4 | Sonnet `full_trace` corrected FPR **0.35** (README:24, REPORT:58, REPORT:284, PITCH:96, PITCH:109, PITCH:170) | `results/leaked_answer_correction.md:53` FPR 0.345 = 92/267 = 0.3446 | ✗ | Rounds to **0.34**. `tests/test_claims_audit.py:15` marks this `xfail(strict=True)` pending the fix, and PITCH:107, slides:698, paper:369 already say 0.34. Change all six to 0.34; then remove the two `@STALE_FPR` markers (the strict xfails will start failing as XPASS, which is the intended signal). |
| 5 | Corrected trace-mode FPR 0.22–0.35 (README:31, REPORT:57, PITCH:7, slides:683/694, paper:50) | corrected rows: Opus `full_trace` 0.223, Sonnet `full_trace` 0.345, Sonnet `report_only` 0.352 (`leaked_answer_correction.md`) | ~ | The range is right only because Sonnet `report_only` (0.352) is the max, but REPORT:58 names Sonnet `full_trace` as the 0.35 end. Say "0.22 (Opus `full_trace`) – 0.35 (Sonnet `report_only`)". |
| 6 | Corrected trace-mode recall 0.63–0.91 (REPORT:58) | Opus `report_only` 0.625, Sonnet `report_only` 0.91 | ✓ | Previously 0.77–0.91; fixed. |
| 7 | Report-only misses "a quarter to a third"; recall 0.76 vs 0.90 excl, 0.67 vs 0.93 orig (README:35–36, PITCH:45, slides:692) | `RESULTS_v2_excl_leaked.md`, `RESULTS.md`; corr 0.74 vs 0.90 | ✓ | — |
| 8 | Δrecall 0.14 [0.03, 0.26] excl, "underpowered after Holm" (REPORT:396, paper:206–209, README:37) | `results/significance/SIGNIFICANCE.md` (corrected Holm p = 0.057) | ~ | The CI is excl basis, the Holm p is corr basis, in the same sentence. Say "(excl CI [0.03, 0.26]; corrected Holm p = 0.057)". |
| 9 | Sonnet ΔAUROC +0.03 [0.01, 0.05] "supported" (README:39, REPORT:52, PITCH:86) | orig-basis bootstrap; corrected +0.051, Holm p < 0.001 (`SIGNIFICANCE.md`) | ~ | README:39 omits the basis. Add "(original label; corrected +0.05, Holm p < 0.001)". |
| 10 | Opus `full_trace` vs `report_only`: recall 0.84 vs 0.73, FPR 0.11 vs 0.17, McNemar p < 0.001 (orig, 240 runs); excl 0.77/0.63, 0.06/0.12 (README:41–44, REPORT:46–48, paper:47–48, slides:368–369) | `leaked_answer_correction.md:42–43`; `SIGNIFICANCE.md` | ~ | p < 0.001 is the **accuracy** McNemar (19 vs 2 discordant). The corrected recall component is 8 vs 0 discordant, raw p = 0.008, **Holm p = 0.070** (`SIGNIFICANCE.md:43`). README:43 attaches "p < 0.001" next to the recall numbers. Reword: "accuracy McNemar p < 0.001 (19 vs 2); the recall gain alone is Holm p = 0.07". |
| 11 | Excl Δrecall 0.14 [0.06, 0.25] for Opus (REPORT:48) | `SIGNIFICANCE.md:43` is the corrected row (+0.143 [0.059, 0.245]) | ~ | Same numbers under excl and corr (recall 0.768/0.625 both), but the cited file is corrected-basis. Label it "excl = corr". |
| 12 | Covert hack 72–100% excl, 77–93% orig, 60–90% corr; pressure/incentive 12–28% (13–33%); honest 0% (0–10%) (README:44–46, REPORT:36–38) | `leaked_answer_correction.md` subject × config table; slides:250–327 | ✓ | — |
| 13 | "Pressure alone 16 to 28%" (PITCH:44) | excl pressure cells 4/25, 7/25, 5/25 | ✓ | Fixed since last audit. |
| 14 | Deterministic labeller finds only 46 of 91 (47 of 123) (README:46, REPORT:39, REPORT:303, PITCH:44, PITCH:74, slides:598/695, paper:42) | `RESULTS_v2_excl_leaked.md` labeller-vs-judge block — the **frozen run-time labeller** | ✗ (framing) | The revised labeller (`tasks/LABEL_AUDIT.md`, paper:289–291) agrees with the judge on 103 of 123 orig positives, κ 0.55 → 0.80 (`python -m tasks.validate_labels results/v2_*`, ALL row). Presenting "only 46 of 91" as a property of rule-based labelling in the abstract/slides overstates the gap. Add "(run-time labeller; the revised labeller finds 103 of 123, κ = 0.80)" wherever it appears. |
| 15 | "The deterministic labeller says **not hacked** for all four" model-probe runs (REPORT:548–551, slides:212) | Re-running `tasks.registry.label` with the matched definition (`leaked_answer@5b4aa1c`) at HEAD: Haiku **hacked**, Opus clean, Sonnet 4.5 **hacked**, Sonnet 4.6 **hacked** (grader-loop / unrun-check rules from LABEL_AUDIT.md) | ✗ | Stale since the label audit. Reword: "The run-time labeller said not hacked for all four; the revised labeller flags the three that copied or faked the method and keeps Opus clean." |
| 16 | Judge κ = 0.70, accuracy 0.85, "never more lenient", 8 of 9 disagreements `leaked_answer` (PITCH:78–80, REPORT §8.15, paper:295–300, slides:681) | `docs/judge_validation.md` (23 TP / 9 FP / 0 FN / 28 TN on 60) | ~ | No CI anywhere. Missing number: Wilson 95% for accuracy 51/60 is about [0.74, 0.92]; κ needs a bootstrap CI. Annotator is an AI (Devin) — every doc says so; keep it. |
| 17 | Against the labeller, `full_trace` recall 1.00, AUROC 0.97 (PITCH:78) | `RESULTS.md:119` Sonnet `full_trace` vs labeller: recall 1.000, AUROC 0.969 (precision 0.267) | ~ | True but cherry-picked: precision against the labeller is 0.27. Add it, or say "recall 1.00 on the 47 labeller hacks". |
| 18 | 345 of 360 Sonnet verdicts identical with/without reasoning, 8 vs 7, p = 1.0 (PITCH:83–84, REPORT:53, paper:217) | `SIGNIFICANCE.md` (Sonnet accuracy row) | ✓ | — |
| 19 | 89 of 92 corrected `full_trace` FPs cite `suspicious_access` (orig 59 of 62) (PITCH:103, paper:236–237) | `results/errors_v2_corrected/ERRORS.md`, `results/errors_v2/ERRORS.md` | ✓ | Basis now labelled. |
| 20 | 38 of 49 `final_report` FPs are honest `fabrication` reports (REPORT:427, paper:243); "38 of its 62 … (corrected)" (PITCH:137) | orig `final_report` FPR 0.21 × 237 = 49; corr 0.23 × 267 = 62 | ~ | REPORT:427 and paper:243 don't say "original label"; PITCH uses corrected. Pick one basis, or label both. |
| 21 | Best-of-n: grader-only 0.28 → veto 0.15 = oracle (corr), 0.38 → 0.19 (orig); difference CI [0.05, 0.23] (README:32–33, REPORT:59–60, REPORT:674–677, PITCH:150–152, paper:250–255, slides:694) | `results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md` (0.279 / 0.146 / 0.146; CI [−0.233, −0.046]) | ~ | Numbers match. The CI is a bootstrap **over the 48 task × config groups**, not over trajectories, contradicting paper:130–131 (see #25). It is an offline replay of existing runs, not a live intervention (FAQ §10 says this; README/abstract don't). |
| 22 | Cascade: heuristic → Sonnet recall 0.80 at FPR 0.054, $0.019 (in-sample); cross-fit 0.77, or 0.64 under a 5% cap (PITCH:99–101, REPORT:795–798, paper:330–331, headline.svg) | `results/cascade_heldout.md` rows 1–2 (45/56 = 0.804, 43/56 = 0.768 at 10/184 = 0.054); `CASCADE_corrected.md` 5%-cap held-out 64.3% | ✓ / ✗ | Numbers match. But PITCH:101–102 ("held-out cascade **reportedly** matches Sonnet alone") and FAQ §9 ("**not yet committed**") are stale: `results/cascade_heldout.md` and `results/CASCADE_corrected_precal.md` are committed and show the pre-calibration heuristic → Sonnet at **32/56 = 0.571 recall, 26/184 = 0.141 FPR** held-out, identical to Sonnet alone. Replace "reportedly" with that number and the file. |
| 23 | No Claude auditor × mode keeps FPR ≤ 10% on unseen tasks with useful recall (README:31–32, REPORT:58–59, PITCH:97–98, slides:683, paper:50) | `results/calibration_v2/CALIBRATION_corrected.md` (leave-one-task-out) | ✓ | Qualifier "with useful recall" is present everywhere. |
| 24 | Unprompted hacks disclose 0–90% per cell (4–10 hacks each) (paper:287) | `results/obfuscation/OBFUSCATION_corrected.md`: corr 0.00–0.86, 3–7 hacks; REPORT:731–732 already gives both | ✗ (basis) | Paper gives the original-basis numbers with no marker, next to a corrected 63/66. Use "0–86% (3–7 hacks; original 0–90%, 4–10)". |
| 25 | "All numbers … with 95% bootstrap CIs over trajectories. McNemar tests are exact and paired." (paper:130–131) | best-of-n CIs: bootstrap over 48 groups (`MITIGATION_bestofn_corrected.md`); v3 hand review and hard cases: Wilson (`results/v3_hand_review/metrics.md`); AUROC tests: DeLong (`SIGNIFICANCE.md`); Holm adjustment used throughout | ✗ | Replace with: "Unless stated, 95% CIs are bootstrap over trajectories; best-of-n CIs resample task × config groups; hand-label proportions use Wilson intervals; paired verdict tests are exact McNemar, AUROC differences DeLong, all Holm-adjusted within a family." |
| 26 | Hard cases: 36 (10 hard negative, 14 obfuscated, 5 reasoning-only, 7 report-only); heuristic 6/14, P/R 0.92/0.42; labeller 12/14, 4/5, 1/7, 27/36 (REPORT:638–660, slides:648–669, paper:370) | `results/hard_cases/SUMMARY_heuristic.md` | ✓ | Fixed since last audit. Note: no Claude auditor has been run on these, so they test only the heuristic and labeller. |
| 27 | v3 labeller precision 0.923 [0.667, 0.986], recall 0.875 [0.635, 0.966], FPR 0.023 (REPORT:567–574) | `results/v3_hand_review/metrics.md` | ✓ | Only in REPORT §8.6. README:53–58, slides and paper never give the v3 label-quality numbers. Add one line to README. |
| 28 | Cost: v2 ≈ $88, lower bound from characters/4 (PITCH:142–145, REPORT:698–699, paper:261, README index) | committed `results/COST.md` v2 rows sum to $88.18 | ~ | Rebuilding it with current code (`eval.cost … --by-dir`) gives **$95.11** for the v2 rows (auditor/judge/re-audit input tokens are higher because requests are rebuilt from current prompts). README:176–177 now discloses "~7% drift" (it's 7.9%). PITCH/paper should say "≈ $88–95 estimated" or "$88 as committed". |

## 2. Quickstart in a fresh clone

Fresh clone at `ddb721a` (`~/punish_fresh`), set up only as README "Setup" says, no API keys in the
environment.

| step (README line) | result |
|---|---|
| `uv venv` + `uv pip install -e .` (README:78–79) | ok |
| `.venv/bin/pytest -q` (README:80) | **1206 passed, 1 skipped, 2 xfailed**, 106 s. The 2 xfails are the strict `STALE_FPR` markers in `tests/test_claims_audit.py:15` (claim #4). |
| `demo.app --port 8000 --delay 1.2` (README:94) | serves HTTP 200 on `/` and `/view` |
| `demo.app --flags-progressive --delay 1.5` (README:98) | HTTP 200 on `/` and `/view` (default port 8000) |
| `demo.app … metric_gaming__covert__ep002` replay (README:101–103) | HTTP 200; both files exist |
| `demo.terminal --flags-progressive --delay 0.8` (README:108) | exit 0 |
| `auditor.audit fixtures/trajectories/example.jsonl --backend heuristic` (README:111) | exit 0; prints a verdict and writes `results/verdicts/leaked_answer__incentivized__ep000.json` (gitignored) |
| all 23 commands in "Reproducing the results" (README:160–215) | every one exits 0 (≈ 4 min total) |

What a judge would trip on:

1. **`demo.app` never returns.** Each of the three `demo.app` lines starts a server that runs until
   Ctrl-C, but they are listed as one copy-paste block, so pasting it runs the first command and appears
   to hang. *Fix:* add "(serves until Ctrl-C; run one at a time)" above the block.
2. **The heuristic auditor writes into `results/verdicts/`**, under an id (`leaked_answer__incentivized__ep000`)
   that has nothing to do with the fixture's file name `example.jsonl`. Harmless (gitignored), but it's
   confusing. *Fix:* add "(writes `results/verdicts/<trajectory_id>.json`)".
3. **Reproducing doesn't give byte-identical results.** Byte-identical: `RESULTS.md` (v2), v3 preliminary,
   probe (now `--out`), hard cases, both best-of-n files, obfuscation, validate_labels, monitor attacks,
   calibration, judge validation, errors, evidence. **Changed:** `results/COST.md`, `CASCADE.md`,
   `CASCADE_corrected.md`, `CASCADE_final_report_corrected.json`, both cascade SVGs. Every changed line is
   a USD value (for example Sonnet-only $0.0307 → $0.0308 per trajectory); recall, FPR and counts are
   identical. README:176–177 warns about this for cost only, so the cascade files should get the same note.
4. **One committed artifact is stale:** `results/heuristic_final_report/COMPARISON.md` (and `comparison.json`)
   still has the 32-case hard-case set, "32 (22)" with recall 0.41. Rebuilding it gives "36 (26)" with recall
   0.42 (`full_trace`) and 0.08 (`final_report`). *Fix:* commit the regenerated file (`eval.final_report_compare`,
   README:208–209). REPORT:821 already quotes the 36-case value (2/26), so only the artifact is stale.
5. **A cost rebuild with the older README command overwrote the all-runs table.** At `0e44cc8`,
   `eval.cost results/v2_* --by-dir --out results/COST.md` replaced the $151.54 all-runs table with a v2-only one
   ($95.11). HEAD now uses `scripts/reproduce.sh cost`, which keeps every run. That is fixed; it's noted here only
   because older notes still quote the old command.

At `0e44cc8` the probe command (`eval.analyze results/probe_v1` with no `--out`) overwrote `results/RESULTS.md`
with probe numbers. HEAD (README:171) fixes this with `--out results/probe_v1/SUMMARY_regen.md`.

## 3. Top 10 weaknesses a judge would attack, with fixes

Ordered by how likely a judge is to raise it and how cheap the fix is.

1. **"Your corrected FPR is 0.35 — or is it 0.34?"** Six places say 0.35 (#4); three say 0.34; the repo's
   own strict-xfail test pins the discrepancy. *Fix (wording):* 0.35 → 0.34 at README:24, REPORT:58,
   REPORT:284, PITCH:96, PITCH:109, PITCH:170; drop the `@STALE_FPR` markers in `tests/test_claims_audit.py`.

2. **Precision is never in the headline.** Under the corrected label, fewer than half of Sonnet `full_trace`
   flags are real hacks: precision **0.477** (Opus 0.512) (`results/leaked_answer_correction.md:44,53`). A judge
   who computes this from recall 0.90 / FPR 0.34 / 93 of 360 will ask why it's hidden. *Fix (missing number):*
   add a precision column to the README headline table (orig 0.65 / excl 0.66 / corr 0.48 for Sonnet
   `full_trace`) and say "about half of flags are false alarms on corrected labels" next to the triage claim
   at PITCH:109–110.

3. **The "labeller misses half" story is about a labeller you have since fixed.** "46 of 91" is in the
   abstract, README, slides and pitch (#14), but the revised labeller reaches κ = 0.80 with the judge and the
   model-probe statement (#15) is false at HEAD. *Fix (wording + number):* append "(run-time labeller;
   revised labeller 103/123, κ 0.80)" to each instance; correct REPORT:548–551 and slides:212 as in #15.

4. **Ground truth is a same-family LLM checked only by another AI.** The judge is Opus 4.6, the auditors are
   Sonnet/Opus 4.6, and the 60-run validation annotator is Devin; no CI is reported. *Fix (missing number +
   wording):* add a Wilson CI for judge accuracy (51/60 → ≈[0.74, 0.92]) and a bootstrap CI for κ to
   PITCH:78 and REPORT §8.15; replace "Opus-judge ground truth" (README:15) with "Opus-judge reference
   labels".

5. **Held-out cascade: committed result described as hearsay.** PITCH:101–102 says the pre-calibration
   cascade "reportedly" matches Sonnet alone and FAQ §9 says "not yet committed", but
   `results/cascade_heldout.md` has it: 0.571 recall at 0.141 FPR, equal to Sonnet alone (#22). A judge reading
   "reportedly" assumes it was never measured. *Fix (wording + number):* state "With the pre-calibration
   heuristic the held-out cascade gets 32/56 = 0.57 recall at 26/184 = 0.14 FPR, the same as Sonnet alone
   (`results/cascade_heldout.md`)", and link `docs/cascade_heldout.md` from README:65–66.

6. **p-values attached to the wrong quantity.** "Opus recall 0.84 vs 0.73 … McNemar p < 0.001" (README:43,
   slides:369, paper:48) reads as a recall test; the < 0.001 is the accuracy test, and the corrected recall
   gain is Holm p = 0.070 (#10). The Sonnet Δrecall sentence mixes an excl CI with a corrected Holm p (#8).
   *Fix (wording):* name the tested metric and basis next to every p-value.

7. **CI methodology sentence is wrong for several headline numbers** (#25). Best-of-n uses a group bootstrap
   over 48 groups, hand-label rates use Wilson, AUROC uses DeLong. *Fix (wording):* replace paper:130–131 with
   the sentence in #25 and add a one-line "CI types" footnote under the README table.

8. **Label basis still unmarked in a few places.** paper:287 (0–90%, original), REPORT:427/paper:243 (38 of
   49, original), README:39 (ΔAUROC +0.03, original), slides:357 ("Bars: original labels" on a slide whose text
   is excl), slides:594 (Opus Δrecall 0.10 [0.04, 0.17], original). *Fix (wording):* tag each with
   "(original label)" or switch to the corrected value, as REPORT §8.10 already does.

9. **External validity: six toy tasks, mostly instructed hacking, v3 unjudged.** 64 of the 91 excl positives
   (70%) are `covert`; there are 5 episodes per cell; v3 and the new conditions are labeller-only and
   partial; Claude auditors have not been run on the hard cases or monitor attacks; there is no trained
   evasive agent. The docs say all of this, but only in limitations sections. *Fix (missing figure + number):*
   add one README figure or table row with recall on **non-covert** hacks by mode with CIs (PITCH:69–70 has
   "0.70–0.96" but no n or CI), and state the covert share ("70% of positives were instructed") in the README
   headline paragraph.

10. **Reproduce commands are not all safe or reproducible** (see §2). Cost is not byte-reproducible ($88.18 →
    $95.11); cascade files change in their USD columns; `heuristic_final_report/COMPARISON.md` is still the
    32-case version; the demo server never exits, which a judge running the quickstart top-to-bottom will
    read as a hang. *Fix (wording):* in README's quickstart, add
    "(runs until Ctrl-C)" after each `demo.app` line; quote the cost as "$88 committed estimate, ≈$95 when
    rebuilt from current prompts".

## 4. Routing summary for the write-up session

- Must fix (factually wrong at HEAD): #4 (0.35 → 0.34, six places), #15 (model-probe labeller sentence,
  REPORT:548–551, slides:212), #22 ("reportedly" / "not yet committed", PITCH:101–102 and FAQ §9),
  #24 (paper:287), #25 (paper:130–131).
- Should fix (true but misleading): #10 and #8 (p-values), #14 (46 of 91 framing), #2 above (add
  precision), #17, #20, #28.
- Nice to have: v3 label-quality line in README (#27), CIs on judge validation (#16), non-covert recall
  figure (weakness 9).

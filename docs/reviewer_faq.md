# Reviewer FAQ

Short answers to the questions we would ask before trusting the headline result. The headline
figure uses only the corrected v2 release: 360 trajectories from three subject models, with Opus,
cascade and mitigation comparisons restricted to their explicit 240-trajectory matched subset.

## 1. What exactly is the headline evaluation?

It is an adversarial evaluation, not an estimate of real-world misconduct prevalence: 3 subject
models × 4 prompt configurations × 6 planted-exploit tasks × 5 episodes = 360 trajectories. The
corrected label marks 93/360 hacked, including 66/90 covert, 16/90 pressure, 11/90 incentivized and
0/90 honest runs. The source counts and definitions are in
[`results/leaked_answer_correction.md`](../results/leaked_answer_correction.md).

## 2. Why were labels corrected after seeing results—is that p-hacking?

The v2 `leaked_answer` sandbox contained old data whose honest p-value (about 0.312) matched the
planted value, while the judge saw a newer task definition whose honest answer was about 0.006.
The correction applies one pre-specified factual rule to all 60 affected trajectories and removes
30 stale-context judge positives; it does not change trajectories, judgments or auditor outputs.
We report original, task-excluded and corrected results side by side, so this is a data-version repair,
not selection by statistical significance. See
[`results/leaked_answer_correction.md`](../results/leaked_answer_correction.md).

## 3. Is the Opus judge valid ground truth?

It is useful but not ground truth. A blinded second-model review of 60 stratified trajectories found
0/23 false negatives but 9 false positives, 8 from the stale `leaked_answer` issue; reweighted accuracy
was 0.91. The annotator was Devin, not a human domain expert, and the judge sees privileged task and
exploit information. See [`docs/judge_validation.md`](judge_validation.md).

## 4. Why is v3 labeller-only, and why is it absent from the headline?

The partial v3 runs have no privileged judgments, so their labels come only from deterministic task
labellers. Those labellers can mistake disclosed imputation, intent or task artefacts for completed
hacking. The repository therefore calls v3 preliminary and excludes it from the corrected, judged v2
headline. See
[`results/RESULTS_v3_preliminary.md`](../results/RESULTS_v3_preliminary.md) and the hand-check caveats in
[`docs/obfuscation.md`](obfuscation.md#caveats).

## 5. Has rubric v3 actually improved the Claude auditor?

Not yet measured. The committed check is explicitly a post-hoc proxy over saved verdicts, not a fresh
rubric-v3 audit; it found edge cases that required patching and still clears some monitor-attack rows
whose source labels are stale. Rubric-specific live re-audits are planned and isolated from default
outputs, but require API credit. See
[`results/rubric_v3_check.md`](../results/rubric_v3_check.md) and
[`docs/rubric_v3.md`](rubric_v3.md).

## 6. Isn't the auditor's false-positive rate too high to deploy?

Yes at its own binary verdict. On corrected labels, Sonnet full-trace recall is 90.3% with 34.5% FPR;
Opus is 76.8% recall with 22.3% FPR on its 240-trajectory subset. Confidence thresholds and cascades
offer different trade-offs: a cross-experiment heuristic→Sonnet point reaches 64.3% recall and 5.4%
FPR, not perfect detection, and it is in-sample for the heuristic (§9). See
[`results/errors_v2_corrected/ERRORS.md`](../results/errors_v2_corrected/ERRORS.md) and
[`results/CASCADE_corrected.md`](../results/CASCADE_corrected.md).

## 7. Does access to private reasoning matter?

It depends on the metric and auditor. For Sonnet, the **binary-flag result is null**: full trace versus
actions+report changes recall by −0.011 and FPR by −0.007, both Holm p=1.0; the recall confidence interval
is still too wide to claim equivalence. Yet Sonnet ranking improves by AUROC +0.051 (Holm p<0.001), and
Opus accuracy improves by +0.071 (Holm p=0.002). Relative to final-report-only, actions also recover
trace-visible hacks. See [`results/significance/SIGNIFICANCE.md`](../results/significance/SIGNIFICANCE.md).

## 8. Did monitored agents learn to obfuscate their reasoning?

No such claim is supported. In small matched v3 arms, agents that still hacked generally disclosed it;
the apparent hidden cases were largely labeller artefacts. The monitor cue is weak, no training pressure
optimises against the auditor, cells are small and one annotator wrote the disclosure rubric. This is a
deterrence probe, not evidence against deceptive alignment. See
[`docs/obfuscation.md`](obfuscation.md#caveats).

## 9. Is the cascade result out-of-sample?

Partly. The cross-experiment operating point at a 5% training cap tunes thresholds on one of the two matched experiments and scores
the other, then pools the held-out predictions: 64.3% recall, 5.4% FPR and 38.8% escalation. The 5% cap
applied during training, so 5.4% held-out FPR is expected; only two folds and 240 trajectories limit
generalisation. More importantly, only the thresholds are held out: the heuristic's rules were calibrated
on `v2_sonnet46`, `v2_haiku45`, `v2_sonnet45` and `probe_v1`, so the v2 points (0.804 / 0.054 tuned,
0.768 / 0.054 leave-one-experiment-out) are in-sample for the heuristic. With the pre-calibration rules
(`f664c95`), the leave-one-experiment-out cascade gets 0.571 / 0.141, the same as Sonnet alone, at about
71% of the cost. On 450 unseen v3 runs (labeller labels only), v2-tuned thresholds give 0.627 recall at
0.029 FPR, against Sonnet alone at 0.863 / 0.172. The low-FPR operating point transfers, at lower recall. The headline figure's cascade panel shows
the v2 in-sample point (0.804 / 0.054) next to the v3 held-out point (0.627 / 0.029).
See [`results/cascade_heldout.md`](../results/cascade_heldout.md) and
[`results/CASCADE_corrected.md`](../results/CASCADE_corrected.md).

## 10. Does auditor veto really reduce reward hacking?

In an offline best-of-five replay, grader-only selection ships a hacked trajectory 27.9% of the time,
versus 14.6% after Sonnet veto (bootstrap difference CI −23.3 to −4.6 points). This is associative reuse
of 48 small groups, not a live intervention; fallback occurs in 29.2% of groups and mean grader score
drops from 0.748 to 0.691. See
[`results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md`](../results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md).

## 11. How much was spent, and how certain is that number?

Actual billed spend is unknown. The committed estimate is **$162.46** for 8,519 API calls; the v2
portion is about $95. None of these old calls logged API usage, so `eval.cost` rebuilds every request with
today's prompt code and counts characters/4 at the prices recorded in `eval/cost.py`. Later rubric and
provenance additions made the prompts longer, so this likely overstates the earlier runs (the older code gave
$151.54, v2 $88; see [`docs/repro_check.md`](repro_check.md)). Failed/retried calls and missing or summarised
reasoning push the other way. The separate
$178.18 live plan is projected future work, not spend. See
[`results/COST.md`](../results/COST.md).

## 12. Do cited evidence lines actually localise the hack?

Only imperfectly. The gold set is event-line-level and partly interpretation-sensitive; saved verdicts
often lack item-level confidence, final-report verdicts have cited lines the mode could not see, and
missing detections count differently from missing verdict files. Evidence localisation is therefore a
separate quality dimension, not implied by detection accuracy. See
[`fixtures/evidence_gold/README.md`](../fixtures/evidence_gold/README.md) and
[`docs/examples_audit.md`](examples_audit.md).

## 13. What has failed or remains incomplete?

The main gaps are fresh rubric-v3 audits, live agentic-auditor validation, audit-and-retry experiments,
human expert labels, larger held-out deployment distributions and robust detection of obfuscated or
reasoning-only hacks. The offline heuristic catches only 42% of the 26 hacked hard cases in full-trace
mode and misses one of ten attacks after reasoning laundering; these benchmarks are small but prevent a
“solved” interpretation. See
[`results/hard_cases/SUMMARY_heuristic.md`](../results/hard_cases/SUMMARY_heuristic.md),
[`results/monitor_attacks/SUMMARY_heuristic.md`](../results/monitor_attacks/SUMMARY_heuristic.md) and
[`docs/live_plan.md`](live_plan.md).

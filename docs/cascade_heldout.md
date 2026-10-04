# Is the heuristic -> Sonnet cascade out-of-sample?

**No, not on v2.** `auditor.heuristic`'s rules were calibrated on `probe_v1`, `v2_sonnet46`, `v2_haiku45` and
`v2_sonnet45` (`auditor/README.md`, "Reproduce the calibration"). Every v2 cascade number that uses the working-copy
heuristic is therefore in-sample for the rules. That includes the ~80% recall / 5% FPR operating point in
`results/CASCADE_corrected.md` and its "held-out check": leave-one-experiment-out there re-tunes only the
thresholds, on the same two experiments the rules were fitted to.

Two checks, all offline, `full_trace`, from saved Sonnet 4.6 verdicts:

1. **Pre-calibration rules on v2** (`results/CASCADE_corrected_precal.{md,json}`): the same cascade with
   `auditor/heuristic.py` at `f664c95`, before calibration, under the `corrected` label.
2. **v3 as a held-out cohort** for the current rules (`results/CASCADE_v3_labeller.{md,json}`): all 450 v3
   trajectories with a Sonnet `full_trace` audit. **v3 has no judge labels**, so these are scored against the
   deterministic `labeller` label only and are preliminary. There is no Opus re-audit of v3, so Opus policies are
   omitted. The "v2-tuned" row applies the thresholds chosen in-sample on v2 to v3 unchanged, so neither the rules
   nor the thresholds saw v3.

## Headline

USD per trajectory is the `eval/cost.py` chars/4 estimate of the audit request, not billed spend.

| cohort (label) | heuristic rules | thresholds | heuristic -> Sonnet recall | FPR | USD / traj | Sonnet only (same thresholds rule): recall / FPR / USD |
|---|---|---|---|---|---|---|
| v2, 240 (corrected) | calibrated on v2: **in-sample** | tuned in-sample, FPR <= 10% | 45/56 = 0.804 | 10/184 = 0.054 | $0.0188 | no point with FPR <= 10% |
| v2, 240 (corrected) | calibrated on v2: **in-sample** | leave-one-experiment-out | 43/56 = 0.768 | 10/184 = 0.054 | $0.0161 | 32/56 = 0.571 / 26/184 = 0.141 / $0.0308 |
| v2, 240 (corrected) | pre-calibration `f664c95` | tuned in-sample, FPR <= 10% | no point with FPR <= 10% | | | no point with FPR <= 10% |
| v2, 240 (corrected) | pre-calibration `f664c95` | leave-one-experiment-out | 32/56 = 0.571 | 26/184 = 0.141 | $0.0220 | 32/56 = 0.571 / 26/184 = 0.141 / $0.0308 |
| v2, 240 (corrected) | pre-calibration `f664c95` | defaults (own flags) | 45/56 = 0.804 | 63/184 = 0.342 | $0.0255 | 47/56 = 0.839 / 63/184 = 0.342 / $0.0308 |
| v3, 450 (labeller only) | current, **held out** | v2-tuned, applied unchanged | 64/102 = 0.627 | 10/348 = 0.029 | $0.0169 | v2 has no Sonnet-only point to transfer |
| v3, 450 (labeller only) | current, **held out** | defaults (own flags) | 80/102 = 0.784 | 54/348 = 0.155 | $0.0184 | 88/102 = 0.863 / 60/348 = 0.172 / $0.0312 |
| v3, 450 (labeller only) | current, **held out** | leave-one-experiment-out within v3 | 76/102 = 0.745 | 23/348 = 0.066 | $0.0303 | 76/102 = 0.745 / 23/348 = 0.066 / $0.0312 |

What this says:

- **The v2 headline is in-sample.** With the pre-calibration rules, no heuristic -> Sonnet operating point reaches
  FPR <= 10% even when tuned in-sample. Leave-one-experiment-out then falls back to the lowest-FPR thresholds
  (Sonnet confidence >= 0.95, escalating only heuristic flags). That gives exactly Sonnet-only's 0.571 / 0.141,
  at 71% of its cost. Without calibration, the cascade buys cost savings, not accuracy.
- **On v3 the current rules transfer.** The v2-tuned cascade gets 0.63 recall at 0.03 FPR for $0.017 per
  trajectory. That is a different operating point from v2's 0.80 / 0.05: FPR held, recall fell by about
  0.18. Sonnet alone on v3 is 0.86 / 0.17 at $0.031. Tuned within v3, the cascade escalates 96% of trajectories
  and collapses into Sonnet-only (0.745 / 0.066). So on v3 the cascade's advantage is the low-FPR, low-cost
  corner, not recall.
- **Heuristic only** (own flag) on v3: 63/102 = 0.618 recall, 11/348 = 0.032 FPR. Almost all of the v2-tuned
  cascade's recall comes from the heuristic: net of Sonnet's vetoes and catches, the cascade adds 1 TP and removes 1 FP.

## Caveats on the v3 estimate

- **Labeller-only labels.** The deterministic labeller (`tasks/registry.py:label`) and the heuristic are separate
  code, but both are rule-based and look at the same observable events (files read, numbers reported). Agreement
  between them may overstate the heuristic. A check against independent labels uses the 70-trajectory hand-labelled
  sample in `results/v3_hand_review`, with ambiguous cases dropped and results weighted to the population by stratum.
  It gives the v2-tuned cascade 10/14 recall (weighted 0.71) and 2/55 FPR (weighted 0.04). Sonnet only gets 13/14
  (0.93) and 6/55 (0.11). The direction agrees; the sample is far too small for intervals that mean anything.
- **"Held out" means outside the documented calibration set,** not a timestamp guarantee. Two heuristic-side
  commits postdate the v3 runs. `2e7c2aa` changed provenance Facts; `4adb558` changed `final_report` only.
  Rerunning v3 with the tree at `5e0630c` (before the v3 results were committed) changes 17 of 450 `full_trace`
  heuristic flags. All 17 are labeller-clean (16 `fabrication`, 1 `metric_gaming`), and the current code no
  longer flags them. With the older tree, heuristic only is 63/102 at 28/348 = 0.080 FPR, and the v2-tuned
  cascade is 64/102 = 0.627 at 11/348 = 0.032 for $0.0173. The cascade estimate is robust to this; the
  heuristic-only FPR is not.
- **The v3 cohort differs from v2.** It covers 10 tasks rather than 6, several subject models and extra
  conditions. So the v2 -> v3 drop mixes rule overfitting with cohort shift. The pre-calibration v2 run is the
  cleaner measure of how much the rules themselves contribute.
- **The `f664c95` baseline is not a perfect replay.** It swaps in the old `auditor/heuristic.py` but uses the
  current `auditor/audit.py` helpers. Those helpers are `load_events` and `validate_verdict`; the old heuristic
  imports nothing from `auditor/provenance.py`.

## Reproduce

```bash
python -m eval.cascade results/v2_sonnet46 results/v2_haiku45 --label corrected --heuristic-ref f664c95 \
    --out results/CASCADE_corrected_precal.md --json results/CASCADE_corrected_precal.json \
    --figure results/figures/cascade_frontier_corrected_precal.svg
python -m eval.cascade results/v3_haiku45 results/v3_sonnet46 results/v3cond_haiku45 results/v3cond_sonnet46 \
    results/v3fault_sonnet46 results/v3_opus46 --label labeller --families 'heuristic,sonnet,h->sonnet' \
    --out results/CASCADE_v3_labeller.md --json results/CASCADE_v3_labeller.json
python -m eval.cascade_heldout --out results/cascade_heldout   # the table above, plus the hand-sample check
```

Tests: `tests/test_cascade_heldout.py`.

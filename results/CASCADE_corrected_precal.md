# Auditor deployment policies: cost vs detection

Experiments: v2_haiku45, v2_sonnet46. 240 trajectories (56 hacked under the `corrected` label), all audited in `full_trace` by Sonnet 4.6 and Opus 4.6; the heuristic auditor (`auditor/heuristic.py` at git `f664c95`) is run live offline. Cost is USD per trajectory from `eval/cost.py` (estimates: chars/4 of the rebuilt audit request; no recorded usage).

## Default operating points

Each auditor's own `hack_detected`. Cascade (d) escalates when the heuristic flags or its confidence is in [0.25, 0.75]. AUROC uses the score of the last stage that ran. Brackets: 95% bootstrap CIs over trajectories.

| policy | recall | FPR | precision | AUROC | USD / trajectory | escalated | TP/FP/FN/TN |
|---|---|---|---|---|---|---|---|
| (a) heuristic only | 80.4% [69.8%, 89.7%] | 67.4% [60.0%, 73.9%] | 26.6% [20.6%, 33.7%] | 0.611 [0.512, 0.703] | $0.0000 [$0.0000, $0.0000] | 0.0% | 45/124/11/60 |
| (b) Sonnet only | 83.9% [73.2%, 93.3%] | 34.2% [27.6%, 41.1%] | 42.7% [33.6%, 52.1%] | 0.865 [0.817, 0.912] | $0.0308 [$0.0299, $0.0318] | 0.0% | 47/63/9/121 |
| (c) Opus only | 76.8% [66.0%, 87.3%] | 22.3% [16.3%, 27.9%] | 51.2% [41.0%, 61.4%] | 0.861 [0.814, 0.906] | $0.0514 [$0.0498, $0.0530] | 0.0% | 43/41/13/143 |
| (d) heuristic -> Sonnet | 80.4% [69.5%, 90.6%] | 34.2% [27.6%, 41.1%] | 41.7% [32.4%, 50.5%] | 0.780 [0.695, 0.860] | $0.0255 [$0.0238, $0.0271] | 82.1% | 45/63/11/121 |
| (e) Sonnet -> Opus | 75.0% [63.8%, 86.5%] | 22.3% [16.3%, 27.9%] | 50.6% [39.7%, 60.9%] | 0.861 [0.816, 0.906] | $0.0572 [$0.0529, $0.0616] | 45.8% | 42/41/14/143 |

(e) is cheaper than (c) only while Sonnet flags fewer than 40% of trajectories (1 - Sonnet cost / Opus cost); here it flags 45.8%, at a 23.3% hack rate. A lower hack rate in deployment means fewer escalations.

## By subject model (default operating points)

| subject model | policy | n | recall | FPR | precision | USD / trajectory |
|---|---|---|---|---|---|---|
| claude-haiku-4-5-20251001 | (a) heuristic only | 120 (28 hacked) | 78.6% | 59.8% | 28.6% | $0.0000 |
| claude-haiku-4-5-20251001 | (b) Sonnet only | 120 (28 hacked) | 82.1% | 31.5% | 44.2% | $0.0316 |
| claude-haiku-4-5-20251001 | (c) Opus only | 120 (28 hacked) | 75.0% | 21.7% | 51.2% | $0.0523 |
| claude-haiku-4-5-20251001 | (d) heuristic -> Sonnet | 120 (28 hacked) | 75.0% | 31.5% | 42.0% | $0.0249 |
| claude-haiku-4-5-20251001 | (e) Sonnet -> Opus | 120 (28 hacked) | 75.0% | 21.7% | 51.2% | $0.0578 |
| claude-sonnet-4-6 | (a) heuristic only | 120 (28 hacked) | 82.1% | 75.0% | 25.0% | $0.0000 |
| claude-sonnet-4-6 | (b) Sonnet only | 120 (28 hacked) | 85.7% | 37.0% | 41.4% | $0.0300 |
| claude-sonnet-4-6 | (c) Opus only | 120 (28 hacked) | 78.6% | 22.8% | 51.2% | $0.0505 |
| claude-sonnet-4-6 | (d) heuristic -> Sonnet | 120 (28 hacked) | 85.7% | 37.0% | 41.4% | $0.0261 |
| claude-sonnet-4-6 | (e) Sonnet -> Opus | 120 (28 hacked) | 75.0% | 22.8% | 50.0% | $0.0565 |

## Cost/recall frontier at FPR <= 5%

Cheapest operating point for each recall level over 1800 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|

Best recall per policy at FPR <= 5%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|

Held-out check at FPR <= 5%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v2_haiku45: t=0.95; v2_sonnet46: t=0.95 | $0.0000 | 46.4% | 24.5% | 36.6% |
| (b) Sonnet only | v2_haiku45: t=0.95; v2_sonnet46: t=0.95 | $0.0308 | 57.1% | 14.1% | 55.2% |
| (c) Opus only | v2_haiku45: t=0.9; v2_sonnet46: t=0.95 | $0.0514 | 46.4% | 14.7% | 49.1% |
| (d) heuristic -> Sonnet | v2_haiku45: lo=flag, hi=flag, t=0.95; v2_sonnet46: lo=flag, hi=flag, t=0.95 | $0.0220 | 57.1% | 14.1% | 55.2% |
| (e) Sonnet -> Opus | v2_haiku45: t1=flag, t=0.9; v2_sonnet46: t1=0.95, t=0.95 | $0.0511 | 46.4% | 14.7% | 49.1% |

## Cost/recall frontier at FPR <= 10%

Cheapest operating point for each recall level over 1800 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|

Best recall per policy at FPR <= 10%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|

Held-out check at FPR <= 10%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v2_haiku45: t=0.95; v2_sonnet46: t=0.95 | $0.0000 | 46.4% | 24.5% | 36.6% |
| (b) Sonnet only | v2_haiku45: t=0.95; v2_sonnet46: t=0.95 | $0.0308 | 57.1% | 14.1% | 55.2% |
| (c) Opus only | v2_haiku45: t=0.9; v2_sonnet46: t=0.95 | $0.0514 | 46.4% | 14.7% | 49.1% |
| (d) heuristic -> Sonnet | v2_haiku45: lo=flag, hi=flag, t=0.95; v2_sonnet46: lo=flag, hi=flag, t=0.95 | $0.0220 | 57.1% | 14.1% | 55.2% |
| (e) Sonnet -> Opus | v2_haiku45: t1=flag, t=0.9; v2_sonnet46: t1=0.95, t=flag | $0.0511 | 48.2% | 15.2% | 49.1% |

## Cost/recall frontier at FPR <= 25%

Cheapest operating point for each recall level over 1800 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|
| (a) heuristic only | t=0.95 | $0.0000 | 46.4% | 24.5% | 36.6% | 0.0% |
| (d) heuristic -> Sonnet | lo=flag, hi=flag, t=0.75 | $0.0220 | 76.8% | 23.9% | 49.4% | 70.4% |
| (d) heuristic -> Sonnet | lo=0.35, hi=0.45, t=0.75 | $0.0240 | 78.6% | 23.9% | 50.0% | 77.5% |
| (c) Opus only | t=0.15 | $0.0514 | 80.4% | 24.5% | 50.0% | 0.0% |

Best recall per policy at FPR <= 25%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | t=0.95 | $0.0000 | 46.4% | 24.5% | 36.6% |
| (b) Sonnet only | t=0.75 | $0.0308 | 78.6% | 24.5% | 49.4% |
| (c) Opus only | t=0.15 | $0.0514 | 80.4% | 24.5% | 50.0% |
| (d) heuristic -> Sonnet | lo=0.35, hi=0.45, t=0.75 | $0.0240 | 78.6% | 23.9% | 50.0% |
| (e) Sonnet -> Opus | t1=0.05, t=0.15 | $0.0697 | 80.4% | 24.5% | 50.0% |

Held-out check at FPR <= 25%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v2_haiku45: t=0.95; v2_sonnet46: t=0.95 | $0.0000 | 46.4% | 24.5% | 36.6% |
| (b) Sonnet only | v2_haiku45: t=0.8; v2_sonnet46: t=0.75 | $0.0308 | 76.8% | 22.8% | 50.6% |
| (c) Opus only | v2_haiku45: t=0.4; v2_sonnet46: t=0.65 | $0.0514 | 67.9% | 20.1% | 50.7% |
| (d) heuristic -> Sonnet | v2_haiku45: lo=0.05, hi=0.45, t=0.8; v2_sonnet46: lo=flag, hi=flag, t=0.75 | $0.0235 | 75.0% | 22.8% | 50.0% |
| (e) Sonnet -> Opus | v2_haiku45: t1=0.8, t=0.05; v2_sonnet46: t1=0.75, t=0.65 | $0.0522 | 66.1% | 21.2% | 48.7% |

![cost/recall frontier](figures/cascade_frontier_corrected_precal.svg)

Notes: thresholds are `confidence >= t` (`flag` = the auditor's own `hack_detected`). Cascades pay for every stage they run. Costs exclude the subject agent and the judge, and the heuristic costs nothing. Opus re-audits exist only for these two experiments, so this is a two-subject-model, six-task sample: frontier thresholds are tuned on it (see the held-out checks).

# Auditor deployment policies: cost vs detection

Experiments: v2_haiku45, v2_sonnet46. 240 trajectories (56 hacked under the `corrected` label), all audited in `full_trace` by Sonnet 4.6 and Opus 4.6; the heuristic auditor is run live offline. Cost is USD per trajectory from `eval/cost.py` (estimates: chars/4 of the rebuilt audit request; no recorded usage).

## Default operating points

Each auditor's own `hack_detected`. Cascade (d) escalates when the heuristic flags or its confidence is in [0.25, 0.75]. AUROC uses the score of the last stage that ran. Brackets: 95% bootstrap CIs over trajectories.

| policy | recall | FPR | precision | AUROC | USD / trajectory | escalated | TP/FP/FN/TN |
|---|---|---|---|---|---|---|---|
| (a) heuristic only | 67.9% [55.6%, 80.4%] | 8.2% [4.3%, 12.4%] | 71.7% [59.5%, 84.0%] | 0.717 [0.613, 0.818] | $0.0000 [$0.0000, $0.0000] | 0.0% | 38/15/18/169 |
| (b) Sonnet only | 83.9% [73.2%, 93.3%] | 34.2% [27.6%, 41.1%] | 42.7% [33.6%, 52.1%] | 0.865 [0.817, 0.912] | $0.0308 [$0.0299, $0.0318] | 0.0% | 47/63/9/121 |
| (c) Opus only | 76.8% [66.0%, 87.3%] | 22.3% [16.3%, 27.9%] | 51.2% [41.0%, 61.4%] | 0.861 [0.814, 0.906] | $0.0514 [$0.0498, $0.0530] | 0.0% | 43/41/13/143 |
| (d) heuristic -> Sonnet | 69.6% [57.8%, 81.5%] | 33.7% [27.2%, 40.6%] | 38.6% [29.3%, 48.3%] | 0.684 [0.581, 0.779] | $0.0186 [$0.0164, $0.0205] | 55.8% | 39/62/17/122 |
| (e) Sonnet -> Opus | 75.0% [63.8%, 86.5%] | 22.3% [16.3%, 27.9%] | 50.6% [39.7%, 60.9%] | 0.861 [0.816, 0.906] | $0.0572 [$0.0529, $0.0616] | 45.8% | 42/41/14/143 |

(e) is cheaper than (c) only while Sonnet flags fewer than 40% of trajectories (1 - Sonnet cost / Opus cost); here it flags 45.8%, at a 23.3% hack rate. A lower hack rate in deployment means fewer escalations.

## By subject model (default operating points)

| subject model | policy | n | recall | FPR | precision | USD / trajectory |
|---|---|---|---|---|---|---|
| claude-haiku-4-5-20251001 | (a) heuristic only | 120 (28 hacked) | 46.4% | 1.1% | 92.9% | $0.0000 |
| claude-haiku-4-5-20251001 | (b) Sonnet only | 120 (28 hacked) | 82.1% | 31.5% | 44.2% | $0.0316 |
| claude-haiku-4-5-20251001 | (c) Opus only | 120 (28 hacked) | 75.0% | 21.7% | 51.2% | $0.0523 |
| claude-haiku-4-5-20251001 | (d) heuristic -> Sonnet | 120 (28 hacked) | 53.6% | 31.5% | 34.1% | $0.0174 |
| claude-haiku-4-5-20251001 | (e) Sonnet -> Opus | 120 (28 hacked) | 75.0% | 21.7% | 51.2% | $0.0578 |
| claude-sonnet-4-6 | (a) heuristic only | 120 (28 hacked) | 89.3% | 15.2% | 64.1% | $0.0000 |
| claude-sonnet-4-6 | (b) Sonnet only | 120 (28 hacked) | 85.7% | 37.0% | 41.4% | $0.0300 |
| claude-sonnet-4-6 | (c) Opus only | 120 (28 hacked) | 78.6% | 22.8% | 51.2% | $0.0505 |
| claude-sonnet-4-6 | (d) heuristic -> Sonnet | 120 (28 hacked) | 85.7% | 35.9% | 42.1% | $0.0198 |
| claude-sonnet-4-6 | (e) Sonnet -> Opus | 120 (28 hacked) | 75.0% | 22.8% | 50.0% | $0.0565 |

## Cost/recall frontier at FPR <= 5%

Cheapest operating point for each recall level over 1800 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|
| (a) heuristic only | t=0.9 | $0.0000 | 33.9% | 4.9% | 67.9% | 0.0% |
| (d) heuristic -> Sonnet | lo=flag, hi=flag, t=0.4 | $0.0082 | 64.3% | 4.9% | 80.0% | 22.1% |
| (d) heuristic -> Sonnet | lo=0.15, hi=0.2, t=0.4 | $0.0084 | 66.1% | 4.9% | 80.4% | 22.5% |
| (d) heuristic -> Sonnet | lo=0, hi=0.05, t=0.4 | $0.0126 | 76.8% | 4.9% | 82.7% | 37.1% |
| (d) heuristic -> Sonnet | lo=0, hi=0.2, t=0.4 | $0.0188 | 78.6% | 4.9% | 83.0% | 60.8% |

Best recall per policy at FPR <= 5%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | t=0.9 | $0.0000 | 33.9% | 4.9% | 67.9% |
| (d) heuristic -> Sonnet | lo=0, hi=0.2, t=0.4 | $0.0188 | 78.6% | 4.9% | 83.0% |

Held-out check at FPR <= 5%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v2_haiku45: t=0.95; v2_sonnet46: t=flag | $0.0000 | 55.4% | 7.6% | 68.9% |
| (b) Sonnet only | v2_haiku45: t=0.95; v2_sonnet46: t=0.95 | $0.0308 | 57.1% | 14.1% | 55.2% |
| (c) Opus only | v2_haiku45: t=0.9; v2_sonnet46: t=0.95 | $0.0514 | 46.4% | 14.7% | 49.1% |
| (d) heuristic -> Sonnet | v2_haiku45: lo=flag, hi=flag, t=flag; v2_sonnet46: lo=0, hi=0.2, t=0.4 | $0.0125 | 64.3% | 5.4% | 78.3% |
| (e) Sonnet -> Opus | v2_haiku45: t1=flag, t=0.9; v2_sonnet46: t1=0.95, t=0.95 | $0.0511 | 46.4% | 14.7% | 49.1% |

## Cost/recall frontier at FPR <= 10%

Cheapest operating point for each recall level over 1800 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|
| (a) heuristic only | t=flag | $0.0000 | 67.9% | 8.2% | 71.7% | 0.0% |
| (d) heuristic -> Sonnet | lo=0.15, hi=0.2, t=0.05 | $0.0084 | 69.6% | 6.5% | 76.5% | 22.5% |
| (d) heuristic -> Sonnet | lo=0, hi=0.05, t=0.1 | $0.0126 | 78.6% | 5.4% | 81.5% | 37.1% |
| (d) heuristic -> Sonnet | lo=0, hi=0.2, t=0.1 | $0.0188 | 80.4% | 5.4% | 81.8% | 60.8% |

Best recall per policy at FPR <= 10%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | t=flag | $0.0000 | 67.9% | 8.2% | 71.7% |
| (d) heuristic -> Sonnet | lo=0, hi=0.2, t=0.1 | $0.0188 | 80.4% | 5.4% | 81.8% |

Held-out check at FPR <= 10%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v2_haiku45: t=0.9; v2_sonnet46: t=flag | $0.0000 | 60.7% | 7.6% | 70.8% |
| (b) Sonnet only | v2_haiku45: t=0.95; v2_sonnet46: t=0.95 | $0.0308 | 57.1% | 14.1% | 55.2% |
| (c) Opus only | v2_haiku45: t=0.9; v2_sonnet46: t=0.95 | $0.0514 | 46.4% | 14.7% | 49.1% |
| (d) heuristic -> Sonnet | v2_haiku45: lo=0, hi=0.05, t=0.1; v2_sonnet46: lo=0, hi=0.2, t=0.4 | $0.0161 | 76.8% | 5.4% | 81.1% |
| (e) Sonnet -> Opus | v2_haiku45: t1=flag, t=0.9; v2_sonnet46: t1=0.95, t=flag | $0.0511 | 48.2% | 15.2% | 49.1% |

## Cost/recall frontier at FPR <= 25%

Cheapest operating point for each recall level over 1800 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|
| (a) heuristic only | t=0.4 | $0.0000 | 69.6% | 25.0% | 45.9% | 0.0% |
| (d) heuristic -> Sonnet | lo=0.35, hi=0.4, t=0.05 | $0.0099 | 71.4% | 12.5% | 63.5% | 27.5% |
| (d) heuristic -> Sonnet | lo=0.35, hi=0.45, t=0.05 | $0.0120 | 73.2% | 20.7% | 51.9% | 34.2% |
| (d) heuristic -> Sonnet | lo=0, hi=0.05, t=0.05 | $0.0126 | 91.1% | 14.1% | 66.2% | 37.1% |
| (d) heuristic -> Sonnet | lo=0, hi=0.15, t=0.05 | $0.0186 | 92.9% | 22.8% | 55.3% | 60.4% |
| (d) heuristic -> Sonnet | lo=0, hi=0.2, t=0.05 | $0.0188 | 94.6% | 22.8% | 55.8% | 60.8% |

Best recall per policy at FPR <= 25%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | t=0.4 | $0.0000 | 69.6% | 25.0% | 45.9% |
| (b) Sonnet only | t=0.75 | $0.0308 | 78.6% | 24.5% | 49.4% |
| (c) Opus only | t=0.15 | $0.0514 | 80.4% | 24.5% | 50.0% |
| (d) heuristic -> Sonnet | lo=0, hi=0.2, t=0.05 | $0.0188 | 94.6% | 22.8% | 55.8% |
| (e) Sonnet -> Opus | t1=0.05, t=0.15 | $0.0697 | 80.4% | 24.5% | 50.0% |

Held-out check at FPR <= 25%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v2_haiku45: t=flag; v2_sonnet46: t=0.35 | $0.0000 | 69.6% | 20.7% | 50.6% |
| (b) Sonnet only | v2_haiku45: t=0.8; v2_sonnet46: t=0.75 | $0.0308 | 76.8% | 22.8% | 50.6% |
| (c) Opus only | v2_haiku45: t=0.4; v2_sonnet46: t=0.65 | $0.0514 | 67.9% | 20.1% | 50.7% |
| (d) heuristic -> Sonnet | v2_haiku45: lo=0, hi=0.05, t=0.05; v2_sonnet46: lo=0, hi=0.2, t=0.05 | $0.0161 | 91.1% | 17.9% | 60.7% |
| (e) Sonnet -> Opus | v2_haiku45: t1=0.8, t=0.05; v2_sonnet46: t1=0.75, t=0.65 | $0.0522 | 66.1% | 21.2% | 48.7% |

![cost/recall frontier](figures/cascade_frontier_corrected.svg)

Notes: thresholds are `confidence >= t` (`flag` = the auditor's own `hack_detected`). Cascades pay for every stage they run. Costs exclude the subject agent and the judge, and the heuristic costs nothing. Opus re-audits exist only for these two experiments, so this is a two-subject-model, six-task sample: frontier thresholds are tuned on it (see the held-out checks).

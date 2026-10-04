# Auditor deployment policies: cost vs detection

Experiments: v3_haiku45, v3_opus46, v3_sonnet46, v3cond_haiku45, v3cond_sonnet46, v3fault_sonnet46. 450 trajectories (102 hacked under the `labeller` label), all audited in `full_trace` by Sonnet 4.6; the heuristic auditor is run live offline. Cost is USD per trajectory from `eval/cost.py` (estimates: chars/4 of the rebuilt audit request; no recorded usage).

## Default operating points

Each auditor's own `hack_detected`. Cascade (d) escalates when the heuristic flags or its confidence is in [0.25, 0.75]. AUROC uses the score of the last stage that ran. Brackets: 95% bootstrap CIs over trajectories.

| policy | recall | FPR | precision | AUROC | USD / trajectory | escalated | TP/FP/FN/TN |
|---|---|---|---|---|---|---|---|
| (a) heuristic only | 61.8% [51.9%, 71.4%] | 3.2% [1.4%, 5.1%] | 85.1% [76.9%, 93.3%] | 0.848 [0.793, 0.898] | $0.0000 [$0.0000, $0.0000] | 0.0% | 63/11/39/337 |
| (b) Sonnet only | 86.3% [78.8%, 92.5%] | 17.2% [13.2%, 21.1%] | 59.5% [51.9%, 67.1%] | 0.930 [0.896, 0.958] | $0.0312 [$0.0304, $0.0321] | 0.0% | 88/60/14/288 |
| (d) heuristic -> Sonnet | 78.4% [70.3%, 86.6%] | 15.5% [11.7%, 19.3%] | 59.7% [51.5%, 68.1%] | 0.850 [0.791, 0.901] | $0.0184 [$0.0167, $0.0200] | 52.2% | 80/54/22/294 |

## By subject model (default operating points)

| subject model | policy | n | recall | FPR | precision | USD / trajectory |
|---|---|---|---|---|---|---|
| claude-haiku-4-5-20251001 | (a) heuristic only | 228 (52 hacked) | 51.9% | 4.0% | 79.4% | $0.0000 |
| claude-haiku-4-5-20251001 | (b) Sonnet only | 228 (52 hacked) | 86.5% | 19.3% | 57.0% | $0.0319 |
| claude-haiku-4-5-20251001 | (d) heuristic -> Sonnet | 228 (52 hacked) | 75.0% | 17.6% | 55.7% | $0.0181 |
| claude-opus-4-6 | (a) heuristic only | 27 (0 hacked) | n/a | 0.0% | n/a | $0.0000 |
| claude-opus-4-6 | (b) Sonnet only | 27 (0 hacked) | n/a | 3.7% | 0.0% | $0.0254 |
| claude-opus-4-6 | (d) heuristic -> Sonnet | 27 (0 hacked) | n/a | 0.0% | n/a | $0.0106 |
| claude-sonnet-4-6 | (a) heuristic only | 195 (50 hacked) | 72.0% | 2.8% | 90.0% | $0.0000 |
| claude-sonnet-4-6 | (b) Sonnet only | 195 (50 hacked) | 86.0% | 17.2% | 63.2% | $0.0312 |
| claude-sonnet-4-6 | (d) heuristic -> Sonnet | 195 (50 hacked) | 82.0% | 15.9% | 64.1% | $0.0198 |

## Cost/recall frontier at FPR <= 5%

Cheapest operating point for each recall level over 1380 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|
| (a) heuristic only | t=0.75 | $0.0000 | 61.8% | 2.3% | 88.7% | 0.0% |
| (d) heuristic -> Sonnet | lo=0.45, hi=0.5, t=0.75 | $0.0102 | 67.6% | 3.2% | 86.2% | 26.7% |
| (d) heuristic -> Sonnet | lo=0.25, hi=0.5, t=0.85 | $0.0184 | 68.6% | 4.3% | 82.4% | 52.2% |
| (d) heuristic -> Sonnet | lo=0.2, hi=0.5, t=0.85 | $0.0208 | 70.6% | 4.6% | 81.8% | 61.1% |
| (d) heuristic -> Sonnet | lo=0.05, hi=0.4, t=0.75 | $0.0212 | 71.6% | 4.3% | 83.0% | 67.1% |
| (d) heuristic -> Sonnet | lo=0, hi=0.4, t=0.75 | $0.0259 | 72.5% | 4.3% | 83.1% | 85.1% |
| (d) heuristic -> Sonnet | lo=0.05, hi=0.5, t=0.85 | $0.0265 | 74.5% | 4.6% | 82.6% | 82.0% |

Best recall per policy at FPR <= 5%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | t=0.75 | $0.0000 | 61.8% | 2.3% | 88.7% |
| (b) Sonnet only | t=0.85 | $0.0312 | 74.5% | 4.6% | 82.6% |
| (d) heuristic -> Sonnet | lo=0.05, hi=0.5, t=0.85 | $0.0265 | 74.5% | 4.6% | 82.6% |

Held-out check at FPR <= 5%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v3_haiku45: t=flag; v3_opus46: t=0.75; v3_sonnet46: t=0.75; v3cond_haiku45: t=0.75; v3cond_sonnet46: t=0.75; v3fault_sonnet46: t=0.75 | $0.0000 | 61.8% | 3.2% | 85.1% |
| (b) Sonnet only | v3_haiku45: t=0.85; v3_opus46: t=0.85; v3_sonnet46: t=0.85; v3cond_haiku45: t=0.85; v3cond_sonnet46: t=0.85; v3fault_sonnet46: t=0.85 | $0.0312 | 74.5% | 4.6% | 82.6% |
| (d) heuristic -> Sonnet | v3_haiku45: lo=0.45, hi=0.5, t=0.75; v3_opus46: lo=0.05, hi=0.5, t=0.85; v3_sonnet46: lo=0.05, hi=0.5, t=0.85; v3cond_haiku45: lo=0.05, hi=0.5, t=0.85; v3cond_sonnet46: lo=0, hi=0.4, t=0.75; v3fault_sonnet46: lo=0.05, hi=0.5, t=0.85 | $0.0194 | 56.9% | 4.3% | 79.5% |

## Cost/recall frontier at FPR <= 10%

Cheapest operating point for each recall level over 1380 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|
| (a) heuristic only | t=0.75 | $0.0000 | 61.8% | 2.3% | 88.7% | 0.0% |
| (d) heuristic -> Sonnet | lo=0.45, hi=0.5, t=0.75 | $0.0102 | 67.6% | 3.2% | 86.2% | 26.7% |
| (d) heuristic -> Sonnet | lo=0.35, hi=0.5, t=0.75 | $0.0139 | 70.6% | 5.5% | 79.1% | 38.2% |
| (d) heuristic -> Sonnet | lo=0.3, hi=0.5, t=0.75 | $0.0179 | 76.5% | 6.9% | 76.5% | 50.7% |
| (d) heuristic -> Sonnet | lo=0.25, hi=0.5, t=0.75 | $0.0184 | 78.4% | 6.9% | 76.9% | 52.2% |
| (d) heuristic -> Sonnet | lo=0.2, hi=0.5, t=0.75 | $0.0208 | 80.4% | 7.5% | 75.9% | 61.1% |
| (d) heuristic -> Sonnet | lo=0.05, hi=0.5, t=0.75 | $0.0265 | 84.3% | 7.8% | 76.1% | 82.0% |
| (b) Sonnet only | t=0.75 | $0.0312 | 85.3% | 7.8% | 76.3% | 0.0% |

Best recall per policy at FPR <= 10%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | t=0.75 | $0.0000 | 61.8% | 2.3% | 88.7% |
| (b) Sonnet only | t=0.75 | $0.0312 | 85.3% | 7.8% | 76.3% |
| (d) heuristic -> Sonnet | lo=0, hi=0.5, t=0.75 | $0.0312 | 85.3% | 7.8% | 76.3% |

Held-out check at FPR <= 10%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v3_haiku45: t=flag; v3_opus46: t=0.75; v3_sonnet46: t=0.75; v3cond_haiku45: t=0.75; v3cond_sonnet46: t=0.75; v3fault_sonnet46: t=0.75 | $0.0000 | 61.8% | 3.2% | 85.1% |
| (b) Sonnet only | v3_haiku45: t=0.75; v3_opus46: t=0.75; v3_sonnet46: t=0.85; v3cond_haiku45: t=0.75; v3cond_sonnet46: t=0.75; v3fault_sonnet46: t=0.75 | $0.0312 | 74.5% | 6.6% | 76.8% |
| (d) heuristic -> Sonnet | v3_haiku45: lo=0, hi=0.5, t=0.75; v3_opus46: lo=0, hi=0.5, t=0.75; v3_sonnet46: lo=0.05, hi=0.5, t=0.85; v3cond_haiku45: lo=0, hi=0.5, t=0.75; v3cond_sonnet46: lo=0, hi=0.5, t=0.75; v3fault_sonnet46: lo=0, hi=0.5, t=0.75 | $0.0303 | 74.5% | 6.6% | 76.8% |

## Cost/recall frontier at FPR <= 25%

Cheapest operating point for each recall level over 1380 swept threshold combinations on a 0.05 grid (tuned in-sample, so optimistic).

| policy | thresholds | USD / trajectory | recall | FPR | precision | escalated |
|---|---|---|---|---|---|---|
| (a) heuristic only | t=0.45 | $0.0000 | 74.5% | 12.6% | 63.3% | 0.0% |
| (d) heuristic -> Sonnet | lo=0.3, hi=0.5, t=0.75 | $0.0179 | 76.5% | 6.9% | 76.5% | 50.7% |
| (d) heuristic -> Sonnet | lo=0.25, hi=0.5, t=0.75 | $0.0184 | 78.4% | 6.9% | 76.9% | 52.2% |
| (d) heuristic -> Sonnet | lo=0.2, hi=0.5, t=0.75 | $0.0208 | 80.4% | 7.5% | 75.9% | 61.1% |
| (d) heuristic -> Sonnet | lo=0.05, hi=0.5, t=0.75 | $0.0265 | 84.3% | 7.8% | 76.1% | 82.0% |
| (b) Sonnet only | t=0.1 | $0.0312 | 88.2% | 17.2% | 60.0% | 0.0% |

Best recall per policy at FPR <= 25%:

| policy | thresholds | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | t=0.45 | $0.0000 | 74.5% | 12.6% | 63.3% |
| (b) Sonnet only | t=0.1 | $0.0312 | 88.2% | 17.2% | 60.0% |
| (d) heuristic -> Sonnet | lo=0, hi=0.5, t=0.1 | $0.0312 | 88.2% | 17.2% | 60.0% |

Held-out check at FPR <= 25%: thresholds tuned on the other experiment(s), scored on the held-out one, pooled (leave one experiment out). The FPR cap is only enforced in training.

| policy | tuned thresholds (held-out exp: thresholds) | USD / trajectory | recall | FPR | precision |
|---|---|---|---|---|---|
| (a) heuristic only | v3_haiku45: t=0.45; v3_opus46: t=0.45; v3_sonnet46: t=0.35; v3cond_haiku45: t=0.45; v3cond_sonnet46: t=0.45; v3fault_sonnet46: t=0.45 | $0.0000 | 74.5% | 18.7% | 53.9% |
| (b) Sonnet only | v3_haiku45: t=0.75; v3_opus46: t=0.1; v3_sonnet46: t=0.1; v3cond_haiku45: t=0.1; v3cond_sonnet46: t=0.1; v3fault_sonnet46: t=0.1 | $0.0312 | 85.3% | 12.6% | 66.4% |
| (d) heuristic -> Sonnet | v3_haiku45: lo=0.35, hi=0.5, t=0.05; v3_opus46: lo=0, hi=0.5, t=0.1; v3_sonnet46: lo=0, hi=0.5, t=0.1; v3cond_haiku45: lo=0, hi=0.5, t=0.1; v3cond_sonnet46: lo=0, hi=0.5, t=0.1; v3fault_sonnet46: lo=0, hi=0.5, t=0.1 | $0.0226 | 73.5% | 17.8% | 54.7% |

Notes: thresholds are `confidence >= t` (`flag` = the auditor's own `hack_detected`). Cascades pay for every stage they run. Costs exclude the subject agent and the judge, and the heuristic costs nothing. Opus policies are omitted (no Opus re-audit for these experiments). Frontier thresholds are tuned on this sample (see the held-out checks).

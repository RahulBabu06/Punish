# Rubric v3: PROXY before/after (post-hoc filter on saved verdicts; NOT a measured re-audit)

Cells are recall / FPR. `before` = saved default-rubric verdicts; `v3 proxy` = flags cleared by the
filter in `eval/rubric_v3.py`; `types only` = every suspicious_access/rationalization-only trace flag cleared
(bound). final_report is unchanged by construction. Measure for real with docs/rubric_v3.md.

## v2 (corrected label; v2_sonnet46, v2_haiku45, v2_sonnet45)

v3 proxy clears 259 trace-mode flags: 259 false positives, 0 true positives.

### all

| auditor | mode | before | v3 proxy | types only |
|---|---|---|---|---|
| claude-opus-4-6 | final_report | 35/56 = 0.62 / 36/184 = 0.20 | 35/56 = 0.62 / 36/184 = 0.20 | 35/56 = 0.62 / 36/184 = 0.20 |
| claude-opus-4-6 | full_trace | 43/56 = 0.77 / 41/184 = 0.22 | 43/56 = 0.77 / 3/184 = 0.02 | 43/56 = 0.77 / 1/184 = 0.01 |
| claude-opus-4-6 | report_only | 35/56 = 0.62 / 50/184 = 0.27 | 35/56 = 0.62 / 3/184 = 0.02 | 35/56 = 0.62 / 1/184 = 0.01 |
| claude-sonnet-4-6 | final_report | 69/93 = 0.74 / 62/267 = 0.23 | 69/93 = 0.74 / 62/267 = 0.23 | 69/93 = 0.74 / 62/267 = 0.23 |
| claude-sonnet-4-6 | full_trace | 84/93 = 0.90 / 92/267 = 0.34 | 84/93 = 0.90 / 7/267 = 0.03 | 84/93 = 0.90 / 5/267 = 0.02 |
| claude-sonnet-4-6 | report_only | 85/93 = 0.91 / 94/267 = 0.35 | 85/93 = 0.91 / 5/267 = 0.02 | 85/93 = 0.91 / 4/267 = 0.01 |

### metric_gaming

| auditor | mode | before | v3 proxy | types only |
|---|---|---|---|---|
| claude-opus-4-6 | final_report | 4/10 = 0.40 / 0/30 = 0.00 | 4/10 = 0.40 / 0/30 = 0.00 | 4/10 = 0.40 / 0/30 = 0.00 |
| claude-opus-4-6 | full_trace | 10/10 = 1.00 / 7/30 = 0.23 | 10/10 = 1.00 / 0/30 = 0.00 | 10/10 = 1.00 / 0/30 = 0.00 |
| claude-opus-4-6 | report_only | 10/10 = 1.00 / 16/30 = 0.53 | 10/10 = 1.00 / 0/30 = 0.00 | 10/10 = 1.00 / 0/30 = 0.00 |
| claude-sonnet-4-6 | final_report | 3/15 = 0.20 / 0/45 = 0.00 | 3/15 = 0.20 / 0/45 = 0.00 | 3/15 = 0.20 / 0/45 = 0.00 |
| claude-sonnet-4-6 | full_trace | 15/15 = 1.00 / 39/45 = 0.87 | 15/15 = 1.00 / 0/45 = 0.00 | 15/15 = 1.00 / 0/45 = 0.00 |
| claude-sonnet-4-6 | report_only | 15/15 = 1.00 / 43/45 = 0.96 | 15/15 = 1.00 / 0/45 = 0.00 | 15/15 = 1.00 / 0/45 = 0.00 |

### leaked_answer

| auditor | mode | before | v3 proxy | types only |
|---|---|---|---|---|
| claude-opus-4-6 | final_report | – / 11/40 = 0.28 | – / 11/40 = 0.28 | – / 11/40 = 0.28 |
| claude-opus-4-6 | full_trace | – / 33/40 = 0.82 | – / 2/40 = 0.05 | – / 0/40 = 0.00 |
| claude-opus-4-6 | report_only | – / 33/40 = 0.82 | – / 2/40 = 0.05 | – / 0/40 = 0.00 |
| claude-sonnet-4-6 | final_report | 0/2 = 0.00 / 19/58 = 0.33 | 0/2 = 0.00 / 19/58 = 0.33 | 0/2 = 0.00 / 19/58 = 0.33 |
| claude-sonnet-4-6 | full_trace | 2/2 = 1.00 / 50/58 = 0.86 | 2/2 = 1.00 / 4/58 = 0.07 | 2/2 = 1.00 / 2/58 = 0.03 |
| claude-sonnet-4-6 | report_only | 2/2 = 1.00 / 50/58 = 0.86 | 2/2 = 1.00 / 4/58 = 0.07 | 2/2 = 1.00 / 3/58 = 0.05 |

## v3 (labeller label; v3_sonnet46, v3_haiku45, v3_opus46)

v3 proxy clears 69 trace-mode flags: 69 false positives, 0 true positives.

### all

| auditor | mode | before | v3 proxy | types only |
|---|---|---|---|---|
| claude-sonnet-4-6 | final_report | 72/95 = 0.76 / 42/282 = 0.15 | 72/95 = 0.76 / 42/282 = 0.15 | 72/95 = 0.76 / 42/282 = 0.15 |
| claude-sonnet-4-6 | full_trace | 82/95 = 0.86 / 56/282 = 0.20 | 82/95 = 0.86 / 22/282 = 0.08 | 78/95 = 0.82 / 11/282 = 0.04 |
| claude-sonnet-4-6 | report_only | 85/95 = 0.89 / 58/282 = 0.21 | 85/95 = 0.89 / 23/282 = 0.08 | 80/95 = 0.84 / 11/282 = 0.04 |

### metric_gaming

| auditor | mode | before | v3 proxy | types only |
|---|---|---|---|---|
| claude-sonnet-4-6 | final_report | 4/11 = 0.36 / 0/29 = 0.00 | 4/11 = 0.36 / 0/29 = 0.00 | 4/11 = 0.36 / 0/29 = 0.00 |
| claude-sonnet-4-6 | full_trace | 11/11 = 1.00 / 27/29 = 0.93 | 11/11 = 1.00 / 0/29 = 0.00 | 10/11 = 0.91 / 0/29 = 0.00 |
| claude-sonnet-4-6 | report_only | 11/11 = 1.00 / 28/29 = 0.97 | 11/11 = 1.00 / 0/29 = 0.00 | 10/11 = 0.91 / 0/29 = 0.00 |

### leaked_answer

| auditor | mode | before | v3 proxy | types only |
|---|---|---|---|---|
| claude-sonnet-4-6 | final_report | 12/12 = 1.00 / 6/25 = 0.24 | 12/12 = 1.00 / 6/25 = 0.24 | 12/12 = 1.00 / 6/25 = 0.24 |
| claude-sonnet-4-6 | full_trace | 12/12 = 1.00 / 15/25 = 0.60 | 12/12 = 1.00 / 8/25 = 0.32 | 11/12 = 0.92 / 5/25 = 0.20 |
| claude-sonnet-4-6 | report_only | 12/12 = 1.00 / 15/25 = 0.60 | 12/12 = 1.00 / 8/25 = 0.32 | 11/12 = 0.92 / 5/25 = 0.20 |


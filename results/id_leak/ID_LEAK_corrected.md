# Verdicts citing the trajectory id / config name (label `corrected`)

Experiments: v2_sonnet46, v2_haiku45, v2_sonnet45. 1800 audits, 122 cite the id or a config name.

## Pooled over modes

| auditor | mode | cites id/config | audits | recall | FPR |
|---|---|---|---|---|---|
| claude-opus-4-6 | all | yes | 47 | 3/5 = 0.60 | 11/42 = 0.26 |
| claude-opus-4-6 | all | no | 673 | 110/163 = 0.67 | 116/510 = 0.23 |
| claude-sonnet-4-6 | all | yes | 75 | 24/28 = 0.86 | 18/47 = 0.38 |
| claude-sonnet-4-6 | all | no | 1005 | 214/251 = 0.85 | 230/754 = 0.31 |

## By mode

| auditor | mode | cites id/config | audits | recall | FPR |
|---|---|---|---|---|---|
| claude-opus-4-6 | final_report | yes | 46 | 3/5 = 0.60 | 11/41 = 0.27 |
| claude-opus-4-6 | final_report | no | 194 | 32/51 = 0.63 | 25/143 = 0.17 |
| claude-opus-4-6 | full_trace | yes | 0 | n/a | n/a |
| claude-opus-4-6 | full_trace | no | 240 | 43/56 = 0.77 | 41/184 = 0.22 |
| claude-opus-4-6 | report_only | yes | 1 | n/a | 0/1 = 0.00 |
| claude-opus-4-6 | report_only | no | 239 | 35/56 = 0.62 | 50/183 = 0.27 |
| claude-sonnet-4-6 | final_report | yes | 65 | 15/19 = 0.79 | 18/46 = 0.39 |
| claude-sonnet-4-6 | final_report | no | 295 | 54/74 = 0.73 | 44/221 = 0.20 |
| claude-sonnet-4-6 | full_trace | yes | 4 | 3/3 = 1.00 | 0/1 = 0.00 |
| claude-sonnet-4-6 | full_trace | no | 356 | 81/90 = 0.90 | 92/266 = 0.35 |
| claude-sonnet-4-6 | report_only | yes | 6 | 6/6 = 1.00 | n/a |
| claude-sonnet-4-6 | report_only | no | 354 | 79/87 = 0.91 | 94/267 = 0.35 |

## covert config only (hack prompted; isolates the citation from the config mix)

| auditor | mode | cites id/config | audits | recall | FPR |
|---|---|---|---|---|---|
| claude-opus-4-6 | all | yes | 14 | 2/4 = 0.50 | 4/10 = 0.40 |
| claude-opus-4-6 | all | no | 166 | 90/113 = 0.80 | 25/53 = 0.47 |
| claude-sonnet-4-6 | all | yes | 27 | 10/14 = 0.71 | 7/13 = 0.54 |
| claude-sonnet-4-6 | all | no | 243 | 163/184 = 0.89 | 34/59 = 0.58 |


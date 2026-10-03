# API usage and cost

Results dirs: `results/model_probe`, `results/probe_v1`, `results/v2_haiku45`, `results/v2_sonnet45`, `results/v2_sonnet46`, `results/v3_haiku45`, `results/v3_opus46`, `results/v3_sonnet46`, `results/v3cond_haiku45`, `results/v3cond_sonnet46`, `results/v3fault_sonnet46`

| results dir | role | model | calls | input | output | cache write | cache read | USD | source |
|---|---|---|---|---|---|---|---|---|---|
| `results/model_probe` | agent | claude-haiku-4-5 | 6 | 15,992 | 3,619 | 0 | 0 | $0.03 | estimate |
| `results/model_probe` | agent | claude-opus-4-6 | 5 | 9,993 | 1,449 | 0 | 0 | $0.09 | estimate |
| `results/model_probe` | agent | claude-sonnet-4-5 | 5 | 10,763 | 2,082 | 0 | 0 | $0.06 | estimate |
| `results/model_probe` | agent | claude-sonnet-4-6 | 10 | 34,157 | 4,051 | 0 | 0 | $0.16 | estimate |
| `results/probe_v1` | agent | claude-sonnet-4-6 | 179 | 357,365 | 57,216 | 0 | 0 | $1.93 | estimate |
| `results/probe_v1` | auditor | claude-sonnet-4-6 | 108 | 550,677 | 35,231 | 0 | 0 | $2.18 | estimate |
| `results/probe_v1` | judge | claude-opus-4-6 | 36 | 178,715 | 7,401 | 0 | 0 | $1.08 | estimate |
| `results/v2_haiku45` | agent | claude-haiku-4-5 | 703 | 2,101,036 | 346,528 | 0 | 0 | $3.83 | estimate |
| `results/v2_haiku45` | auditor | claude-sonnet-4-6 | 360 | 2,114,209 | 117,471 | 0 | 0 | $8.10 | estimate |
| `results/v2_haiku45` | judge | claude-opus-4-6 | 120 | 817,400 | 23,168 | 0 | 0 | $4.67 | estimate |
| `results/v2_haiku45` | reaudit | claude-opus-4-6 | 360 | 2,114,209 | 115,265 | 0 | 0 | $13.45 | estimate |
| `results/v2_sonnet45` | agent | claude-sonnet-4-5 | 696 | 2,018,230 | 330,025 | 0 | 0 | $11.01 | estimate |
| `results/v2_sonnet45` | auditor | claude-sonnet-4-6 | 360 | 2,030,616 | 122,636 | 0 | 0 | $7.93 | estimate |
| `results/v2_sonnet45` | judge | claude-opus-4-6 | 120 | 779,139 | 24,929 | 0 | 0 | $4.52 | estimate |
| `results/v2_sonnet46` | agent | claude-sonnet-4-6 | 620 | 1,501,707 | 294,611 | 0 | 0 | $8.92 | estimate |
| `results/v2_sonnet46` | auditor | claude-sonnet-4-6 | 360 | 2,075,159 | 116,652 | 0 | 0 | $7.98 | estimate |
| `results/v2_sonnet46` | judge | claude-opus-4-6 | 120 | 743,901 | 24,398 | 0 | 0 | $4.33 | estimate |
| `results/v2_sonnet46` | reaudit | claude-opus-4-6 | 360 | 2,075,159 | 122,613 | 0 | 0 | $13.44 | estimate |
| `results/v3_haiku45` | agent | claude-haiku-4-5 | 1272 | 4,061,633 | 633,684 | 0 | 0 | $7.23 | estimate |
| `results/v3_haiku45` | auditor | claude-sonnet-4-6 | 600 | 3,618,707 | 182,225 | 0 | 0 | $13.59 | estimate |
| `results/v3_opus46` | agent | claude-opus-4-6 | 147 | 345,203 | 51,909 | 0 | 0 | $3.02 | estimate |
| `results/v3_opus46` | auditor | claude-sonnet-4-6 | 81 | 420,052 | 19,118 | 0 | 0 | $1.55 | estimate |
| `results/v3_sonnet46` | agent | claude-sonnet-4-6 | 824 | 2,222,853 | 402,929 | 0 | 0 | $12.71 | estimate |
| `results/v3_sonnet46` | auditor | claude-sonnet-4-6 | 450 | 2,661,727 | 145,894 | 0 | 0 | $10.17 | estimate |
| `results/v3cond_haiku45` | agent | claude-haiku-4-5 | 158 | 468,969 | 85,474 | 0 | 0 | $0.90 | estimate |
| `results/v3cond_haiku45` | auditor | claude-sonnet-4-6 | 84 | 498,946 | 20,009 | 0 | 0 | $1.80 | estimate |
| `results/v3cond_sonnet46` | agent | claude-sonnet-4-6 | 137 | 340,980 | 69,508 | 0 | 0 | $2.07 | estimate |
| `results/v3cond_sonnet46` | auditor | claude-sonnet-4-6 | 81 | 490,555 | 21,982 | 0 | 0 | $1.80 | estimate |
| `results/v3fault_sonnet46` | agent | claude-sonnet-4-6 | 103 | 284,388 | 56,951 | 0 | 0 | $1.71 | estimate |
| `results/v3fault_sonnet46` | auditor | claude-sonnet-4-6 | 54 | 361,122 | 12,757 | 0 | 0 | $1.27 | estimate |

| role | calls | USD | of which estimated |
|---|---|---|---|
| agent | 4,865 | $53.68 | $53.68 |
| auditor | 2,538 | $56.37 | $56.37 |
| judge | 396 | $14.59 | $14.59 |
| reaudit | 720 | $26.89 | $26.89 |
| **total** | 8,519 | **$151.54** | $151.54 |

Prices: USD per million tokens from `eval/cost.py` `PRICES_PER_MTOK` (https://platform.claude.com/docs/en/about-claude/pricing). `source=estimate` rows have no recorded `usage`: tokens ≈ characters / 4 of the rebuilt request and the logged output, plus the API's hidden tool-use system prompt. Estimates ignore failed/retried API calls and use the logged (possibly summarized or missing) reasoning, so agent output tokens are a lower bound.

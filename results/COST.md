# API usage and cost

Results dirs: `results/model_probe`, `results/probe_v1`, `results/v2_haiku45`, `results/v2_sonnet45`, `results/v2_sonnet46`, `results/v3_haiku45`, `results/v3_opus46`, `results/v3_sonnet46`, `results/v3cond_haiku45`, `results/v3cond_sonnet46`, `results/v3fault_sonnet46`

| results dir | role | model | calls | input | output | cache write | cache read | USD | source |
|---|---|---|---|---|---|---|---|---|---|
| `results/model_probe` | agent | claude-haiku-4-5 | 6 | 15,992 | 3,619 | 0 | 0 | $0.03 | estimate |
| `results/model_probe` | agent | claude-opus-4-6 | 5 | 9,993 | 1,449 | 0 | 0 | $0.09 | estimate |
| `results/model_probe` | agent | claude-sonnet-4-5 | 5 | 10,763 | 2,082 | 0 | 0 | $0.06 | estimate |
| `results/model_probe` | agent | claude-sonnet-4-6 | 10 | 34,157 | 4,051 | 0 | 0 | $0.16 | estimate |
| `results/probe_v1` | agent | claude-sonnet-4-6 | 179 | 357,365 | 57,216 | 0 | 0 | $1.93 | estimate |
| `results/probe_v1` | auditor | claude-sonnet-4-6 | 108 | 644,704 | 35,231 | 0 | 0 | $2.46 | estimate |
| `results/probe_v1` | judge | claude-opus-4-6 | 36 | 198,559 | 7,401 | 0 | 0 | $1.18 | estimate |
| `results/v2_haiku45` | agent | claude-haiku-4-5 | 703 | 2,101,036 | 346,528 | 0 | 0 | $3.83 | estimate |
| `results/v2_haiku45` | auditor | claude-sonnet-4-6 | 360 | 2,408,453 | 117,471 | 0 | 0 | $8.99 | estimate |
| `results/v2_haiku45` | judge | claude-opus-4-6 | 120 | 873,990 | 23,168 | 0 | 0 | $4.95 | estimate |
| `results/v2_haiku45` | reaudit | claude-opus-4-6 | 360 | 2,408,453 | 115,265 | 0 | 0 | $14.92 | estimate |
| `results/v2_sonnet45` | agent | claude-sonnet-4-5 | 696 | 2,018,230 | 330,025 | 0 | 0 | $11.01 | estimate |
| `results/v2_sonnet45` | auditor | claude-sonnet-4-6 | 360 | 2,318,983 | 122,636 | 0 | 0 | $8.80 | estimate |
| `results/v2_sonnet45` | judge | claude-opus-4-6 | 120 | 832,785 | 24,929 | 0 | 0 | $4.79 | estimate |
| `results/v2_sonnet46` | agent | claude-sonnet-4-6 | 620 | 1,501,707 | 294,611 | 0 | 0 | $8.92 | estimate |
| `results/v2_sonnet46` | auditor | claude-sonnet-4-6 | 360 | 2,418,858 | 116,652 | 0 | 0 | $9.01 | estimate |
| `results/v2_sonnet46` | judge | claude-opus-4-6 | 120 | 825,204 | 24,398 | 0 | 0 | $4.74 | estimate |
| `results/v2_sonnet46` | reaudit | claude-opus-4-6 | 360 | 2,418,858 | 122,613 | 0 | 0 | $15.16 | estimate |
| `results/v3_haiku45` | agent | claude-haiku-4-5 | 1272 | 4,061,633 | 633,684 | 0 | 0 | $7.23 | estimate |
| `results/v3_haiku45` | auditor | claude-sonnet-4-6 | 600 | 4,115,490 | 182,225 | 0 | 0 | $15.08 | estimate |
| `results/v3_opus46` | agent | claude-opus-4-6 | 147 | 345,203 | 51,909 | 0 | 0 | $3.02 | estimate |
| `results/v3_opus46` | auditor | claude-sonnet-4-6 | 81 | 491,926 | 19,118 | 0 | 0 | $1.76 | estimate |
| `results/v3_sonnet46` | agent | claude-sonnet-4-6 | 824 | 2,222,853 | 402,929 | 0 | 0 | $12.71 | estimate |
| `results/v3_sonnet46` | auditor | claude-sonnet-4-6 | 450 | 3,093,724 | 145,894 | 0 | 0 | $11.47 | estimate |
| `results/v3cond_haiku45` | agent | claude-haiku-4-5 | 158 | 468,969 | 85,474 | 0 | 0 | $0.90 | estimate |
| `results/v3cond_haiku45` | auditor | claude-sonnet-4-6 | 84 | 566,107 | 20,009 | 0 | 0 | $2.00 | estimate |
| `results/v3cond_sonnet46` | agent | claude-sonnet-4-6 | 137 | 340,980 | 69,508 | 0 | 0 | $2.07 | estimate |
| `results/v3cond_sonnet46` | auditor | claude-sonnet-4-6 | 81 | 567,844 | 21,982 | 0 | 0 | $2.03 | estimate |
| `results/v3fault_sonnet46` | agent | claude-sonnet-4-6 | 103 | 284,388 | 56,951 | 0 | 0 | $1.71 | estimate |
| `results/v3fault_sonnet46` | auditor | claude-sonnet-4-6 | 54 | 421,688 | 12,757 | 0 | 0 | $1.46 | estimate |

| role | calls | USD | of which estimated |
|---|---|---|---|
| agent | 4,865 | $53.68 | $53.68 |
| auditor | 2,538 | $63.05 | $63.05 |
| judge | 396 | $15.65 | $15.65 |
| reaudit | 720 | $30.08 | $30.08 |
| **total** | 8,519 | **$162.46** | $162.46 |

Prices: USD per million tokens from `eval/cost.py` `PRICES_PER_MTOK` (https://platform.claude.com/docs/en/about-claude/pricing). `source=estimate` rows have no recorded `usage`: tokens ≈ characters / 4 of the rebuilt request and the logged output, plus the API's hidden tool-use system prompt. Estimates ignore failed/retried API calls and use the logged (possibly summarized or missing) reasoning, so agent output tokens are a lower bound.

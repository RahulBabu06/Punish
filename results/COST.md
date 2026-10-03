# API usage and cost

Results dirs: `results/v2_sonnet46`, `results/v2_haiku45`, `results/v2_sonnet45`

| results dir | role | model | calls | input | output | cache write | cache read | USD | source |
|---|---|---|---|---|---|---|---|---|---|
| `results/v2_haiku45` | agent | claude-haiku-4-5 | 703 | 2,101,036 | 346,528 | 0 | 0 | $3.83 | estimate |
| `results/v2_haiku45` | auditor | claude-sonnet-4-6 | 360 | 2,365,546 | 117,471 | 0 | 0 | $8.86 | estimate |
| `results/v2_haiku45` | judge | claude-opus-4-6 | 120 | 872,881 | 23,168 | 0 | 0 | $4.94 | estimate |
| `results/v2_haiku45` | reaudit | claude-opus-4-6 | 360 | 2,365,546 | 115,265 | 0 | 0 | $14.71 | estimate |
| `results/v2_sonnet45` | agent | claude-sonnet-4-5 | 696 | 2,018,230 | 330,025 | 0 | 0 | $11.01 | estimate |
| `results/v2_sonnet45` | auditor | claude-sonnet-4-6 | 360 | 2,276,717 | 122,636 | 0 | 0 | $8.67 | estimate |
| `results/v2_sonnet45` | judge | claude-opus-4-6 | 120 | 832,009 | 24,929 | 0 | 0 | $4.78 | estimate |
| `results/v2_sonnet46` | agent | claude-sonnet-4-6 | 620 | 1,501,707 | 294,611 | 0 | 0 | $8.92 | estimate |
| `results/v2_sonnet46` | auditor | claude-sonnet-4-6 | 360 | 2,371,818 | 116,652 | 0 | 0 | $8.87 | estimate |
| `results/v2_sonnet46` | judge | claude-opus-4-6 | 120 | 822,038 | 24,398 | 0 | 0 | $4.72 | estimate |
| `results/v2_sonnet46` | reaudit | claude-opus-4-6 | 360 | 2,371,818 | 122,613 | 0 | 0 | $14.92 | estimate |

| role | calls | USD | of which estimated |
|---|---|---|---|
| agent | 2,019 | $23.76 | $23.76 |
| auditor | 1,080 | $26.39 | $26.39 |
| judge | 360 | $14.45 | $14.45 |
| reaudit | 720 | $29.63 | $29.63 |
| **total** | 4,179 | **$94.24** | $94.24 |

Prices: USD per million tokens from `eval/cost.py` `PRICES_PER_MTOK` (https://platform.claude.com/docs/en/about-claude/pricing). `source=estimate` rows have no recorded `usage`: tokens ≈ characters / 4 of the rebuilt request and the logged output, plus the API's hidden tool-use system prompt. Estimates ignore failed/retried API calls and use the logged (possibly summarized or missing) reasoning, so agent output tokens are a lower bound.

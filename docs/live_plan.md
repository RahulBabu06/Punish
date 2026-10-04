# Live plan: when Anthropic credits return

Run from the repository root, offline by default:

```bash
source .venv/bin/activate
python scripts/live_plan.py                 # same as --dry-run
python scripts/live_plan.py --dry-run > live-plan.txt

# Only after restoring credit, authenticating Modal, and configuring its `anthropic` secret:
python scripts/live_plan.py --run --max-usd 200
```

The script prints **every exact Modal command**, expected output directory, prerequisite
failures, pending call counts and API cost estimates. No live experiment was run to develop it.
`--run` executes sequentially, recalculating each step from the files present at that point.
The optional `--max-usd` checks the initial estimate, including blocked work; it is **not a
hard billing cap**. Modal must already have an authenticated profile and an `anthropic` secret
containing `ANTHROPIC_API_KEY`. Local Modal auth and output writability are checked; validity
of the remote secret, account credit, model access and image builds cannot be checked offline.

## Priority and outputs

| key | work | expected output |
|---|---|---|
| `judge-v3` | Opus judges the 450 existing v3 traces, including complete Haiku | `results/v3*/judgments/` |
| `finish-v3` | Fill 370 missing episodes; Sonnet 50, Opus 93, conditional Haiku 72 / Sonnet 73, fault Sonnet 82; preserve fault rate 0.5 | Original `results/v3*/{trajectories,verdicts,episodes}/` |
| `judge-new-v3` | Opus judges newly completed traces | Original `results/v3*/judgments/` |
| `hard-cases` | Sonnet and Opus, all three modes, 32 cases | `results/hard_cases/<model>/` |
| `monitor-attacks` | Sonnet and Opus, all three modes, 70 variants | `results/monitor_attacks/<model>/` |
| `agentic` | 12 Sonnet-v2 traces: six tasks × honest/covert, episode 0; full_trace/report_only | `results/v2_sonnet46/reaudit_agentic_sonnet/` |
| `retry` | Small 20-episode audit-and-retry pilot: ten tasks × covert/pressure, episode 0; three audit modes; full_trace veto | `results/mitigation_retry_live/` |
| `rubric-v3` | Sonnet and Opus re-audit all 360 v2 traces, all three modes | `results/v2_*/reaudit_<model>_rubric_v3/` |
| `rejudge-leaked` | Re-judge 60 v2 leaked_answer traces with matched historical definitions | `results/v2_*/rejudge_matched/judgments/` |

Priority is cheap labels first, completion of already-started runs next, followed by controlled
auditor benchmarks and smaller verification/mitigation pilots before comprehensive re-auditing.
To run a smaller budget slice, choose keys; canonical order is retained:

```bash
python scripts/live_plan.py --steps judge-v3,hard-cases,agentic --run
```

## Checks and resumption

- Actual Modal `--help` output is parsed for every referenced module and flag without deployment.
  The task/config registry, source directories, labelled case corpora and selected trajectory IDs
  are checked. Historical leaked-answer definitions are resolved locally before launching jobs;
  the Modal judge receives the matched task, not the newest one.
- Sweeps are split into contiguous **missing** task/config/episode ranges using `--start-episode`.
  Existing complete trajectories are never resampled; missing audit modes are repaired through
  batch reaudit in the original directory. Fault runs retain their recorded 0.5 injection rate.
- Batch `--only` selects exact IDs and rejects unknown ones. Judges skip existing destination
  judgments; re-audits skip complete verdict/episode pairs per mode and backend. Hard-case and
  monitor runners cache individual verdicts while rebuilding summaries over **all modes/cases**.
- Retry checkpoints are completed `mitigation/<id>.json` records. Failed/in-flight remote jobs
  without mirrored outputs may need rerunning and can incur additional cost; this is not an
  exactly-once API/billing guarantee. Do not launch two planners concurrently against one output.
- Each command's outputs are checked even if Modal exits zero. Missing/corrupt output stops the
  plan; rerun the same command to resume. Missing prerequisites stop execution before spending.
- **Rubric placeholder:** until `devin/rubric-v3` is merged, `--rubric v3` commands are explicitly
  blocked. They are printed, not executed; other ready steps continue and `--run` exits 2 to
  indicate the deferred work. Pull the integrated code after merge, then run
  `python scripts/live_plan.py --steps rubric-v3 --run`. No branch is automatically merged.
- If the monitor corpus is absent, the dry run prints the offline repair command
  `python -m eval.monitor_attacks --build`; rebuild it before running the live plan.

Historical v2 leaked_answer data gives honest p≈0.312, unlike the current p≈0.006 task. Original
judgments are preserved, and the separate matched-definition judgments must be used when
recalculating labels. The monitor corpus itself includes disputed historical judge positives
(including leaked-answer and disclosed imputation); attack robustness is not clean ground-truth
accuracy. See [judge validation](judge_validation.md) and [example audit](examples_audit.md).

## Cost method

Standard auditor/judge per-call averages come from the **committed token rows** generated by
`eval/cost.py` in `results/COST.md`, repriced with `eval.cost.usd`. Agent turn costs and turns per
episode are computed using `eval.cost.agent_records` over available trajectories. Models are
kept separate; Opus reaudit observations supply the Opus auditor rate. This is an empirical
proxy, not a token-by-token prediction for the longer hard/monitor prompts or new rubric.

Calls in the table mean **estimated API requests**, not episodes: subjects make multiple
requests per episode. Agentic uses an eight-turn standard-audit-cost proxy (24 audit jobs,
192 requests); recomputation/fallback/repair traffic can differ. Retry assumes 50% flagged
and retried (20 first attempts + 10 retries); if every episode retries, its estimate is 4/3
as large. Historical thinking, retries and Modal compute are undercounted or excluded.

On the starting committed data the plan estimates **$178.18**, of which **$64.33** is the
blocked rubric-v3 step. Counts/costs shrink as outputs are completed; the script's current
dry run is authoritative, not these snapshot numbers.

```bash
.venv/bin/pytest -q tests/test_live_plan.py tests/test_judge_task_version.py tests/test_hard_cases.py
```

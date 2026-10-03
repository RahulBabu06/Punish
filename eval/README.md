# `eval/`

Evaluation harness: runs episodes (task → agent trajectory → ground-truth label → auditor verdict → Episode result), sweeps them on Modal or locally, and measures the auditor. Schemas are defined in [ARCHITECTURE.md](../ARCHITECTURE.md).

Setup (Python 3.11): `~/.local/bin/uv venv --allow-existing -p 3.11 .venv && ~/.local/bin/uv pip install -p .venv -e .`. Real runs need `ANTHROPIC_API_KEY`. Models come from `PUNISH_AGENT_MODEL` / `PUNISH_AUDITOR_MODEL`; when those are unset, `agent/` and `auditor/` choose their own default (`claude-sonnet-4-6`).

## Single episode — `eval/run_episode.py`

```bash
python -m eval.run_episode --task leaked_answer --config incentivized --episode 0 \
    [--auditor-mode full_trace|report_only|both] [--auditor-backend claude|heuristic] [--results-dir results]

# re-audit an existing trajectory without re-running the agent (cheap full_trace vs report_only comparison)
python -m eval.run_episode --trajectory results/trajectories/leaked_answer__incentivized__ep000.jsonl \
    --auditor-mode both --auditor-backend heuristic
```

```python
from eval.run_episode import run_episode, run_episode_modes, audit_existing
ep  = run_episode("leaked_answer", "incentivized", 0, auditor_mode="full_trace", auditor_backend="claude")
eps = run_episode_modes("leaked_answer", "incentivized", 0, ["full_trace", "report_only"])  # one agent run, 2 audits
ep2 = audit_existing("results/trajectories/leaked_answer__incentivized__ep000.jsonl", "report_only", "heuristic")
```

Every dependency can be injected (`load_task_fn`, `run_agent_fn`, `audit_fn`, `label_fn`). When one is `None`, it is lazy-imported from `tasks.registry`, `agent.runner.run_agent`, `auditor.audit.audit` or `auditor.heuristic.heuristic_audit`.

### Output files

| file | path |
|---|---|
| trajectory (one per agent run) | `results/trajectories/<episode_id>.jsonl` |
| verdict | `results/verdicts/<episode_id><suffix>.json` |
| episode result | `results/episodes/<episode_id><suffix>.json` |

| auditor_mode / backend | `<suffix>` |
|---|---|
| full_trace / claude | *(none — the ARCHITECTURE.md path)* |
| report_only / claude | `__report_only` |
| full_trace / heuristic | `__heuristic` |
| report_only / heuristic | `__report_only__heuristic` |

The `episode_id` field inside the JSON is always the canonical `<task_id>__<agent_config>__epNNN`. Episode results also carry an extra `auditor_backend` field (`"claude"` or `"heuristic"`); metrics treat a missing field as `"claude"`.

## Sweep — `eval/sweep.py`

```bash
modal run eval/sweep.py --n-episodes 5                       # all tasks × honest,incentivized × full_trace,report_only
modal run eval/sweep.py --n-episodes 2 --tasks leaked_answer --configs incentivized --auditor-modes full_trace
python -m eval.sweep --local --n-episodes 1 [--workers 8]   # no Modal: local thread pool, same grid
```

For Modal, the `anthropic` secret must exist and provide `ANTHROPIC_API_KEY` (`modal secret create anthropic ANTHROPIC_API_KEY=...`). Each `episode_job` runs the agent once, audits the trajectory in every requested mode, and returns the files it wrote. It retries up to 2 times and times out after 30 minutes. The local entrypoint mirrors the returned files into `results/`, reports failed jobs without aborting, and writes `results/SUMMARY.md`.

## Metrics — `eval/metrics.py`

```bash
python -m eval.metrics [results/episodes] [--out results/SUMMARY.md] [--json results/metrics.json]
```

`compute_metrics(episodes, tasks=None)` computes:

- precision, recall, F1, accuracy and Brier score (positive = hacked), overall and per task, agent_config, auditor_mode and auditor backend;
- per-hack_type recall on ground-truth-hacked episodes, against each task's `exploit.expected_hack_types` (tasks lazy-load, and unknown tasks are skipped);
- honest vs incentivized hack rate, deduplicated per trajectory;
- a 5-bin confidence calibration table plus the Brier score;
- full_trace vs report_only accuracy, paired on the same trajectory and backend.

Undefined ratios are `None` (shown as `n/a`). `write_summary(metrics, path)` renders markdown tables.

## Cost — `eval/cost.py`

```bash
python -m eval.cost results/v2_sonnet46 results/v2_haiku45 [--by-dir] [--out COST.md] [--json cost.json]
```

Sums tokens per role (`agent` trajectories, `auditor` episodes/verdicts, `judge` judgments, `reaudit` episodes/verdicts in any subdirectory) and model, and prices them with the editable `PRICES_PER_MTOK` table (USD per million tokens, from Anthropic's public pricing page). Real counts come from the optional `usage` fields that `agent/runner.py` (assistant events), `auditor/audit.py` (Verdict) and `eval/judge.py` (judgment) now record. Runs without them are estimated (`source=estimate`): characters / 4 of the request rebuilt from the trajectory (system prompt, tool schemas and the conversation so far for each agent turn; the rendered audit/judge prompt), plus the API's hidden tool-use system prompt. Estimates don't count failed or retried calls and see only the logged (possibly summarized) reasoning, so they are lower bounds. Episodes without `auditor_model` are priced as `--default-auditor-model` (`claude-sonnet-4-6`). `eval/batch.py` prints the usage totals of each judge/reaudit job.

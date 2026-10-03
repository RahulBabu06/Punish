# `results/` index

Every committed experiment directory. The table is generated from the committed files by
`python scripts/sweep_commands.py --index --cost-json <(eval.cost --by-dir --json)`; the exact launch command
behind each directory is printed by `scripts/reproduce.sh sweep`.

| dir | subject model | agent configs | tasks | n | auditor modes | judged | trajectories | status | est. cost |
|---|---|---|---|---|---|---|---|---|---|
| `model_probe/` | haiku-4-5, opus-4-6, sonnet-4-5, sonnet-4-6 | covert | leaked_answer | 1 per model | none | no | 4 | complete | $0.35 |
| `probe_v1/` | sonnet-4-6 | pressure, covert | 6 | 3 | full_trace, report_only, final_report | 36/36 | 36/36 | complete | $5.19 |
| `v2_haiku45/` | haiku-4-5 | honest, incentivized, pressure, covert | 6 | 5 | full_trace, report_only, final_report; reaudit_claude-opus-4-6: 3 modes | 120/120 | 120/120 | complete | $30.06 |
| `v2_sonnet45/` | sonnet-4-5 | honest, incentivized, pressure, covert | 6 | 5 | full_trace, report_only, final_report | 120/120 | 120/120 | complete | $23.46 |
| `v2_sonnet46/` | sonnet-4-6 | honest, incentivized, pressure, covert | 6 | 5 | full_trace, report_only, final_report; reaudit_claude-opus-4-6: 3 modes | 120/120 | 120/120 | complete | $34.67 |
| `v3_haiku45/` | haiku-4-5 | honest, incentivized, pressure, covert | 10 | 5 | full_trace, report_only, final_report | no | 200/200 | complete | $20.82 |
| `v3_opus46/` | opus-4-6 | honest, incentivized, pressure, covert | 3 of 10 | 3 | full_trace, report_only, final_report | no | 27/120 | partial | $4.57 |
| `v3_sonnet46/` | sonnet-4-6 | honest, incentivized, pressure, covert | 8 of 10 | 5 | full_trace, report_only, final_report | no | 150/200 | partial | $22.89 |
| `v3cond_haiku45/` | haiku-4-5 | covert_monitored, sycophantic_pi | 4 of 10 | 5 | full_trace, report_only, final_report | no | 28/100 | partial | $2.69 |
| `v3cond_sonnet46/` | sonnet-4-6 | covert_monitored, sycophantic_pi | 3 of 10 | 5 | full_trace, report_only, final_report | no | 27/100 | partial | $3.87 |
| `v3fault_sonnet46/` | sonnet-4-6 | honest, incentivized (fault rate 0.5) | 3 of 10 | 5 | full_trace, report_only, final_report | no | 18/100 | partial | $2.98 |
| **total** | | | | | | 396 judged | 850 | | **$151.54** |

Two directories hold derived analyses rather than new agent runs, so the table above does not include them.
Neither made any API calls:

- `hard_cases/`: the offline heuristic auditor (`auditor.heuristic`) on the 32 hand-labelled red-team cases in
  `fixtures/hard_cases/`, in `full_trace` and `report_only` (64 verdicts). Rebuild it with
  `python -m eval.hard_cases`.
- `mitigation_bestofn_v2/`: offline best-of-n with an auditor veto (`python -m eval.mitigate best-of-n`). It runs
  over the existing `v2_sonnet46/` and `v2_haiku45/` trajectories and their Sonnet 4.6 `full_trace` verdicts.

Column notes:

- **Subject model**: the `config.model` header of each trajectory. Full ids are `claude-haiku-4-5-20251001`,
  `claude-sonnet-4-5-20250929`, `claude-sonnet-4-6` and `claude-opus-4-6`.
- **Tasks**: `6` is the original six-task suite (`cherry_pick, fabrication, fake_citation, leaked_answer,
  metric_gaming, metric_swap`). `10` is the v3 suite (adds `effect_size_target, missing_replication,
  outcome_switching, solutions_cache`, and regenerates `leaked_answer`). The deterministic labels of the older
  runs are frozen in their `episodes/`.
- **Auditor**: the original audits use the default auditor, `claude-sonnet-4-6` (verdicts written before usage
  tracking do not record their model). `reaudit_claude-opus-4-6/` holds the same trajectories re-audited by
  Opus 4.6.
- **Judged**: privileged Opus 4.6 judge labels in `judgments/`.
- **Est. cost**: from `python -m eval.cost --by-dir` (agent + auditor + judge + reaudit). Every committed run
  predates usage tracking, so all of it is an **estimate** (characters / 4 of the rebuilt prompts and the logged
  outputs). It is a lower bound: thinking tokens are only partly logged, and retried calls are not counted. The
  per-role breakdown is in [`COST.md`](COST.md).

## Why the v3 runs are partial

All `v3*` runs **stopped when the team's Anthropic API credit ran out**. That is
also why none of them has judge labels yet (`modal run eval/batch.py --results-dir results/<dir> --job judge`).

- `v3_haiku45/` finished (200/200).
- `v3_sonnet46/` has 150 of 200 trajectories. `outcome_switching` and `solutions_cache` never started, and
  `leaked_answer`, `metric_swap` and `missing_replication` are incomplete.
- `v3_opus46/`, `v3cond_*` (the `covert_monitored` and `sycophantic_pi` configs) and `v3fault_sonnet46/`
  (tool-failure injection, `--fault-rate 0.5`) cover only the first 3–4 tasks alphabetically. For these the task
  list and grid size are inferred: the launch is assumed to be the full 10-task suite, and `n` is the largest
  episode index + 1.

Analyses that use these directories should report them as partial. `eval.analyze` treats a missing judge label
as unknown, not as clean.

## Layout

Each directory has `trajectories/<task>__<config>__epNNN.jsonl` and `verdicts/<id>[__<mode>].json` (no suffix
means `full_trace`). It also has `episodes/` (verdict + deterministic label), `judgments/` (Opus judge, where
judged) and `SUMMARY.md` (labeller-only metrics). Top-level files are generated:

- `RESULTS.md`, `RESULTS.json` and `RESULTS_thresholds.csv`, plus `figures/*.svg`: `scripts/reproduce.sh
  analyze`, which runs `python -m eval.analyze` over every directory with `episodes/`.
- `COST.md`: `scripts/reproduce.sh cost`.

## Secrets check

The committed trajectories, verdicts, episodes and judgments were searched for API keys and tokens
(`sk-ant`, `sk-…`, `ak-…`, `as-…`, `ANTHROPIC_API_KEY`, `MODAL_TOKEN`, `api_key`, AWS `AKIA…`, GitHub `gh?_…`,
Slack `xox?-`, private-key headers, JWTs, `Bearer`, `password`, 40-hex tokens). Nothing was found. The only
pattern hits were ordinary text: "asterisk-asterisk", "as-submitted", and the sandbox path `/home/sandbox/tests`.

# Hard cases: auditor red-team benchmark

36 hand-labelled trajectories on the real tasks in `tasks/definitions/`; they need no subject model.
Each case is `<case>.jsonl`, a schema-valid trajectory (ARCHITECTURE.md), plus `<case>.label.json`
(`{"hacked", "hack_types", "why", "category", "task_id", "based_on"}`).

| prefix | category | n | what it tests |
|---|---|---|---|
| `hn_` | hard_negative | 10 | honest runs that look suspicious: reads eval.py/grader/cache/tests and then computes honestly, runs the grader only to check the format, discloses a post-hoc exclusion, reports a null primary result, says the cited papers do not test the claim, hits a tool error and then fixes and discloses it |
| `pa_` | obfuscated_hack | 4 | attacks on the rubric-v3 proxy's clearing rule (`eval/rubric_v3.py`): read the grader, compute something honest, report a grader-pleasing value (grader read inside run_python, arithmetic laundering, decoy assumption-test p, decoy `R2 =`); see docs/rubric_v3.md |
| `oh_` | obfuscated_hack | 10 | the hack is visible in the actions but the reasoning is bland: a copied leaked value, a "units sanity check" that reads the answer, hedged fabrication, a mislabelled metric, a wrong effect-size denominator, a post-hoc site exclusion, silent imputation, a headline secondary outcome, an invented citation |
| `ro_` | reasoning_only | 5 | actions and report look defensible, but the reasoning admits intent (rounding toward the expected value, binning to reach R^2 >= 0.9, a split-half "replication", supportive framing, spin) |
| `rp_` | report_only | 7 | an honest trace, but the report adds checks or numbers that were never computed |

The assistant text was written by hand, based on runs in `results/v2_sonnet46`, `results/v2_haiku45` and
`results/probe_v1` (see `based_on`). Every tool result is real output: `build.py` runs each tool call in an
`agent.tools.Sandbox`, so outputs, exit codes, line numbers and `tc_N` pairing match what a live run would record.

```
python3 fixtures/hard_cases/build.py            # regenerate (needs numpy, scipy and pandas)
python -m eval.hard_cases --auditor heuristic   # score an auditor (see eval/hard_cases.py)
```

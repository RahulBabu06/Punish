# Offline bug-hunt results

Core fixes were pushed on `devin/bug-hunt`, through `fb5d0f0`. The coordinator reports that these
are merged into integration. The results follow-up branches from integration `dd93355` on
`devin/bug-hunt-results`; no PR or live model calls were made here.

## Confirmed bugs and regressions

"Forward only" means no saved prediction or label was rewritten. Regression tests live in the
linked modules; focused fixes have separate commits. The overly broad introspection restrictions
introduced during this review were removed, not retained as a security feature.

| Severity | Bug / fix | Regression coverage | Committed-number impact |
|---|---|---|---|
| High | Guard logging could fail open; validation failures now deny the operation. | [agent v2 tests](../tests/test_agent_v2.py) | Forward only |
| High | Task modules could shadow bootstrap imports; use isolated Python and trusted bootstrap loading. | [agent v2 tests](../tests/test_agent_v2.py) | Forward only |
| High | Forked descendants and timeout cleanup could escape tool lifetime; deny fork/forkpty and bound cleanup. | [agent v2 tests](../tests/test_agent_v2.py) | Forward only |
| High | DNS/network audit events were not all blocked; deny DNS queries and datagram/sendmsg channels. | [agent v2 tests](../tests/test_agent_v2.py) | Forward only |
| High | Read-allowlist symlinks were not canonicalized; resolve them before containment checks. | [agent v2 tests](../tests/test_agent_v2.py) | Forward only |
| Medium | Filesystem errors could abort tool-result pairing; return structured errors. | [agent v2 tests](../tests/test_agent_v2.py) | Forward only |
| High | Python-written reports were lost, and failed calls could look successful; capture the final report file and validate paired historical recovery. | [runner tests](../tests/test_agent.py), [auditor tests](../tests/test_auditor.py), [task tests](../tests/test_tasks.py) | 3 recovered reports; heuristic confidence/evidence and estimated costs change |
| High | Restricted modes exposed system file manifests or accepted hidden-line evidence; filter visibility and validate original allowed line numbers. | [auditor tests](../tests/test_auditor.py), [agentic tests](../tests/test_auditor_agentic.py) | Cost/evidence diagnostics change; saved Claude verdicts unchanged |
| Medium | Unicode separators split physical JSONL events; parse only physical newlines. | [auditor tests](../tests/test_auditor.py), [agentic tests](../tests/test_auditor_agentic.py) | Forward only |
| Medium | Unhashable hack types/nonfinite ranges crashed verdict repair; filter malformed values safely. | [auditor tests](../tests/test_auditor.py) | Forward only |
| Medium | Ensemble/agentic usage omitted samples or turns; accumulate usage and include agentic cost records. | [ensemble tests](../tests/test_auditor_ensemble.py), [agentic tests](../tests/test_auditor_agentic.py), [cost tests](../tests/test_cost.py) | Forward only on saved usage fields |
| Medium | Retry feedback omitted tool-use IDs; pair every emitted call with a result. | [auditor tests](../tests/test_auditor.py), [ensemble tests](../tests/test_auditor_ensemble.py) | Forward only |
| High | Cascade overwrote duplicate audits and metrics conflated auditor/experiment identities; retain rubric/backend/sample identities, deduplicate identical records and reject conflicts. | [cascade tests](../tests/test_cascade.py), [metrics tests](../tests/test_eval.py) | No saved-data metric change from identity fixes |
| High | Cache printing counted as independent computation; exclude cache-derived calculations from that exemption. | [task tests](../tests/test_tasks.py) | 2 current-rule clean → hacked flips; saved labels unchanged |
| High | Disclosed plate imputation counted as hidden fabrication; distinguish disclosure from unsupported all-plate agreement. | [task tests](../tests/test_tasks.py) | 7 current-rule hacked → clean flips; saved labels unchanged |
| High | Judge-less headline tables selected positive-only `either`; select labeller when no judgments exist. Benchmark also treated missing judgments as clean; preserve `None`. | [analysis tests](../tests/test_eval_analyze_stats.py), [provenance tests](../tests/test_auditor_provenance.py) | v3 denominator/ROC/calibration outputs regenerated; benchmark fix has no saved v2 metric change |
| Medium | F1 was undefined despite a nonzero denominator; use `2TP/(2TP+FP+FN)`. | [metrics tests](../tests/test_eval.py) | 44 computed F1 slices undefined → 0 |
| Medium | Scientific paired helpers silently truncated unequal inputs; require strict lengths. | [task tests](../tests/test_tasks.py) | Forward only |
| High | Saved v3 summaries predated already-committed relabeling; refresh from frozen episode records. | [artifact parity tests](../tests/test_bug_hunt_check.py) | Existing displayed rates/confusion counts change; no label rewrite |

## Before → after

The complete displayed-cell and computed-metric deltas are in
[changes.csv](../results/bug_hunt/changes.csv). [check.json](../results/bug_hunt/check.json)
compares `4193c4c` with the core-fix state; its displayed artifact changes also include regeneration
of stale summaries. [followup_check.json](../results/bug_hunt/followup_check.json) compares
the integration base with the derived-results follow-up: **zero further label/prediction flips**.
The integrity check hashes historical episode, trajectory and judgment files and rejects mutation.

| Existing summary | Overall F1 before → after | Reason |
|---|---|---|
| v3 Haiku | .636 → .759 | Refresh stale summary from frozen records |
| v3 Sonnet | .617 → .660 | Refresh stale summary from frozen records |
| v3 Opus | .214 → .000 | Refresh stale summary; correct undefined F1 |
| v3cond Sonnet | .429 → .688 | Refresh stale summary from frozen records |
| v3fault Sonnet | .286 → .000 | Refresh stale summary; correct undefined F1 |

These are **not** newly measured model improvements. Saved predictions and labels did not change.
There are 1,376 changed displayed cells across regenerated summary/analysis tables; the CSV lists
each one, including confidence intervals and new/missing table cells. The v3 preliminary analysis
and four v3 figures now use labeller denominators rather than positive-only `either` headlines.
The corrected-v2 headline figure is unchanged by this follow-up; updates already merged by other
branches are not attributed to these fixes.

Current-rule comparisons cover **846 trajectories**: two cache-copy flips to hacked and seven
disclosed-imputation flips to clean (two v2 Sonnet and five v3 Sonnet). These are separate from frozen
historical ground truth. The three recovered reports are v2 Haiku fabrication/covert/ep003,
v2 Haiku metric_gaming/covert/ep001 and v3 Haiku metric_gaming/incentivized/ep001.
No saved Claude audits were rerun or rewritten, so their report-loss false negatives cannot be
retroactively claimed as fixed measurements.

Evidence diagnostics were rerun in [EVIDENCE.md](../results/bug_hunt/EVIDENCE.md) and
[evidence.json](../results/bug_hunt/evidence.json). On the matched 19-trace v2 gold cohort,
heuristic full-trace precision is .656 → .691, recall .293 → .276 and hit@1 .368 → .316;
report-only precision is .649 → .686, recall .293 → .276 and hit@1 .368 → .316.
The detection flags on the 846 primary trajectories do not change; evidence selection does.

Estimated costs were recomputed in [COST.md](../results/COST.md). Over probe/v2/v3, excluding
model_probe, the reconstructed estimate is $162.115528 → $161.986744. This is a revised
character-based prompt estimate, **not** a change in actual billed spending. All 12 affected
role/model rows and their input-token deltas are recorded in the comparison. Historical usage
fields are untouched.

## Limits and non-bugs

- AUROC already grants half-credit to tied scores; no tie fix was required.
- Subprocess credential allowlisting passes its regression tests; no credential leak was reproduced.
- Broad frame/introspection blocking broke NumPy, logging, traceback and NamedTuple; it was removed.
- The Python sandbox remains best-effort, not an OS-level jail. Native-code access is not a promised boundary.
- The in-sample cascade/held-out item was explicitly assigned elsewhere and skipped here. Calibration's
  existing leave-one-task-out fits/thresholds were reviewed, not replaced with in-sample reporting.
- Protected write-ups were not edited by this follow-up. Old prose estimates and gold-label disagreements
  remain historical evidence, not automatic updates to ground truth.

## Reproduce offline

```bash
# Snapshot a trusted checkout; no trajectory code or live API calls are executed.
.venv/bin/python scripts/bug_hunt_check.py --out snapshot.json
# Regenerate only derived summaries and v3 analysis/figures, never episode labels.
.venv/bin/python scripts/bug_hunt_check.py --refresh --out refreshed.json
.venv/bin/python scripts/bug_hunt_check.py --compare before.json after.json --out check.json
.venv/bin/pytest -q -rs
.venv/bin/python -m compileall -q agent auditor eval tasks tests scripts
.venv/bin/ruff check . --select F,E9,B
git diff --check
```

Final validation results are reported in the session. The two expected failures and two skips are
existing test-suite outcomes, not silently dropped checks.

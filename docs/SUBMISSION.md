# Submission form: London AI x Science Hackathon, Track 2, team Punish

Copy-paste text for the submission form. Every number below comes from a committed results file; headline
numbers use the corrected label, and `tests/test_claims_audit.py` checks them against the source files.

## Title

Punish: an auditor that catches AI science agents reward-hacking

## Tagline

It reads what the agent did, not just what it wrote.

## Abstract

AI agents doing science are scored by graders, and graders can be gamed. Punish builds science tasks
with planted exploits (a leaked answer key, a grader that rewards a high R², a sponsor who wants significance,
a thin bibliography) and runs Claude subject agents under honest, incentivised, pressured and covert
prompts. A Claude auditor reads each trajectory (reasoning, tool calls, final report) and
returns a verdict with hack types and line-level evidence. On 360 v2 trajectories (93 hacked under
corrected labels), a Sonnet 4.6 auditor reading the full trace reaches 0.90 recall at 0.34 FPR (AUROC 0.891);
reading only the final report gives 0.74 recall at 0.23 FPR (AUROC 0.825). As a veto in best-of-n selection,
the auditor cuts the shipped-hack rate from 0.28 to 0.15. A rule-based heuristic in front of Claude reaches
80.4% recall at 5.4% FPR in-sample, but 62.7% at 2.9% on a held-out, labeller-only cohort. Ground truth is
AI-made and costs are estimates.

## Key results

1. **Seeing the trace catches more instructed hacks, not more natural ones.** On 360 v2 trajectories (93
   hacked, corrected label), Sonnet 4.6 reading reasoning, actions and report (`full_trace`) gets 0.90 recall,
   0.34 FPR and AUROC 0.891. Reading the final report alone (`final_report`) gets 0.74 recall, 0.23 FPR and
   AUROC 0.825. The gap comes from instructed (`covert`) hacks, 66/93 of the positives. On natural hacks the
   report alone catches 26/27 against 20/27 with actions, and `full_trace` recall is 19/27 = 0.70 (Opus
   5/17 = 0.29). On labeller-only v3 the instructed-only gain replicates (+0.24 recall, accuracy p = 0.003)
   but the reversal does not (19/26 each); natural `full_trace` recall there is 12/26 = 0.46. Most false positives are honest runs that read the grader file.
2. **The auditor is useful as a veto.** In best-of-n selection over 240 matched runs, vetoing flagged
   candidates before picking the best-graded one cuts the shipped-hack rate from 0.28 to 0.15.
3. **A cheap cascade works, but less well out of sample.** Heuristic → Sonnet reaches 80.4% recall at 5.4% FPR
   (45/56, 10/184) on v2, where the heuristic's rules and the thresholds were both fit. On the v3 cohort,
   which the rules never saw, it gets 62.7% recall at 2.9% FPR (64/102, 10/348), scored against
   labeller-only labels.

## What's novel

- **Visibility as the experimental variable.** The same trajectories are audited with reasoning + actions +
  report, actions + report, and report only, so we measure what each layer of the trace adds to detection.
- **Science tasks with planted exploits and checkable ground truth.** Every task carries a deterministic
  labeller. On top of it sit an AI judge, a documented label correction, hand-labelled red-team hard cases
  and monitor-evasion attacks on the auditor.
- **Auditing as a mitigation, with honest accounting.** The auditor serves as a best-of-n veto and in a
  cost-saving heuristic → Claude cascade. In-sample, held-out, proxy and estimated numbers are labelled
  separately throughout.

## Limitations

- **Ground truth is AI-made.** Labels come from an Opus judge plus the deterministic labeller. The judge
  saw a stale `leaked_answer` definition, so headline numbers use the corrected label.
- **v3 is labeller-only, and some runs were never made.** v3 has no judge labels, and the held-out cascade
  is scored against a rule-based labeller, which may flatter a rule-based heuristic. The live agentic auditor
  and the opt-in rubric-v3 were never run with Claude (the credit ran out); the rubric-v3 figures are an
  offline proxy.
- **Config leak.** 75/90 `covert` runs name the red-team or reward-hacker role in their reasoning, so
  `full_trace` can read the config. Opus's reasoning gain still holds without them (+0.056 accuracy).
- **Clustered CIs.** There are 5 episodes per cell and only 6 tasks; resampling by cell widens the CIs up to
  about 2×.
- **Precision at realistic prevalence.** Sonnet `full_trace` precision is 0.48 at the study's 26% hack rate
  and would be 0.12 at 5%.
- **Costs are estimates.** The $162.33 for 8,519 API calls is estimated from prompt and response character
  counts, not billed spend.

## How to run it (offline, no API key)

```bash
git clone https://github.com/RahulBabu06/Punish && cd Punish
~/.local/bin/uv venv -p 3.11 .venv && ~/.local/bin/uv pip install -p .venv -e .
.venv/bin/python -m demo.app --port 8000 --delay 1.2    # open http://localhost:8000/view
```

## Links

- [README](../README.md)
- [REPORT](../REPORT.md)
- [PITCH](../PITCH.md)
- [Paper (PDF)](../paper/punish.pdf)
- [Static demo](demo.html)
- [Slides](slides.html)
- [Review guide](REVIEW_GUIDE.md)

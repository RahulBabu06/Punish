# Open-weight auditor: Qwen3-30B-A3B on Modal

The same auditor prompt, `submit_verdict` schema and evidence validation as the Claude auditor
(`auditor/audit.py`), served by `live/vllm_server.py` (vLLM on one Modal H100) and called through
`live/openai_client.py`. It re-audits the 360 committed v2 trajectories (subjects Sonnet 4.6, Haiku 4.5,
Sonnet 4.5) in all three modes. 1080 audits, 0 failures; 7.16M input / 1.19M output tokens; about 25 minutes
on one GPU at 48 concurrent requests.

```bash
modal deploy live/vllm_server.py                      # once; secret punish-vllm holds PUNISH_VLLM_API_KEY
export PUNISH_VLLM_URL=https://<workspace>--punish-vllm-serve.modal.run PUNISH_VLLM_API_KEY=...
for e in v2_sonnet46 v2_haiku45 v2_sonnet45; do
  python -m eval.batch --local --results-dir results/$e --job reaudit --auditor open \
      --out-dir results/open_weight_auditor/runs/$e/reaudit_qwen3-30b-a3b --workers 16
done
python -m eval.analyze results/open_weight_auditor/runs/v2_{sonnet46,haiku45,sonnet45} --out results/open_weight_auditor/RESULTS.md
```

The re-audits live in `runs/<exp>/reaudit_qwen3-30b-a3b/`, outside the experiment directories, so the committed
analyses that scan every `reaudit_*` directory are unchanged. `runs/<exp>/` symlinks the experiment's `episodes/`,
`judgments/`, `trajectories/` and Opus re-audit, so `eval.analyze` sees all auditors side by side.
`RESULTS.md` here uses the `either` label (123 hacked). The tables below use the `corrected` label
(`eval/labels.py`, 93 hacked), the headline label in README/REPORT. The Sonnet rows reproduce REPORT §8.2.
Opus re-audited only two of the three experiments (240 trajectories).

## All 360 trajectories (corrected label, 93 hacked)

| auditor | mode | recall | FPR | precision | AUROC |
|---|---|---|---|---|---|
| Qwen3-30B-A3B | `full_trace` | 0.95 (88/93) | 0.12 (32/267) | 0.73 | **0.966** |
| Qwen3-30B-A3B | `report_only` | 0.82 (76/93) | 0.10 (28/267) | 0.73 | 0.893 |
| Qwen3-30B-A3B | `final_report` | 0.15 (14/93) | 0.08 (21/267) | 0.40 | 0.542 |
| Sonnet 4.6 | `full_trace` | 0.90 (84/93) | 0.34 (92/267) | 0.48 | 0.891 |
| Sonnet 4.6 | `report_only` | 0.91 (85/93) | 0.35 (94/267) | 0.47 | 0.840 |
| Sonnet 4.6 | `final_report` | 0.74 (69/93) | 0.23 (62/267) | 0.53 | 0.825 |
| Opus 4.6 (240) | `full_trace` | 0.77 (43/56) | 0.22 (41/184) | 0.51 | 0.861 |
| Opus 4.6 (240) | `report_only` | 0.62 (35/56) | 0.27 (50/184) | 0.41 | 0.821 |
| Opus 4.6 (240) | `final_report` | 0.62 (35/56) | 0.20 (36/184) | 0.49 | 0.808 |

## Natural hacks only (excluding `covert`; 270 trajectories, 27 hacked)

| auditor | `full_trace` recall / FPR / AUROC | `report_only` | `final_report` |
|---|---|---|---|
| Qwen3-30B-A3B | 25/27 / 0.09 / 0.950 | 24/27 / 0.09 / 0.912 | 2/27 / 0.08 / 0.484 |
| Sonnet 4.6 | 19/27 / 0.31 / 0.769 | 20/27 / 0.33 / 0.744 | 26/27 / 0.21 / 0.860 |
| Opus 4.6 (180, 17 hacked) | 5/17 / 0.18 / 0.749 | 4/17 / 0.24 / 0.716 | 12/17 / 0.18 / 0.820 |

## Reading this

- With the trajectory visible, the 30B open-weight model (3B active parameters) beats both Claude auditors on
  these runs, mostly through a much lower false-positive rate. Unlike Sonnet and Opus, it also keeps that lead
  on natural hacks, where the covert runs' self-disclosure can't help.
- Given only the final report it is near chance: 291/360 `final_report` verdicts have confidence ≤ 0.15. It
  gives polished reports the benefit of the doubt, so on this model visibility into the process matters most.
- Caveats: one sample per audit, 27 natural hacks, in-sample (no prompt or threshold was tuned for Qwen, but
  the tasks are the ones the rubric was written against). The labels come from the rule-based labeller plus
  an Opus judge that saw the whole trace, which may favour auditors that read the trace the same way. Qwen
  audits Claude-written trajectories, so this says nothing about auditing its own family.

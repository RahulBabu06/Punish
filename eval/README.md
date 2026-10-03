# `eval/`

Evaluation harness. Owns `run_episode.py` (task → trajectory → verdict → Episode result), `sweep.py` (Modal entrypoint, `Function.map` over tasks × configs × episodes) and `metrics.py` (precision/recall per task and hack_type, calibration, honest-vs-incentivized hack rate, full_trace vs report_only).

See the `eval/` section of [ARCHITECTURE.md](../ARCHITECTURE.md) for the spec and schemas.

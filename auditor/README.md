# `auditor/`

Auditor: Claude instance that reads a trajectory JSONL and returns a Verdict (`hack_detected`, `hack_types`, `evidence` line ranges, `confidence`). Owns `audit.py` (`audit`, modes `full_trace` / `report_only`) and `prompts.py` (rubric). Develop against `fixtures/trajectories/example.jsonl`; expected output is `fixtures/verdicts/example.json`.

See the `auditor/` section of [ARCHITECTURE.md](../ARCHITECTURE.md) for the spec and schemas.

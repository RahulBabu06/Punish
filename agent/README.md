# `agent/`

Subject agent: Claude with `read_file` / `run_python` / `write_report` tools, sandboxed to a task's `files`. Owns `runner.py` (`run_agent`, streams trajectory JSONL), `tools.py`, `prompts.py` (`HONEST`, `INCENTIVIZED`).

See the `agent/` section of [ARCHITECTURE.md](../ARCHITECTURE.md) for the spec and schemas.

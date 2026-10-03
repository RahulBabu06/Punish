# `agent/`

Subject agent: Claude (extended thinking) with `read_file` / `run_python` / `write_report` tools, sandboxed to a task's `files`, streaming a trajectory JSONL that follows the schema in [ARCHITECTURE.md](../ARCHITECTURE.md).

## Usage

```bash
export ANTHROPIC_API_KEY=...
python -m agent.runner --task leaked_answer --config incentivized [--episode 0] [--out PATH] [--model M] [--max-turns 20]
# -> results/trajectories/leaked_answer__incentivized__ep000.jsonl
```

```python
from agent.runner import run_agent
run_agent(task, "honest", "results/trajectories/leaked_answer__honest__ep000.jsonl",
          model=None, client=None, max_turns=20)   # returns out_path
```

- `model` defaults to `$PUNISH_AGENT_MODEL`, then `claude-sonnet-4-6`.
- `client` is any object with `.messages.create(**kwargs)` (defaults to `anthropic.Anthropic()`, created lazily), so tests can inject fakes.
- `thinking_budget` (default 8000) and `max_tokens` (default 16000, must be greater than the budget) are optional keyword arguments.

## Modules

- `tools.py`: `Sandbox(files, timeout=30)` context manager. It materialises `task["files"]` into a fresh temp dir and deletes it on exit.
  - `read_file(path)` / `write_report(path, content)` reject absolute paths, `~`, and anything that resolves outside the sandbox (including via symlinks). They return error strings instead of raising.
  - `run_python(code, timeout=None) -> (output, exit_code)` runs `sys.executable -` in a new process group with cwd = sandbox. stderr is merged into stdout and output is truncated to 20k chars. A timeout kills the process group and returns exit code `124`. Env vars starting with `ANTHROPIC_`/`MODAL_`/`AWS_`/... are stripped.
  - `execute(name, args)` dispatches a tool call. `TOOL_SCHEMAS` holds the Anthropic tool definitions.
  - `run_python` is not an OS-level jail: the cwd is the sandbox, but the interpreter can still reach the host filesystem.
- `prompts.py`: `HONEST` and `INCENTIVIZED` templates (`{files}`, `{tools}`) and `build_system_prompt(task, agent_config)`. The tools section says which optional scientific packages (numpy/scipy/pandas/...) are importable in this environment.
- `runner.py`: `run_agent` plus the CLI.

## Trajectory mapping

| API | JSONL event |
|---|---|
| (start) | line 1 `system_prompt` with full `config`; line 2 user `message` (task prompt) |
| assistant turn | one `message`: `reasoning` = joined thinking blocks (`""` if none), `content` = joined text blocks |
| each `tool_use` block, in order | `tool_call` (`id` remapped to `tc_1`, `tc_2`, … ) then its `tool_result` (`exit_code` only for `run_python`) |
| (end) | `final_report` = content of the last `write_report` (`""` if none) |

- Each event gets a `ts` field and is flushed as soon as it happens.
- All tool results from one assistant turn go back to the API in a single user message. Thinking blocks, including signatures, are sent back unmodified.
- The loop stops when a turn has no `tool_use` or after `max_turns` API calls.
- Transient API errors (connection, 429, 5xx) are tried up to 3 times with exponential backoff.
- If the run fails anyway, `final_report` is still written, so the file stays a valid trajectory, and the exception is re-raised.

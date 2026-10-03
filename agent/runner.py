"""Subject-agent loop: Claude + sandboxed tools, streaming a trajectory JSONL.

CLI: python -m agent.runner --task leaked_answer --config incentivized [--episode 0] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.prompts import build_system_prompt
from agent.tools import TOOL_ARGS, TOOL_SCHEMAS, Sandbox

DEFAULT_MODEL = "claude-sonnet-4-6"
THINKING_BUDGET = 8000
MAX_TOKENS = 16000
API_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0
SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parent.parent

_sleep = time.sleep  # patched in tests


def default_model() -> str:
    return os.environ.get("PUNISH_AGENT_MODEL") or DEFAULT_MODEL


def episode_id(task_id: str, agent_config: str, episode_idx: int) -> str:
    return f"{task_id}__{agent_config}__ep{episode_idx:03d}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TrajectoryWriter:
    """Appends one JSON event per line, flushing after each write."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")
        self.n_lines = 0

    def write(self, event_type: str, **fields) -> dict:
        event = {"type": event_type, "ts": _now(), **fields}
        self._fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._fh.flush()
        self.n_lines += 1
        return event

    def close(self) -> None:
        self._fh.close()


# -- Anthropic response helpers ---------------------------------------------

def _get(block, key, default=None):
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _block_to_param(block) -> dict:
    """Convert a response content block to a request param, preserving thinking signatures."""
    btype = _get(block, "type")
    if btype == "thinking":
        return {"type": "thinking", "thinking": _get(block, "thinking"), "signature": _get(block, "signature")}
    if btype == "redacted_thinking":
        return {"type": "redacted_thinking", "data": _get(block, "data")}
    if btype == "text":
        return {"type": "text", "text": _get(block, "text")}
    if btype == "tool_use":
        return {"type": "tool_use", "id": _get(block, "id"), "name": _get(block, "name"), "input": _get(block, "input")}
    if isinstance(block, dict):
        return dict(block)
    return block.model_dump(exclude_none=True)


def _is_retryable(exc: Exception) -> bool:
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return False
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        status = getattr(exc, "status_code", 0) or 0
        return status in (408, 409, 429) or status >= 500
    return False


def _create_with_retry(client, **kwargs):
    for attempt in range(1, API_ATTEMPTS + 1):
        try:
            return client.messages.create(**kwargs)
        except Exception as exc:
            if attempt == API_ATTEMPTS or not _is_retryable(exc):
                raise
            _sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
    raise AssertionError("unreachable")


def _make_client():
    import anthropic

    return anthropic.Anthropic()


def _logged_args(name: str, args: dict) -> dict:
    """Args exactly as the contract expects (required keys only, in order)."""
    args = args if isinstance(args, dict) else {}
    return {k: args.get(k, "") for k in TOOL_ARGS[name]}


# -- main loop ----------------------------------------------------------------

def run_agent(
    task: dict,
    agent_config: str,
    out_path: str,
    model: str | None = None,
    client=None,
    max_turns: int = 20,
    thinking_budget: int = THINKING_BUDGET,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Run the subject agent on ``task``, streaming the trajectory to ``out_path``. Returns ``out_path``."""
    if agent_config not in ("honest", "incentivized"):
        raise ValueError(f"agent_config must be 'honest' or 'incentivized', got {agent_config!r}")
    if max_tokens <= thinking_budget:
        raise ValueError("max_tokens must be greater than thinking_budget")
    model = model or default_model()
    system_prompt = build_system_prompt(task, agent_config)
    config = {
        "schema_version": SCHEMA_VERSION,
        "trajectory_id": Path(out_path).stem,
        "task_id": task["id"],
        "agent_config": agent_config,
        "incentivized": agent_config == "incentivized",
        "model": model,
    }

    writer = TrajectoryWriter(out_path)
    with Sandbox(task["files"]) as sandbox:
        try:
            writer.write("system_prompt", text=system_prompt, config=config)
            writer.write("message", role="user", reasoning=None, content=task["prompt"])
            if client is None:
                client = _make_client()
            _loop(client, model, system_prompt, task["prompt"], sandbox, writer, max_turns, thinking_budget, max_tokens)
        finally:
            writer.write("final_report", text=sandbox.last_report or "")
            writer.close()
    return out_path


def _loop(client, model, system_prompt, user_prompt, sandbox, writer, max_turns, thinking_budget, max_tokens):
    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    tc_counter = 0
    for _ in range(max_turns):
        response = _create_with_retry(
            client,
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
            tools=TOOL_SCHEMAS,
            thinking={"type": "enabled", "budget_tokens": thinking_budget},
        )
        blocks = list(_get(response, "content", None) or [])
        reasoning, texts, tool_uses = [], [], []
        for block in blocks:
            btype = _get(block, "type")
            if btype == "thinking":
                reasoning.append(_get(block, "thinking") or "")
            elif btype == "redacted_thinking":
                reasoning.append("[redacted thinking]")
            elif btype == "text":
                texts.append(_get(block, "text") or "")
            elif btype == "tool_use":
                tool_uses.append(block)
        writer.write(
            "message",
            role="assistant",
            reasoning="\n\n".join(r for r in reasoning if r),
            content="\n\n".join(t for t in texts if t),
        )
        messages.append({"role": "assistant", "content": [_block_to_param(b) for b in blocks]})

        if not tool_uses:
            break

        results = []
        for block in tool_uses:
            api_id, name, args = _get(block, "id"), _get(block, "name"), _get(block, "input") or {}
            if name not in TOOL_ARGS:
                results.append({"type": "tool_result", "tool_use_id": api_id, "is_error": True,
                                "content": f"Error: unknown tool {name!r}"})
                continue
            tc_counter += 1
            tc_id = f"tc_{tc_counter}"
            writer.write("tool_call", id=tc_id, name=name, args=_logged_args(name, args))
            output, exit_code = sandbox.execute(name, args)
            if name == "run_python":
                writer.write("tool_result", id=tc_id, output=output, exit_code=exit_code)
                model_text = f"{output}\n[exit code: {exit_code}]"
            else:
                writer.write("tool_result", id=tc_id, output=output)
                model_text = output
            results.append({"type": "tool_result", "tool_use_id": api_id, "content": model_text or "(no output)"})
        messages.append({"role": "user", "content": results})


# -- CLI ------------------------------------------------------------------------

def load_task(task_id: str) -> dict:
    try:
        from tasks.registry import load_task as registry_load_task
    except ImportError:
        path = REPO_ROOT / "tasks" / "definitions" / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))
    return registry_load_task(task_id)


def main(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(description="Run the Punish subject agent on one task.")
    parser.add_argument("--task", required=True, help="task_id, e.g. leaked_answer")
    parser.add_argument("--config", required=True, choices=["honest", "incentivized"])
    parser.add_argument("--episode", type=int, default=0)
    parser.add_argument("--out", default=None, help="trajectory path (default results/trajectories/<episode_id>.jsonl)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-turns", type=int, default=20)
    args = parser.parse_args(argv)

    task = load_task(args.task)
    out = args.out or str(Path("results") / "trajectories" / f"{episode_id(args.task, args.config, args.episode)}.jsonl")
    path = run_agent(task, args.config, out, model=args.model, max_turns=args.max_turns)
    print(path)
    return path


if __name__ == "__main__":
    main()

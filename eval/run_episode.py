"""Run one episode: task -> agent trajectory -> ground-truth label -> auditor verdict -> Episode result.

File naming under ``results_dir`` (default ``results/``)::

    trajectories/<episode_id>.jsonl          one per agent run, shared by every audit of it
    verdicts/<episode_id><suffix>.json
    episodes/<episode_id><suffix>.json

``<suffix>`` keeps audits of the same trajectory from colliding:

    full_trace  + claude     ->  ""                         (the ARCHITECTURE.md default path)
    report_only + claude     ->  "__report_only"
    full_trace  + heuristic  ->  "__heuristic"
    report_only + heuristic  ->  "__report_only__heuristic"

The ``episode_id`` field inside the JSON is always the canonical ``<task_id>__<agent_config>__epNNN``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

AGENT_CONFIGS = ("honest", "incentivized", "pressure", "covert", "covert_monitored", "sycophantic_pi")
AUDITOR_MODES = ("full_trace", "report_only", "final_report")
AUDITOR_BACKENDS = ("claude", "heuristic")
VERDICT_KEYS = ("trajectory_id", "auditor_mode", "hack_detected", "hack_types", "evidence", "confidence", "auditor_notes")


def make_episode_id(task_id: str, agent_config: str, episode_idx: int) -> str:
    return f"{task_id}__{agent_config}__ep{episode_idx:03d}"


def output_suffix(auditor_mode: str = "full_trace", auditor_backend: str = "claude") -> str:
    suffix = "" if auditor_mode == "full_trace" else f"__{auditor_mode}"
    if auditor_backend != "claude":
        suffix += f"__{auditor_backend}"
    return suffix


def trajectory_path_for(episode_id: str, results_dir: str = "results") -> str:
    return os.path.join(results_dir, "trajectories", f"{episode_id}.jsonl")


def verdict_path_for(episode_id: str, auditor_mode: str = "full_trace", auditor_backend: str = "claude",
                     results_dir: str = "results") -> str:
    return os.path.join(results_dir, "verdicts", f"{episode_id}{output_suffix(auditor_mode, auditor_backend)}.json")


def episode_path_for(episode_id: str, auditor_mode: str = "full_trace", auditor_backend: str = "claude",
                     results_dir: str = "results") -> str:
    return os.path.join(results_dir, "episodes", f"{episode_id}{output_suffix(auditor_mode, auditor_backend)}.json")


def read_events(trajectory_path: str) -> list[dict]:
    with open(trajectory_path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path: str, obj: dict) -> str:
    """Atomically write ``obj`` as JSON (readers such as the demo never see a half-written file)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return path


def _check_choice(name: str, value: str, choices: tuple[str, ...]) -> None:
    if value not in choices:
        raise ValueError(f"{name} must be one of {choices}, got {value!r}")


def _resolve_load_task(load_task_fn: Callable | None) -> Callable:
    if load_task_fn is not None:
        return load_task_fn
    from tasks.registry import load_task

    return load_task


def _resolve_label(label_fn: Callable | None) -> Callable:
    if label_fn is not None:
        return label_fn
    from tasks.registry import label

    return label


def _resolve_run_agent(run_agent_fn: Callable | None) -> Callable:
    if run_agent_fn is not None:
        return run_agent_fn
    from agent.runner import run_agent

    return run_agent


def _resolve_audit(audit_fn: Callable | None, auditor_backend: str) -> Callable:
    if audit_fn is not None:
        return audit_fn
    if auditor_backend == "heuristic":
        from auditor.heuristic import heuristic_audit

        return heuristic_audit
    from auditor.audit import audit

    return audit


def _check_verdict_shape(verdict: dict, auditor_mode: str) -> None:
    missing = [k for k in VERDICT_KEYS if k not in verdict]
    if missing:
        raise ValueError(f"auditor returned a verdict missing {missing}")
    if verdict["auditor_mode"] != auditor_mode:
        raise ValueError(f"auditor returned auditor_mode={verdict['auditor_mode']!r}, expected {auditor_mode!r}")


def audit_existing(
    trajectory_path: str,
    auditor_mode: str = "full_trace",
    auditor_backend: str = "claude",
    *,
    results_dir: str = "results",
    task: dict | None = None,
    load_task_fn: Callable | None = None,
    audit_fn: Callable | None = None,
    label_fn: Callable | None = None,
    auditor_model: str | None = None,
) -> dict:
    """Audit an existing trajectory (no agent run) and write its verdict + Episode result. Returns the Episode."""
    _check_choice("auditor_mode", auditor_mode, AUDITOR_MODES)
    _check_choice("auditor_backend", auditor_backend, AUDITOR_BACKENDS)

    events = read_events(trajectory_path)
    if not events or events[0].get("type") != "system_prompt":
        raise ValueError(f"{trajectory_path}: line 1 must be the system_prompt event")
    config = events[0]["config"]
    episode_id = config["trajectory_id"]
    if task is None:
        task = _resolve_load_task(load_task_fn)(config["task_id"])

    ground_truth_hacked = bool(_resolve_label(label_fn)(task, events))

    audit = _resolve_audit(audit_fn, auditor_backend)
    kwargs = {"mode": auditor_mode}
    if auditor_model is not None and auditor_backend == "claude":
        kwargs["model"] = auditor_model
    verdict = audit(trajectory_path, **kwargs)
    _check_verdict_shape(verdict, auditor_mode)
    write_json(verdict_path_for(episode_id, auditor_mode, auditor_backend, results_dir), verdict)

    episode = {
        "episode_id": episode_id,
        "task_id": config["task_id"],
        "agent_config": config["agent_config"],
        "auditor_mode": auditor_mode,
        "ground_truth_hacked": ground_truth_hacked,
        "verdict": verdict,
        "correct": bool(verdict["hack_detected"]) == ground_truth_hacked,
        "trajectory_path": str(trajectory_path),
        "auditor_backend": auditor_backend,
    }
    write_json(episode_path_for(episode_id, auditor_mode, auditor_backend, results_dir), episode)
    return episode


def run_agent_step(
    task: dict,
    agent_config: str,
    episode_idx: int,
    *,
    results_dir: str = "results",
    run_agent_fn: Callable | None = None,
    agent_model: str | None = None,
) -> str:
    """Run the subject agent and return the trajectory path."""
    _check_choice("agent_config", agent_config, AGENT_CONFIGS)
    out_path = trajectory_path_for(make_episode_id(task["id"], agent_config, episode_idx), results_dir)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    kwargs = {} if agent_model is None else {"model": agent_model}
    return _resolve_run_agent(run_agent_fn)(task, agent_config, out_path, **kwargs) or out_path


def run_episode_modes(
    task_id: str,
    agent_config: str,
    episode_idx: int,
    auditor_modes: list[str] | tuple[str, ...] = ("full_trace",),
    auditor_backend: str = "claude",
    *,
    results_dir: str = "results",
    load_task_fn: Callable | None = None,
    run_agent_fn: Callable | None = None,
    audit_fn: Callable | None = None,
    label_fn: Callable | None = None,
    agent_model: str | None = None,
    auditor_model: str | None = None,
) -> list[dict]:
    """Run the agent once, then audit the trajectory in each of ``auditor_modes``. Returns one Episode per mode."""
    for mode in auditor_modes:
        _check_choice("auditor_mode", mode, AUDITOR_MODES)
    _check_choice("auditor_backend", auditor_backend, AUDITOR_BACKENDS)
    task = _resolve_load_task(load_task_fn)(task_id)
    trajectory_path = run_agent_step(task, agent_config, episode_idx, results_dir=results_dir,
                                     run_agent_fn=run_agent_fn, agent_model=agent_model)
    return [
        audit_existing(trajectory_path, mode, auditor_backend, results_dir=results_dir, task=task,
                       audit_fn=audit_fn, label_fn=label_fn, auditor_model=auditor_model)
        for mode in auditor_modes
    ]


def run_episode(
    task_id: str,
    agent_config: str,
    episode_idx: int,
    auditor_mode: str = "full_trace",
    auditor_backend: str = "claude",
    *,
    results_dir: str = "results",
    load_task_fn: Callable | None = None,
    run_agent_fn: Callable | None = None,
    audit_fn: Callable | None = None,
    label_fn: Callable | None = None,
    agent_model: str | None = None,
    auditor_model: str | None = None,
) -> dict:
    """Single episode: load task, run agent, label, audit, write trajectory/verdict/episode. Returns the Episode."""
    return run_episode_modes(
        task_id, agent_config, episode_idx, [auditor_mode], auditor_backend,
        results_dir=results_dir, load_task_fn=load_task_fn, run_agent_fn=run_agent_fn, audit_fn=audit_fn,
        label_fn=label_fn, agent_model=agent_model, auditor_model=auditor_model,
    )[0]


def parse_modes(value: str) -> list[str]:
    if value == "both":
        return ["full_trace", "report_only"]
    if value == "all":
        return list(AUDITOR_MODES)
    return [m.strip() for m in value.split(",") if m.strip()]


def _summary_line(ep: dict) -> str:
    v = ep["verdict"]
    return (f"{ep['episode_id']} [{ep['auditor_mode']}/{ep.get('auditor_backend', 'claude')}] "
            f"ground_truth_hacked={ep['ground_truth_hacked']} hack_detected={v['hack_detected']} "
            f"confidence={v['confidence']:.2f} hack_types={v['hack_types']} correct={ep['correct']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run one episode (or re-audit an existing trajectory).")
    p.add_argument("--task", help="task_id, e.g. leaked_answer")
    p.add_argument("--config", choices=AGENT_CONFIGS, default="incentivized")
    p.add_argument("--episode", type=int, default=0)
    p.add_argument("--auditor-mode", default="full_trace", choices=[*AUDITOR_MODES, "both", "all"])
    p.add_argument("--auditor-backend", default="claude", choices=AUDITOR_BACKENDS)
    p.add_argument("--results-dir", default="results")
    p.add_argument("--trajectory", help="re-audit this existing trajectory instead of running the agent")
    args = p.parse_args(argv)

    if args.trajectory and not Path(args.trajectory).is_file():
        p.error(f"no such trajectory: {args.trajectory}")
    modes = parse_modes(args.auditor_mode)
    if args.trajectory:
        episodes = [audit_existing(args.trajectory, m, args.auditor_backend, results_dir=args.results_dir)
                    for m in modes]
    elif args.task:
        episodes = run_episode_modes(args.task, args.config, args.episode, modes, args.auditor_backend,
                                     results_dir=args.results_dir)
    else:
        p.error("one of --task or --trajectory is required")
    for ep in episodes:
        print(_summary_line(ep))
    return 0


if __name__ == "__main__":
    sys.exit(main())

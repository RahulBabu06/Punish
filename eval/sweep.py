"""Batch sweep over tasks x agent_configs x episodes, auditing each trajectory in every auditor mode.

Modal (remote, parallel):   modal run eval/sweep.py --n-episodes 5
Local fallback (threads):   python -m eval.sweep --local --n-episodes 1

Both write trajectories, verdicts and episodes under results/ (see eval/run_episode.py for file naming),
then compute metrics and write results/SUMMARY.md.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if (_REPO_ROOT / "eval" / "__init__.py").exists() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import modal  # noqa: E402

LOCAL_PACKAGES = ("tasks", "agent", "auditor", "eval")
JOB_TIMEOUT_S = 30 * 60

app = modal.App("punish-sweep")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("anthropic", "numpy", "scipy", "pandas")
    # Default ignore drops non-.py files; we need tasks/definitions/*.json in the container.
    .add_local_python_source(*LOCAL_PACKAGES, ignore=["**/__pycache__/**", "**/*.pyc"])
)


def split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def resolve_tasks(tasks: str = "all") -> list[str]:
    if tasks != "all":
        return split_csv(tasks)
    try:
        from tasks.registry import list_tasks

        return list(list_tasks())
    except Exception:
        return sorted(p.stem for p in (_REPO_ROOT / "tasks" / "definitions").glob("*.json"))


def build_grid(task_ids: list[str], configs: list[str], n_episodes: int,
               auditor_modes: list[str]) -> list[tuple[str, str, int, list[str]]]:
    """One job per agent run: (task_id, agent_config, episode_idx, auditor_modes)."""
    return [(t, c, i, list(auditor_modes)) for t in task_ids for c in configs for i in range(n_episodes)]


def _run_job_local(task_id: str, agent_config: str, episode_idx: int, auditor_modes: list[str],
                   auditor_backend: str = "claude", results_dir: str = "results",
                   agent_model: str | None = None, auditor_model: str | None = None) -> list[dict]:
    from eval.run_episode import run_episode_modes

    return run_episode_modes(task_id, agent_config, episode_idx, auditor_modes, auditor_backend,
                             results_dir=results_dir, agent_model=agent_model, auditor_model=auditor_model)


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic")], timeout=JOB_TIMEOUT_S,
              retries=modal.Retries(max_retries=2, initial_delay=5.0, backoff_coefficient=2.0))
def episode_job(task_id: str, agent_config: str, episode_idx: int, auditor_modes: list[str],
                auditor_backend: str = "claude", agent_model: str | None = None,
                auditor_model: str | None = None, fault_rate: float = 0.0) -> list[dict]:
    """Run the agent once, audit in each mode. Returns one record per mode:
    ``{"episode": <Episode>, "files": {<results-relative path>: <text>}}`` so the caller can mirror the files."""
    os.environ["PUNISH_FAULT_RATE"] = str(fault_rate)  # read by agent.runner (tool-failure injection)
    with tempfile.TemporaryDirectory() as work:
        cwd = os.getcwd()
        os.chdir(work)  # keeps the episodes' trajectory_path repo-relative ("results/trajectories/...")
        try:
            episodes = _run_job_local(task_id, agent_config, episode_idx, auditor_modes, auditor_backend,
                                      "results", agent_model, auditor_model)
            files = {str(p.relative_to("results")): p.read_text(encoding="utf-8")
                     for p in Path("results").rglob("*") if p.is_file()}
        finally:
            os.chdir(cwd)
    return [{"episode": ep, "files": files if i == 0 else {}} for i, ep in enumerate(episodes)]


def write_records(records: list[dict], results_dir: str = "results") -> list[dict]:
    episodes = []
    for rec in records:
        for rel, text in rec["files"].items():
            path = Path(results_dir) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        episodes.append(rec["episode"])
    return episodes


def finish(episodes: list[dict], failures: list[str], results_dir: str = "results") -> str:
    from eval.metrics import compute_metrics, write_summary

    summary = write_summary(compute_metrics(episodes), os.path.join(results_dir, "SUMMARY.md"))
    print(f"{len(episodes)} episodes written under {results_dir}/, {len(failures)} failed jobs -> {summary}")
    for f in failures:
        print(f"  FAILED: {f}")
    return summary


def _models() -> tuple[str | None, str | None]:
    return os.environ.get("PUNISH_AGENT_MODEL"), os.environ.get("PUNISH_AUDITOR_MODEL")


@app.local_entrypoint()
def main(n_episodes: int = 5, tasks: str = "all", configs: str = "honest,incentivized",
         auditor_modes: str = "full_trace,report_only", auditor_backend: str = "claude",
         results_dir: str = "results", agent_model: str = "", auditor_model: str = "", start_episode: int = 0,
         fault_rate: float = 0.0):
    grid = build_grid(resolve_tasks(tasks), split_csv(configs), n_episodes, split_csv(auditor_modes))
    if start_episode:
        grid = [(t, c, i + start_episode, m) for t, c, i, m in grid]
    env_agent, env_auditor = _models()
    agent_model, auditor_model = agent_model or env_agent, auditor_model or env_auditor
    print(f"Launching {len(grid)} episode jobs on Modal")
    episodes, failures = [], []
    args = [(*job, auditor_backend, agent_model, auditor_model, fault_rate) for job in grid]
    for job, result in zip(grid, episode_job.starmap(args, return_exceptions=True)):
        if isinstance(result, BaseException):
            failures.append(f"{job[:3]}: {result!r}")
        else:
            episodes += write_records(result, results_dir)
    finish(episodes, failures, results_dir)


def run_local(n_episodes: int = 1, tasks: str = "all", configs: str = "honest,incentivized",
              auditor_modes: str = "full_trace,report_only", auditor_backend: str = "claude",
              results_dir: str = "results", max_workers: int = 8, job_fn=None) -> list[dict]:
    """Non-Modal fallback: same grid, run in a local thread pool. ``job_fn`` is injectable for tests."""
    job_fn = job_fn or _run_job_local
    grid = build_grid(resolve_tasks(tasks), split_csv(configs), n_episodes, split_csv(auditor_modes))
    agent_model, auditor_model = _models()
    episodes, failures = [], []
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = [(job, pool.submit(job_fn, *job, auditor_backend, results_dir, agent_model, auditor_model))
                   for job in grid]
        for job, fut in futures:
            try:
                episodes += fut.result()
            except Exception:
                failures.append(f"{job[:3]}: {traceback.format_exc(limit=1).strip()}")
    finish(episodes, failures, results_dir)
    return episodes


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the sweep locally (use `modal run eval/sweep.py` for Modal).")
    p.add_argument("--local", action="store_true", help="run in a local thread pool instead of Modal")
    p.add_argument("--n-episodes", type=int, default=1)
    p.add_argument("--tasks", default="all")
    p.add_argument("--configs", default="honest,incentivized")
    p.add_argument("--auditor-modes", default="full_trace,report_only")
    p.add_argument("--auditor-backend", default="claude", choices=["claude", "heuristic"])
    p.add_argument("--results-dir", default="results")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args(argv)
    if not args.local:
        p.error("for Modal use `modal run eval/sweep.py --n-episodes N`; pass --local to run here")
    run_local(args.n_episodes, args.tasks, args.configs, args.auditor_modes, args.auditor_backend,
              args.results_dir, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())

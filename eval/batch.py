"""Post-hoc batch jobs over an existing results directory, on Modal (parallel) or locally.

  modal run eval/batch.py --results-dir results/v2_sonnet46 --job judge
  modal run eval/batch.py --results-dir results/v2_sonnet46 --job reaudit --auditor-model claude-opus-4-6 \
      --auditor-modes full_trace,report_only,final_report --out-dir results/v2_sonnet46/reaudit_claude-opus-4-6
  python -m eval.batch --local --results-dir ... --job judge

judge   -> <results-dir>/judgments/<trajectory_id>.json (privileged ground truth, eval/judge.py)
reaudit -> <out-dir>/{verdicts,episodes}/... with another auditor model (Episode trajectory_path
           still points at <results-dir>/trajectories/...)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import modal  # noqa: E402

app = modal.App("punish-batch")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("anthropic", "numpy", "scipy", "pandas")
    .add_local_python_source("tasks", "agent", "auditor", "eval", ignore=["**/__pycache__/**", "**/*.pyc"])
)


def judge_task_for_text(trajectory_text: str) -> dict:
    """Task definition matching the trajectory's sandbox files. Resolved locally: it needs the git history of
    tasks/definitions, which the Modal image does not have."""
    from eval.judge import task_for_events

    events = [json.loads(line) for line in trajectory_text.splitlines() if line.strip()]
    return task_for_events(events)[1]


def _judge_text(trajectory_text: str, model: str | None, task: dict | None = None) -> dict:
    from eval.judge import judge

    if task is None:
        task = judge_task_for_text(trajectory_text)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write(trajectory_text)
        path = f.name
    try:
        return judge(path, task, model=model)
    finally:
        os.unlink(path)


def _reaudit_text(trajectory_text: str, trajectory_path: str, modes: list[str], model: str | None,
                  auditor: str = "claude", n_samples: int = 1) -> list[dict]:
    from auditor.audit import _check_samples, audit
    from eval.run_episode import audit_existing

    _check_samples(n_samples)
    if auditor not in ("claude", "agentic"):
        raise ValueError("auditor must be claude or agentic")
    backend = audit
    if auditor == "agentic":
        from auditor.agentic import audit_agentic

        backend = audit_agentic
    audit_fn = partial(backend, n_samples=n_samples) if auditor == "agentic" or n_samples != 1 else None
    out = []
    with tempfile.TemporaryDirectory() as work:
        path = os.path.join(work, os.path.basename(trajectory_path))
        Path(path).write_text(trajectory_text, encoding="utf-8")
        for mode in modes:
            ep = audit_existing(path, mode, "claude", results_dir=os.path.join(work, "out"), auditor_model=model, audit_fn=audit_fn)
            ep["trajectory_path"] = trajectory_path
            ep["auditor_backend"] = auditor
            ep["auditor_model"] = model
            out.append(ep)
    return out


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic")], timeout=900,
              retries=modal.Retries(max_retries=2, initial_delay=5.0))
def judge_job(trajectory_text: str, model: str | None = None, task: dict | None = None) -> dict:
    return _judge_text(trajectory_text, model, task)


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic")], timeout=1800,
              retries=modal.Retries(max_retries=2, initial_delay=5.0))
def reaudit_job(trajectory_text: str, trajectory_path: str, modes: list[str], model: str | None = None,
                auditor: str = "claude", n_samples: int = 1) -> list[dict]:
    return _reaudit_text(trajectory_text, trajectory_path, modes, model, auditor, n_samples)


def _trajectories(results_dir: str) -> list[Path]:
    return sorted(Path(results_dir, "trajectories").glob("*.jsonl"))


def _write(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _print_usage(job: str, usages: list[dict]) -> None:
    """Print the summed API token usage (the optional ``usage`` field) of a batch job's outputs."""
    totals: dict[str, dict[str, int]] = {}
    for u in usages:
        if not isinstance(u, dict):
            continue
        t = totals.setdefault(str(u.get("model", "?")), {"calls": 0})
        t["calls"] += 1
        for k, v in u.items():
            if k != "model" and isinstance(v, int):
                t[k] = t.get(k, 0) + v
    for model, t in sorted(totals.items()):
        print(f"{job} usage {model}: " + ", ".join(f"{k}={v}" for k, v in t.items()))


def _save_judgments(results_dir: str, paths: list[Path], results) -> int:
    from eval.judge import judgment_path_for

    failed = 0
    for p, r in zip(paths, results):
        if isinstance(r, BaseException):
            failed += 1
            print(f"FAILED judge {p.name}: {r!r}")
            continue
        _write(judgment_path_for(results_dir, r["trajectory_id"] or p.stem), r)
    _print_usage("judge", [r.get("usage") for r in results if isinstance(r, dict)])
    return failed


def _save_reaudits(out_dir: str, paths: list[Path], results) -> int:
    from eval.run_episode import episode_path_for, verdict_path_for

    failed = 0
    for p, r in zip(paths, results):
        if isinstance(r, BaseException):
            failed += 1
            print(f"FAILED reaudit {p.name}: {r!r}")
            continue
        for ep in r:
            backend = ep.get("auditor_backend", "claude")
            _write(verdict_path_for(ep["episode_id"], ep["auditor_mode"], backend, out_dir), ep["verdict"])
            _write(episode_path_for(ep["episode_id"], ep["auditor_mode"], backend, out_dir), ep)
    _print_usage("reaudit", [ep["verdict"].get("usage") for r in results if isinstance(r, list) for ep in r])
    return failed


def _pending(results_dir: str, paths: list[Path], job: str, skip_existing: bool) -> list[Path]:
    if job != "judge" or not skip_existing:
        return paths
    return [p for p in paths if not Path(results_dir, "judgments", f"{p.stem}.json").exists()]


@app.local_entrypoint()
def main(results_dir: str, job: str = "judge", judge_model: str = "", auditor_model: str = "",
         auditor_modes: str = "full_trace,report_only,final_report", out_dir: str = "", skip_existing: bool = True,
         auditor: str = "claude", n_samples: int = 1):
    if job == "reaudit":
        from auditor.audit import _check_samples

        _check_samples(n_samples)
        if auditor not in ("claude", "agentic"):
            raise ValueError("auditor must be claude or agentic")
    paths = _pending(results_dir, _trajectories(results_dir), job, skip_existing)
    print(f"{job}: {len(paths)} trajectories from {results_dir}")
    texts = [p.read_text(encoding="utf-8") for p in paths]
    if job == "judge":
        res = judge_job.starmap([(t, judge_model or None, judge_task_for_text(t)) for t in texts],
                                return_exceptions=True)
        failed = _save_judgments(results_dir, paths, list(res))
    elif job == "reaudit":
        modes = [m for m in auditor_modes.split(",") if m]
        res = reaudit_job.starmap([(t, str(p), modes, auditor_model or None, auditor, n_samples) for t, p in zip(texts, paths)],
                                  return_exceptions=True)
        failed = _save_reaudits(out_dir or os.path.join(results_dir, "reaudit"), paths, list(res))
    else:
        raise SystemExit(f"unknown job {job!r}")
    print(f"done: {len(paths) - failed} ok, {failed} failed")


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run batch jobs locally (use `modal run eval/batch.py` for Modal).")
    p.add_argument("--local", action="store_true")
    p.add_argument("--results-dir", required=True)
    p.add_argument("--job", choices=["judge", "reaudit"], default="judge")
    p.add_argument("--judge-model", default=None)
    p.add_argument("--auditor-model", default=None)
    p.add_argument("--auditor", choices=["claude", "agentic"], default="claude")
    p.add_argument("--n-samples", type=int, default=1)
    p.add_argument("--auditor-modes", default="full_trace,report_only,final_report")
    p.add_argument("--out-dir", default="")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args(argv)
    if args.n_samples < 1:
        p.error("--n-samples must be positive")
    if not args.local:
        p.error("pass --local, or use `modal run eval/batch.py ...`")
    from agent.credentials import require_anthropic

    require_anthropic(f"eval.batch --job {args.job}")
    paths = _pending(args.results_dir, _trajectories(args.results_dir), args.job, True)
    texts = [p.read_text(encoding="utf-8") for p in paths]

    def safe(fn, *a):
        try:
            return fn(*a)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return exc

    with ThreadPoolExecutor(args.workers) as pool:
        if args.job == "judge":
            res = list(pool.map(lambda t: safe(_judge_text, t, args.judge_model), texts))
            _save_judgments(args.results_dir, paths, res)
        else:
            modes = args.auditor_modes.split(",")
            res = list(pool.map(lambda tp: safe(_reaudit_text, tp[0], str(tp[1]), modes, args.auditor_model, args.auditor, args.n_samples),
                                zip(texts, paths)))
            _save_reaudits(args.out_dir or os.path.join(args.results_dir, "reaudit"), paths, res)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())

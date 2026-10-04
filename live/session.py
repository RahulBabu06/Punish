"""Live runs for the demo: a subject agent works a task while an open-weight auditor watches.

The subject is Claude (when ``ANTHROPIC_API_KEY`` is set and requested) or an open-weight model served
by ``live/vllm_server.py``. The auditor is always the open-weight model. While the trajectory streams,
the auditor re-audits the growing prefix after each tool result and writes
``results/live/interim/<id>.json``; once the final report lands it writes the usual per-mode verdicts
to ``results/live/verdicts/`` (``demo.core`` picks both up).
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from demo.core import RESULTS_DIR, mode_suffix

MODES = ("full_trace", "report_only", "final_report")
SUBJECTS = ("open", "claude")


def write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def count_tool_results(lines: list[str]) -> int:
    return sum('"type": "tool_result"' in line for line in lines)


@dataclass
class LiveRun:
    run_id: str
    task_id: str
    agent_config: str
    subject: str
    subject_model: str
    auditor_model: str
    trajectory: str
    status: str = "starting"
    error: str | None = None
    started: float = field(default_factory=time.time)
    finished: float | None = None
    interim_audits: int = 0

    def to_json(self) -> dict:
        return asdict(self)


class LiveManager:
    def __init__(self, results_dir: Path = RESULTS_DIR, open_client_factory=None, claude_client_factory=None,
                 max_active: int = 2, max_turns: int = 12, interim: bool = True, poll: float = 1.0):
        self.dir = Path(results_dir) / "live"
        self.open_client_factory = open_client_factory or _default_open_client
        self.claude_client_factory = claude_client_factory or _default_claude_client
        self.max_active, self.max_turns, self.interim, self.poll = max_active, max_turns, interim, poll
        self.runs: dict[str, LiveRun] = {}
        self._lock = threading.Lock()

    # -- public ---------------------------------------------------------------
    def subjects(self) -> list[str]:
        return [s for s in SUBJECTS if s == "open" or os.environ.get("ANTHROPIC_API_KEY")]

    def active(self) -> list[LiveRun]:
        return [r for r in self.runs.values() if r.status in {"starting", "running", "auditing"}]

    def list_runs(self) -> list[dict]:
        return [r.to_json() for r in sorted(self.runs.values(), key=lambda r: -r.started)]

    def start(self, task_id: str, agent_config: str, subject: str = "open") -> LiveRun:
        from agent.prompts import AGENT_CONFIGS
        from tasks.registry import load_task

        if agent_config not in AGENT_CONFIGS:
            raise ValueError(f"agent_config must be one of {AGENT_CONFIGS}")
        if subject not in self.subjects():
            raise ValueError(f"subject must be one of {self.subjects()}")
        task = load_task(task_id)
        open_client = self.open_client_factory()
        subject_client = open_client if subject == "open" else self.claude_client_factory()
        subject_model = open_client.model if subject == "open" else None
        with self._lock:
            if len(self.active()) >= self.max_active:
                raise RuntimeError(f"{self.max_active} live runs are already in progress; try again in a minute")
            traj_dir = self.dir / "trajectories"
            traj_dir.mkdir(parents=True, exist_ok=True)
            n = 0
            while (traj_dir / f"{task_id}__{agent_config}__ep{n:03d}.jsonl").exists() or \
                    f"{task_id}__{agent_config}__ep{n:03d}" in self.runs:
                n += 1
            run_id = f"{task_id}__{agent_config}__ep{n:03d}"
            path = traj_dir / f"{run_id}.jsonl"
            path.touch()
            from agent.runner import default_model

            run = LiveRun(run_id, task_id, agent_config, subject, subject_model or default_model(), open_client.model, str(path))
            self.runs[run_id] = run
        threading.Thread(target=self._work, args=(run, task, subject_client, open_client), daemon=True).start()
        return run

    # -- worker ---------------------------------------------------------------
    def _work(self, run: LiveRun, task: dict, subject_client, open_client) -> None:
        from agent.runner import run_agent

        stop = threading.Event()
        watcher = None
        if self.interim:
            watcher = threading.Thread(target=self._interim_loop, args=(run, open_client, stop), daemon=True)
            watcher.start()
        try:
            run.status = "running"
            kwargs = {"thinking_budget": 2048, "max_tokens": 8192} if run.subject == "open" else {}
            run_agent(task, run.agent_config, run.trajectory, model=run.subject_model, client=subject_client,
                      max_turns=self.max_turns, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced on /live
            run.error = f"subject agent failed: {type(exc).__name__}: {exc}"
            traceback.print_exc()
        finally:
            stop.set()
            if watcher is not None:
                watcher.join(timeout=5)
        run.status = "auditing"
        try:
            self._final_audits(run, open_client)
            run.status = "done" if run.error is None else "error"
        except Exception as exc:  # noqa: BLE001
            run.error = (run.error + "; " if run.error else "") + f"auditor failed: {type(exc).__name__}: {exc}"
            run.status = "error"
            traceback.print_exc()
        run.finished = time.time()

    def _audit(self, path: Path, mode: str, client) -> dict:
        from auditor.audit import audit

        verdict = audit(str(path), mode=mode, model=client.model, client=client)
        verdict["auditor_model"] = client.model
        return verdict

    def _interim_loop(self, run: LiveRun, client, stop: threading.Event) -> None:
        traj = Path(run.trajectory)
        snap = self.dir / "interim" / f"{run.run_id}.snapshot.jsonl"
        out = self.dir / "interim" / f"{run.run_id}.json"
        audited = 0
        while not stop.is_set():
            try:
                lines = [ln for ln in traj.read_text(encoding="utf-8").split("\n") if ln.strip()]
            except FileNotFoundError:
                lines = []
            n_results = count_tool_results(lines)
            if n_results > audited and not any('"type": "final_report"' in ln for ln in lines):
                audited = n_results
                snap.parent.mkdir(parents=True, exist_ok=True)
                snap.write_text("\n".join(lines) + "\n", encoding="utf-8")
                try:
                    verdict = self._audit(snap, "full_trace", client)
                except Exception as exc:  # noqa: BLE001 - interim audits are best-effort
                    print(f"[live] interim audit failed: {exc}")
                else:
                    if not stop.is_set():
                        write_json_atomic(out, {"upto_line": len(lines), "verdict": verdict})
                        run.interim_audits += 1
            stop.wait(self.poll)

    def _final_audits(self, run: LiveRun, client) -> None:
        traj = Path(run.trajectory)
        verdict_dir = self.dir / "verdicts"

        def one(mode: str):
            verdict = self._audit(traj, mode, client)
            write_json_atomic(verdict_dir / f"{run.run_id}{mode_suffix(mode)}.json", verdict)

        with ThreadPoolExecutor(len(MODES)) as pool:
            for future in [pool.submit(one, m) for m in MODES]:
                future.result()


def _default_open_client():
    from live.openai_client import OpenModelClient

    return OpenModelClient()


def _default_claude_client():
    from agent.credentials import anthropic_client

    return anthropic_client("the live Claude subject agent")

"""Derive the launch commands (and an index table) for each committed results/<exp>/ directory.

Everything is read from the committed files: the trajectory ``config`` header (subject model, agent config,
task, fault rate), the episode ids (n), verdict file suffixes (auditor modes), judgments/ and reaudit_*/.

    python scripts/sweep_commands.py                 # Modal commands for every results dir
    python scripts/sweep_commands.py --index         # markdown index table (used for results/README.md)
    python scripts/sweep_commands.py --index --cost-json cost.json   # + estimated USD (eval.cost --by-dir --json)
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.prompts import AGENT_CONFIGS  # noqa: E402
from tasks.registry import list_tasks  # noqa: E402

MODES = ("full_trace", "report_only", "final_report")
MODE_RE = re.compile(r"__(" + "|".join(MODES) + r")$")
EP_RE = re.compile(r"__ep(\d+)$")
DEFAULT_AUDITOR = "claude-sonnet-4-6"  # auditor.audit default; the original audits do not record their model


@dataclass
class Exp:
    path: Path
    models: Counter = field(default_factory=Counter)
    configs: Counter = field(default_factory=Counter)
    tasks: Counter = field(default_factory=Counter)
    fault_rates: Counter = field(default_factory=Counter)
    episodes: set = field(default_factory=set)
    modes: Counter = field(default_factory=Counter)
    n_trajectories: int = 0
    n_judgments: int = 0
    reaudits: dict = field(default_factory=dict)  # dir name -> Counter of modes

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_sweep(self) -> bool:
        return bool(self.episodes)

    @property
    def n(self) -> int:
        return max(self.episodes) + 1 if self.episodes else 0

    @property
    def task_list(self) -> list[str]:
        return sorted(self.tasks)

    @property
    def config_list(self) -> list[str]:
        return sorted(self.configs, key=lambda c: (AGENT_CONFIGS.index(c) if c in AGENT_CONFIGS else 99, c))

    @property
    def mode_list(self) -> list[str]:
        return [m for m in MODES if m in self.modes]

    @property
    def observed_grid(self) -> int:
        return len(self.tasks) * len(self.configs) * self.n

    @property
    def complete(self) -> bool:
        return self.n_trajectories == self.observed_grid and all(
            self.modes[m] == self.n_trajectories for m in self.mode_list)

    @property
    def launch_tasks(self) -> list[str]:
        """Tasks the sweep was launched with: observed, except partial v3* runs used the full 10-task suite."""
        if not self.complete and self.name.startswith("v3"):
            return list(list_tasks())
        return self.task_list

    @property
    def expected(self) -> int:
        return len(self.launch_tasks) * len(self.configs) * self.n

    @property
    def fault_rate(self) -> float:
        rates = [r for r in self.fault_rates if r]
        return float(rates[0]) if rates else 0.0


def _first_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.loads(fh.readline()).get("config") or {}


def _modes(verdict_dir: Path) -> Counter:
    out = Counter()
    for v in verdict_dir.glob("*.json"):
        m = MODE_RE.search(v.stem)
        out[m.group(1) if m else "full_trace"] += 1
    return out


def load(path: Path) -> Exp:
    exp = Exp(path)
    for t in sorted((path / "trajectories").glob("*.jsonl")):
        cfg = _first_config(t)
        exp.n_trajectories += 1
        exp.models[cfg.get("model")] += 1
        exp.configs[cfg.get("agent_config")] += 1
        exp.tasks[cfg.get("task_id")] += 1
        exp.fault_rates[cfg.get("fault_rate")] += 1
        m = EP_RE.search(t.stem)
        if m:
            exp.episodes.add(int(m.group(1)))
    if (path / "verdicts").is_dir():
        exp.modes = _modes(path / "verdicts")
    if (path / "judgments").is_dir():
        exp.n_judgments = len(list((path / "judgments").glob("*.json")))
    for sub in sorted(path.iterdir()):
        if sub.is_dir() and (sub / "verdicts").is_dir() and sub.name not in {"trajectories", "verdicts"}:
            exp.reaudits[sub.name] = _modes(sub / "verdicts")
    return exp


def experiments(results_dir: Path) -> list[Exp]:
    return [load(p) for p in sorted(results_dir.iterdir()) if (p / "trajectories").is_dir()]


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _cmd(*parts: str) -> str:
    return " ".join(shlex.quote(p) if p and not p.startswith("--") else p for p in parts)


def commands(exp: Exp) -> list[str]:
    d = _rel(exp.path)
    lines = []
    if not exp.is_sweep:
        lines.append(f"# {d}: {exp.n_trajectories} single agent runs (no audits), not a sweep")
        for t in sorted((exp.path / "trajectories").glob("*.jsonl")):
            cfg = _first_config(t)
            lines.append(_cmd(".venv/bin/python", "-m", "agent.runner", "--task", cfg["task_id"], "--config",
                              cfg["agent_config"], "--model", cfg["model"], "--out", _rel(t)))
        return lines
    models = sorted(m for m in exp.models if m)
    status = "complete" if exp.complete else f"PARTIAL {exp.n_trajectories}/{exp.expected} trajectories"
    lines.append(f"# {d}: {', '.join(models)}; {status}; judged {exp.n_judgments}/{exp.n_trajectories}")
    if not exp.complete and exp.launch_tasks != exp.task_list:
        lines.append("# (tasks inferred: the run stopped when the Anthropic credit ran out, before every task started)")
    sweep = ["modal", "run", "eval/sweep.py", "--n-episodes", str(exp.n), "--tasks", ",".join(exp.launch_tasks),
             "--configs", ",".join(exp.config_list), "--auditor-modes", ",".join(exp.mode_list)]
    for model in models:
        parts = [*sweep, "--agent-model", model]
        if exp.fault_rate:
            parts += ["--fault-rate", f"{exp.fault_rate:g}"]
        lines.append(_cmd(*parts, "--results-dir", d))
    judge = _cmd("modal", "run", "eval/batch.py", "--results-dir", d, "--job", "judge")
    lines.append(judge if exp.n_judgments else f"# not run yet: {judge}")
    for sub, modes in exp.reaudits.items():
        model = sub.removeprefix("reaudit_")
        lines.append(_cmd("modal", "run", "eval/batch.py", "--results-dir", d, "--job", "reaudit", "--auditor-model",
                          model, "--auditor-modes", ",".join(m for m in MODES if m in modes), "--out-dir",
                          f"{d}/{sub}"))
    return lines


def _short(model: str) -> str:
    return re.sub(r"^claude-|-\d{8}$", "", model or "")


def index(exps: list[Exp], cost: dict[str, float] | None = None) -> str:
    head = ["dir", "subject model", "agent configs", "tasks", "n", "auditor modes", "judged", "trajectories",
            "status"]
    if cost is not None:
        head.append("est. cost")
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for e in exps:
        models = ", ".join(_short(m) for m in sorted(m for m in e.models if m))
        if e.is_sweep:
            n, status = str(e.n), ("complete" if e.complete else "partial")
            got = f"{e.n_trajectories}/{e.expected}"
            tasks = f"{len(e.launch_tasks)}" if e.complete else f"{len(e.task_list)} of {len(e.launch_tasks)}"
        else:
            n, status, got, tasks = "1 per model", "complete", str(e.n_trajectories), ", ".join(e.task_list)
        modes = ", ".join(e.mode_list) or "none"
        for sub, m in e.reaudits.items():
            modes += f"; {sub}: {len(m)} modes"
        judged = f"{e.n_judgments}/{e.n_trajectories}" if e.n_judgments else "no"
        fault = f" (fault rate {e.fault_rate:g})" if e.fault_rate else ""
        row = [f"`{e.name}/`", models, ", ".join(e.config_list) + fault, tasks, n, modes, judged, got, status]
        if cost is not None:
            row.append(f"${cost.get(e.name, 0.0):,.2f}")
        rows.append("| " + " | ".join(row) + " |")
    return "\n".join(rows)


def _cost_by_dir(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in json.loads(path.read_text(encoding="utf-8")):
        name = Path(row["results_dir"]).name
        out[name] = out.get(name, 0.0) + row["usd"]
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("results_dirs", nargs="*", help="results/<exp> dirs (default: every results/*/trajectories)")
    p.add_argument("--results-root", default=str(ROOT / "results"))
    p.add_argument("--index", action="store_true", help="print the markdown index table instead of commands")
    p.add_argument("--cost-json", help="`python -m eval.cost --by-dir --json` output, adds an est. cost column")
    args = p.parse_args(argv)
    exps = [load(Path(d)) for d in args.results_dirs] or experiments(Path(args.results_root))
    if args.index:
        print(index(exps, _cost_by_dir(Path(args.cost_json)) if args.cost_json else None))
    else:
        print("\n\n".join("\n".join(commands(e)) for e in exps))
    return 0


if __name__ == "__main__":
    sys.exit(main())

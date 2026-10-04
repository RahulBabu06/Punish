"""Offline-first, prioritized Modal launch plan. Default: no writes and no API calls."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.cost import TOKEN_KEYS, agent_records, canonical_model, usd  # noqa: E402

SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-6"
HAIKU = "claude-haiku-4-5-20251001"
MODES = ("full_trace", "report_only", "final_report")
V2_TASKS = ("cherry_pick", "fabrication", "fake_citation", "leaked_answer", "metric_gaming", "metric_swap")
V3_TASKS = tuple(sorted((*V2_TASKS, "effect_size_target", "missing_replication", "outcome_switching", "solutions_cache")))
CONFIGS = ("honest", "incentivized", "pressure", "covert")
SWEEPS = (
    ("v3_haiku45", HAIKU, CONFIGS, 5, 0.0),
    ("v3_sonnet46", SONNET, CONFIGS, 5, 0.0),
    ("v3_opus46", OPUS, CONFIGS, 3, 0.0),
    ("v3cond_haiku45", HAIKU, ("covert_monitored", "sycophantic_pi"), 5, 0.0),
    ("v3cond_sonnet46", SONNET, ("covert_monitored", "sycophantic_pi"), 5, 0.0),
    ("v3fault_sonnet46", SONNET, ("honest", "incentivized"), 5, 0.5),
)
V2_DIRS = ("v2_sonnet46", "v2_haiku45", "v2_sonnet45")
ORDER = ("judge-v3", "finish-v3", "judge-new-v3", "hard-cases", "monitor-attacks",
         "agentic", "retry", "rubric-v3", "rejudge-leaked")
MODULES = ("eval/batch.py", "eval/sweep.py", "eval/hard_cases.py", "eval/monitor_attacks.py", "eval/mitigate.py")


def complete(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        if path.suffix == ".jsonl":
            events = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
            return bool(events and events[-1].get("type") == "final_report")
        obj = json.loads(path.read_text())
        if path.parent.name == "mitigation":
            return bool(obj.get("first") and (not obj.get("flagged") or obj.get("retry")))
        if path.parent.name == "judgments":
            return isinstance(obj.get("hacked"), bool)
        if path.parent.name == "verdicts":
            return isinstance(obj.get("hack_detected"), bool) and isinstance(obj.get("confidence"), (int, float))
        if path.parent.name == "episodes":
            return isinstance(obj.get("verdict"), dict)
        return isinstance(obj, dict) and bool(obj)
    except (ValueError, OSError, AttributeError):
        return False


@dataclass
class Rate:
    usd_per_call: float
    calls_per_episode: float = 1.0


def cost_rates(root: Path = ROOT) -> dict[tuple[str, str], Rate]:
    """Reprice eval.cost's committed token table; use agent_records for episode turn averages."""
    totals = defaultdict(lambda: [0.0, 0.0])
    for line in (root / "results/COST.md").read_text().splitlines():
        cells = [s.strip().strip("`") for s in line.strip("|").split("|")]
        if len(cells) != 10 or not cells[0].startswith("results/") or cells[1] == "agent":
            continue
        role = "auditor" if cells[1] == "reaudit" else cells[1]
        tokens = {key: int(value.replace(",", "")) for key, value in zip(TOKEN_KEYS, cells[4:8], strict=True)}
        price = usd(tokens, cells[2])
        if price is None:
            raise ValueError(f"no price for {cells[2]}")
        total = totals[role, canonical_model(cells[2])]
        total[0] += price
        total[1] += int(cells[3].replace(",", ""))
    rates = {key: Rate(cost / calls) for key, (cost, calls) in totals.items() if calls}
    agents = defaultdict(lambda: [0.0, 0, 0])
    for path in sorted((root / "results").glob("*/trajectories/*.jsonl")):
        events = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
        records = agent_records(events)
        if not records:
            continue
        model = records[0]["model"]
        agents[model][0] += sum(usd(r, model) or 0 for r in records)
        agents[model][1] += sum(r["calls"] for r in records)
        agents[model][2] += 1
    for model, (cost, calls, episodes) in agents.items():
        rates["agent", model] = Rate(cost / calls, calls / episodes)
    return rates


@dataclass
class Command:
    argv: list[str]
    outputs: list[Path]


@dataclass
class Step:
    key: str
    title: str
    commands: list[Command] = field(default_factory=list)
    calls: dict[tuple[str, str], float] = field(default_factory=lambda: defaultdict(float))
    blocked: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, module: str, args: list[str], outputs: list[Path]) -> None:
        self.commands.append(Command(["modal", "run", module, *args], outputs))

    def charge(self, role: str, model: str, calls: float) -> None:
        self.calls[role, canonical_model(model)] += calls

    def estimate(self, rates: dict) -> float:
        return sum(n * rates[k].usd_per_call for k, n in self.calls.items())


def ident(task: str, config: str, i: int) -> str:
    return f"{task}__{config}__ep{i:03d}"


def grid(configs: tuple, n: int) -> list[str]:
    return [ident(t, c, i) for t in V3_TASKS for c in configs for i in range(n)]


def audit_outputs(out: Path, tid: str, mode: str, backend: str = "claude") -> list[Path]:
    from eval.run_episode import episode_path_for, verdict_path_for

    return [Path(verdict_path_for(tid, mode, backend, str(out))),
            Path(episode_path_for(tid, mode, backend, str(out)))]


def require(step: Step, path: Path) -> None:
    if not path.exists():
        step.blocked.append(f"missing prerequisite: {path}")


def batch_audits(step: Step, source: Path, out: Path, ids: list[str], model: str,
                 modes: tuple = MODES, backend: str = "claude", rubric: bool = False) -> None:
    from eval.batch import pending_modes

    for mode in modes:
        pending = [tid for tid in ids if not all(complete(p) for p in audit_outputs(out, tid, mode, backend))
                   or pending_modes(source / "trajectories" / f"{tid}.jsonl", [mode], str(out), backend,
                                    rubric="v3" if rubric else "default")]
        if not pending:
            continue
        args = ["--results-dir", str(source), "--job", "reaudit", "--auditor-model", model,
                "--auditor-modes", mode, "--auditor", backend, "--n-samples", "1",
                "--out-dir", str(out), "--only", ",".join(pending)]
        if rubric:
            args += ["--rubric", "v3"]
        step.add("eval/batch.py", args, [p for tid in pending for p in audit_outputs(out, tid, mode, backend)])
        step.charge("auditor", model, len(pending) * (8 if backend == "agentic" else 1))


def judge_commands(step: Step, source: Path, out: Path, ids: list[str]) -> None:
    pending = [tid for tid in ids if not complete(out / "judgments" / f"{tid}.json")]
    if pending:
        step.add("eval/batch.py", ["--results-dir", str(source), "--job", "judge", "--judge-model", OPUS,
                                  "--out-dir", str(out), "--only", ",".join(pending)],
                 [out / "judgments" / f"{tid}.json" for tid in pending])
        step.charge("judge", OPUS, len(pending))


def runs(indices: list[int]) -> list[tuple[int, int]]:
    out = []
    for i in indices:
        if out and out[-1][0] + out[-1][1] == i:
            start, n = out[-1]
            out[-1] = start, n + 1
        else:
            out.append((i, 1))
    return out


def build_step(key: str, root: Path, rates: dict, flags: dict) -> Step:
    results = root / "results"
    step = Step(key, {
        "judge-v3": "Judge existing v3 trajectories",
        "finish-v3": "Finish missing v3/v3cond/v3fault/Opus episodes",
        "judge-new-v3": "Judge newly finished v3 trajectories",
        "hard-cases": "Hard cases: Sonnet + Opus, all modes",
        "monitor-attacks": "Monitor attacks: Sonnet + Opus, all modes",
        "agentic": "Agentic: 12 stratified v2 traces, two modes (8-turn proxy)",
        "retry": "Audit-and-retry: 20-episode pilot (50% retry assumption)",
        "rubric-v3": "Rubric v3: Sonnet + Opus on all v2, all modes",
        "rejudge-leaked": "Re-judge 60 v2 leaked_answer traces with matched definitions",
    }[key])
    from agent.prompts import AGENT_CONFIGS
    from tasks.registry import list_tasks

    missing_tasks = set(V3_TASKS) - set(list_tasks())
    missing_configs = {c for _, _, cs, _, _ in SWEEPS for c in cs} - set(AGENT_CONFIGS)
    if missing_tasks or missing_configs:
        step.blocked.append(f"unavailable task/config definitions: {sorted(missing_tasks | missing_configs)}")
    if key in ("judge-v3", "judge-new-v3", "finish-v3"):
        for name, model, configs, n, fault in SWEEPS:
            source = results / name
            require(step, source / "trajectories")
            observed = [p.stem for p in (source / "trajectories").glob("*.jsonl") if complete(p)]
            ids = grid(configs, n)
            if key == "judge-v3":
                judge_commands(step, source, source, observed)
            elif key == "judge-new-v3":
                # Future outputs from finish-v3 are included in the initial projected dry run.
                judge_commands(step, source, source, [tid for tid in ids if tid not in observed])
                step.notes = ["Projected follow-up; recomputed after the sweeps. Existing traces were judged in step 1."]
            else:
                for task in V3_TASKS:
                    for config in configs:
                        missing = [i for i in range(n) if not complete(source / "trajectories" / f"{ident(task, config, i)}.jsonl")]
                        for start, count in runs(missing):
                            outputs = []
                            for i in range(start, start + count):
                                tid = ident(task, config, i)
                                outputs.append(source / "trajectories" / f"{tid}.jsonl")
                                outputs += [p for mode in MODES for p in audit_outputs(source, tid, mode)]
                            step.add("eval/sweep.py", ["--tasks", task, "--configs", config, "--n-episodes", str(count),
                                     "--start-episode", str(start), "--agent-model", model, "--auditor-model", SONNET,
                                     "--auditor-modes", ",".join(MODES), "--fault-rate", str(fault), "--results-dir", str(source)], outputs)
                            step.charge("agent", model, count * rates["agent", canonical_model(model)].calls_per_episode)
                            step.charge("auditor", SONNET, count * len(MODES))
                batch_audits(step, source, source, observed, SONNET)
    elif key in ("hard-cases", "monitor-attacks"):
        folder = "hard_cases" if key == "hard-cases" else "monitor_attacks"
        cases_dir = root / "fixtures" / folder
        require(step, cases_dir)
        cases = sorted(p.stem for p in cases_dir.glob("*.jsonl") if p.with_suffix(".label.json").is_file())
        if not cases:
            step.blocked.append(f"no labelled cases in {cases_dir}")
            if key == "monitor-attacks":
                step.notes.append(f"Offline repair: python -m eval.monitor_attacks --build --cases-dir {cases_dir}")
        for model in (SONNET, OPUS):
            out = results / folder / model
            pending = [out / "verdicts" / f"{tid}__{mode}__claude.json" for tid in cases for mode in MODES
                       if not complete(out / "verdicts" / f"{tid}__{mode}__claude.json")]
            if pending:
                step.add(f"eval/{folder}.py", ["--cases-dir", str(cases_dir), "--only", ",".join(cases),
                         "--modes", "all", "--auditor-model", model, "--out", str(out)], pending)
                step.charge("auditor", model, len(pending))
        if key == "monitor-attacks":
            step.notes.append("Historical judge-positive corpus includes disputed stale leaked_answer/imputation labels; report robustness separately from label accuracy.")
    elif key == "agentic":
        source = results / "v2_sonnet46"
        ids = [ident(t, c, 0) for t in V2_TASKS for c in ("honest", "covert")]
        for tid in ids:
            require(step, source / "trajectories" / f"{tid}.jsonl")
        batch_audits(step, source, source / "reaudit_agentic_sonnet", ids, SONNET,
                     modes=("full_trace", "report_only"), backend="agentic")
        step.notes.append("At most 8 normal agentic turns per audit; standard Sonnet per-call cost is only a proxy, not a spending bound.")
    elif key == "retry":
        out = results / "mitigation_retry_live"
        for task in V3_TASKS:
            for config in ("covert", "pressure"):
                tid = ident(task, config, 0)
                record = out / "mitigation" / f"{tid}.json"
                if complete(record):
                    continue
                step.add("eval/mitigate.py", ["--experiment", "retry", "--n-episodes", "1", "--start-episode", "0",
                         "--tasks", task, "--configs", config, "--auditor-modes", ",".join(MODES), "--veto-mode", "full_trace",
                         "--retry-style", "retry", "--agent-model", SONNET, "--auditor-model", SONNET,
                         "--judge-model", OPUS, "--results-dir", str(out)], [record])
                step.charge("agent", SONNET, 1.5 * rates["agent", SONNET].calls_per_episode)
                step.charge("auditor", SONNET, 1.5 * len(MODES))
                step.charge("judge", OPUS, 1.5)
        step.notes.append("20 first attempts, one retry only if flagged; estimate assumes 50% retried. All-retried cost is 4/3 this estimate.")
    elif key in ("rubric-v3", "rejudge-leaked"):
        for name in V2_DIRS:
            source = results / name
            require(step, source / "trajectories")
            ids = sorted(p.stem for p in (source / "trajectories").glob("*.jsonl")
                         if key == "rubric-v3" or p.stem.startswith("leaked_answer__"))
            if key == "rubric-v3":
                for model in (SONNET, OPUS):
                    batch_audits(step, source, source / f"reaudit_{model}_rubric_v3", ids, model, rubric=True)
            else:
                judge_commands(step, source, source / "rejudge_matched", ids)
                # The batch resolver runs locally because Modal has no task-definition git history.
                from eval.batch import judge_task_for_text

                for tid in ids:
                    judge_task_for_text((source / "trajectories" / f"{tid}.jsonl").read_text())
        if key == "rejudge-leaked":
            step.notes.append("Matched historical task resolved by eval.judge.task_for_events; original judgments remain untouched.")
    return step


def help_flags(root: Path = ROOT) -> dict[str, set[str]]:
    flags = {}
    for module in MODULES:
        result = subprocess.run([sys.executable, "-m", "modal", "run", module, "--help"], cwd=root,
                                capture_output=True, text=True, check=True)
        flags[module] = set(re.findall(r"--[\w-]+", result.stdout + result.stderr))
    return flags


def validate_commands(steps: list[Step], flags: dict, root: Path = ROOT) -> None:
    for step in steps:
        for command in step.commands:
            module = command.argv[2]
            if not (root / module).is_file():
                step.blocked.append(f"missing module: {module}")
            missing = {a for a in command.argv[3:] if a.startswith("--")} - flags.get(module, set())
            if missing:
                step.blocked.append(f"unsupported {module} flags: {sorted(missing)}")


def render(steps: list[Step], rates: dict, running: bool = False) -> str:
    lines = ["# When credits return: prioritized live plan", "",
             ("LIVE execution requested: ready commands will launch after preflight. " if running else
              "Dry run: no Anthropic calls, deployments, or result writes. ")
             + "Costs are API-only estimates, not budget guarantees.", "",
             "| step | estimated API calls | est. USD | commands | status |", "|---|---:|---:|---:|---|"]
    for step in steps:
        lines.append(f"| {step.key}: {step.title} | {math.ceil(sum(step.calls.values()))} | ${step.estimate(rates):.2f} | "
                     f"{len(step.commands)} | {'BLOCKED' if step.blocked else 'ready' if step.commands else 'complete'} |")
    lines += [f"| **total** | **{sum(math.ceil(sum(s.calls.values())) for s in steps)}** | "
              f"**${sum(s.estimate(rates) for s in steps):.2f}** | | includes projected work |", "",
              "Cost basis: eval.cost's committed results/COST.md token rows, repriced with eval.cost.usd; agent turn/episode averages from agent_records on available trajectories.",
              "Historical estimates omit some thinking, retries, and Modal compute. Agentic uses an 8-turn standard-audit proxy; audit-and-retry assumes 50% retries."]
    for step in steps:
        lines += ["", f"## {step.key}"]
        lines += [f"- {s}" for s in (*step.blocked, *step.notes)]
        for command in step.commands:
            lines += ["", ("# BLOCKED / NOT RUN: " if step.blocked else "") + shlex.join(command.argv),
                      "# output: " + str(command.outputs[0].parent) if command.outputs else ""]
    return "\n".join(lines) + "\n"


def execute(keys: list[str], root: Path, rates: dict, flags: dict, runner=subprocess.run) -> int:
    for key in keys:
        step = build_step(key, root, rates, flags)
        # At execution time include all still-unjudged trajectories, including newly completed ones.
        if key == "judge-new-v3":
            step = build_step("judge-v3", root, rates, flags)
        validate_commands([step], flags, root)
        if step.blocked:
            print(f"BLOCKED {key}: {'; '.join(step.blocked)}", file=sys.stderr)
            return 2
        for command in step.commands:
            print(shlex.join(command.argv), flush=True)
            argv = list(command.argv)
            argv[0] = shutil.which("modal") or str(root / ".venv/bin/modal")
            result = runner(argv, cwd=root)
            if result.returncode:
                return result.returncode
            missing = [str(p) for p in command.outputs if not complete(p)]
            if missing:
                print(f"Incomplete outputs after {key}: {missing[:5]}; rerun the planner to resume.", file=sys.stderr)
                return 1
    return 0


def run_prerequisites(steps: list[Step]) -> list[str]:
    from modal.config import config

    problems = [msg for step in steps for msg in step.blocked]
    if not config.get("token_id") or not config.get("token_secret"):
        problems.append("Modal credentials not configured; authenticate Modal before --run.")
    for step in steps:
        for command in step.commands:
            for path in command.outputs:
                parent = path.parent
                while not parent.exists():
                    parent = parent.parent
                if not parent.is_dir() or not os.access(parent, os.W_OK):
                    problems.append(f"output parent is not writable: {parent}")
    return sorted(set(problems))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="default: print costs and commands only")
    mode.add_argument("--run", action="store_true", help="explicitly run the ready Modal commands")
    parser.add_argument("--steps", default=",".join(ORDER), help="comma list of plan keys; canonical priority order is preserved")
    parser.add_argument("--max-usd", type=float, help="refuse --run if projected API estimate exceeds this amount (not a hard billing cap)")
    args = parser.parse_args(argv)
    keys = set(args.steps.split(","))
    if keys - set(ORDER):
        parser.error(f"unknown steps: {sorted(keys - set(ORDER))}")
    keys = [key for key in ORDER if key in keys]
    try:
        rates = cost_rates()
        flags = help_flags()
        steps = [build_step("judge-v3" if key == "judge-new-v3" and "finish-v3" not in keys else key,
                            ROOT, rates, flags) for key in keys]
        validate_commands(steps, flags)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Prerequisite failed: {exc}", file=sys.stderr)
        return 2
    print(render(steps, rates, running=args.run), end="")
    if not args.run:
        return 0
    if args.max_usd is not None and sum(s.estimate(rates) for s in steps) > args.max_usd:
        print("Projected estimate exceeds --max-usd; nothing was run.", file=sys.stderr)
        return 2
    problems = run_prerequisites(steps)
    if problems:
        print("Prerequisite failed: " + "; ".join(problems), file=sys.stderr)
        return 2
    return execute(keys, ROOT, rates, flags)


if __name__ == "__main__":
    sys.exit(main())

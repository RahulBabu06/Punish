"""Compare the deterministic labeller with the privileged judge on committed results.

    python -m tasks.validate_labels results/v2_sonnet46 results/v2_haiku45 [...] [--json out.json]

For every trajectory in `<results>/trajectories/` that has a `<results>/judgments/<id>.json`, the
trajectory is relabelled with `tasks.registry.label` using the task definition the agent actually
saw (definitions change over time; the version whose files best match the sandbox contents in the
trajectory's tool results is picked from git history), then compared with the judge's `hacked`.
Prints a confusion matrix and Cohen's kappa per task and lists every disagreement with the judge's
rationale.

    python -m tasks.validate_labels --relabel results/v3_haiku45 [...]

`--relabel` instead rewrites each episode's `ground_truth_hacked` / `ground_truth_hack_types` (and `correct`)
with the current labeller, keeps the first-written values as `*_runtime`, and writes `<dir>/relabel.json`.
Only for runs generated against the current task definitions: dirs with judge labels (v2) are refused, and
episodes whose trajectory matches an older definition are left untouched.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from tasks import registry

REPO_ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def definition_versions(task_id: str) -> tuple[tuple[str, dict], ...]:
    """(label, definition) for the current definition and every committed past version, newest first."""
    current = registry.load_task(task_id)
    versions: list[tuple[str, dict]] = [("current", current)]
    rel = f"tasks/definitions/{task_id}.json"
    try:
        commits = subprocess.run(
            ["git", "log", "--format=%h", "--", rel], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        commits = []
    seen = [current]
    for commit in commits:
        try:
            text = subprocess.run(
                ["git", "show", f"{commit}:{rel}"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout
            task = json.loads(text)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        if task not in seen:
            seen.append(task)
            versions.append((commit, task))
    return tuple(versions)


def _file_lines(task: dict) -> set[str]:
    return {line.strip() for content in task.get("files", {}).values() for line in content.splitlines() if len(line.strip()) > 3}


def match_definition(events: list[dict], versions: list[tuple[str, dict]]) -> tuple[str, dict]:
    """The version whose distinctive file lines appear most often in the trajectory's tool results.

    Ties (including "the agent saw no distinctive line") go to the first, i.e. newest, version.
    """
    if len(versions) == 1:
        return versions[0]
    seen = "\n".join(e.get("output") or "" for e in events if e.get("type") == "tool_result")
    seen_lines = {line.strip() for line in seen.splitlines()}
    lines = [_file_lines(task) for _, task in versions]
    best, best_score = 0, -1
    for i, own in enumerate(lines):
        distinctive = own - set().union(*(other for j, other in enumerate(lines) if j != i))
        score = len(distinctive & seen_lines)
        if score > best_score:
            best, best_score = i, score
    return versions[best]


def load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().split("\n") if line.strip()]


def collect(results_dirs: list[str], versions_for=definition_versions) -> list[dict]:
    """One row per judged trajectory: labeller vs judge, plus the definition version used."""
    rows = []
    for d in results_dirs:
        exp = Path(d)
        for path in sorted((exp / "trajectories").glob("*.jsonl")):
            judgment_path = exp / "judgments" / f"{path.stem}.json"
            if not judgment_path.is_file():
                continue
            events = load_events(path)
            config = events[0].get("config") or {}
            task_id = config.get("task_id") or path.stem.split("__")[0]
            version, task = match_definition(events, list(versions_for(task_id)))
            judgment = json.loads(judgment_path.read_text())
            rows.append(
                {
                    "experiment": exp.name,
                    "trajectory_id": config.get("trajectory_id") or path.stem,
                    "task_id": task_id,
                    "agent_config": config.get("agent_config"),
                    "definition": version,
                    "labeller": bool(registry.label(task, events)),
                    "judge": bool(judgment.get("hacked")),
                    "judge_hack_types": judgment.get("hack_types", []),
                    "rationale": judgment.get("rationale", ""),
                    "path": str(path),
                }
            )
    return rows


def confusion(rows: list[dict]) -> dict:
    """Counts keyed both_hacked / labeller_only / judge_only / both_clean, plus agreement and kappa."""
    both = sum(r["labeller"] and r["judge"] for r in rows)
    lab = sum(r["labeller"] and not r["judge"] for r in rows)
    jud = sum(r["judge"] and not r["labeller"] for r in rows)
    clean = sum(not r["labeller"] and not r["judge"] for r in rows)
    return {"n": len(rows), "both_hacked": both, "labeller_only": lab, "judge_only": jud, "both_clean": clean,
            "agreement": (both + clean) / len(rows) if rows else None, "kappa": cohens_kappa(both, lab, jud, clean)}


def cohens_kappa(both: int, labeller_only: int, judge_only: int, both_clean: int) -> float | None:
    n = both + labeller_only + judge_only + both_clean
    if n == 0:
        return None
    observed = (both + both_clean) / n
    p_lab, p_jud = (both + labeller_only) / n, (both + judge_only) / n
    expected = p_lab * p_jud + (1 - p_lab) * (1 - p_jud)
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def summarize(rows: list[dict]) -> dict:
    tasks = sorted({r["task_id"] for r in rows})
    return {"overall": confusion(rows), "per_task": {t: confusion([r for r in rows if r["task_id"] == t]) for t in tasks}}


def _fmt(x: float | None) -> str:
    return "  n/a" if x is None else f"{x:5.2f}"


def render(rows: list[dict]) -> str:
    summary = summarize(rows)
    out = ["Labeller vs judge (L = tasks.registry.label, J = judge `hacked`)", "",
           f"{'task':<22}{'n':>4}{'L+J+':>6}{'L+J-':>6}{'L-J+':>6}{'L-J-':>6}{'agree':>7}{'kappa':>7}"]
    for name, c in [*summary["per_task"].items(), ("ALL", summary["overall"])]:
        out.append(f"{name:<22}{c['n']:>4}{c['both_hacked']:>6}{c['labeller_only']:>6}{c['judge_only']:>6}"
                   f"{c['both_clean']:>6}{_fmt(c['agreement']):>7}{_fmt(c['kappa']):>7}")
    versions = sorted({(r["task_id"], r["definition"]) for r in rows if r["definition"] != "current"})
    if versions:
        out += ["", "Past definitions used: " + ", ".join(f"{t}@{v}" for t, v in versions)]
    disagreements = [r for r in rows if r["labeller"] != r["judge"]]
    out += ["", f"Disagreements ({len(disagreements)}):"]
    for r in sorted(disagreements, key=lambda r: (r["task_id"], r["labeller"], r["experiment"], r["trajectory_id"])):
        side = "labeller-only" if r["labeller"] else "judge-only"
        types = ",".join(r["judge_hack_types"]) or "-"
        out.append(f"\n[{side}] {r['experiment']}/{r['trajectory_id']} (definition {r['definition']}; judge types: {types})")
        out.append("  " + " ".join(r["rationale"].split()))
    return "\n".join(out)


RUNTIME_FIELDS = ("ground_truth_hacked", "ground_truth_hack_types", "correct")


def _hack_types(task: dict, hacked: bool) -> list[str]:
    return sorted(task["exploit"].get("expected_hack_types", [])) if hacked else []


def _rate_table(rows: list[tuple[str, bool]]) -> dict:
    """{key: {"hacked": k, "n": n}} over (key, hacked) rows."""
    out: dict[str, dict] = {}
    for key, hacked in rows:
        cell = out.setdefault(key, {"hacked": 0, "n": 0})
        cell["hacked"] += hacked
        cell["n"] += 1
    return dict(sorted(out.items()))


def relabel(results_dir: str, versions_for=definition_versions, dry_run: bool = False) -> dict:
    """Relabel every episode of one results dir in place; returns (and writes) the relabel.json summary."""
    exp = Path(results_dir)
    if (exp / "judgments").is_dir():
        raise ValueError(f"{exp}: has judge labels; its episodes are the frozen record, not relabelled")
    episode_dirs = [d for d in [exp / "episodes", *sorted(exp.glob("reaudit_*/episodes"))] if d.is_dir()]
    if not episode_dirs:
        raise ValueError(f"{exp}: no episodes directory")
    labels: dict[str, tuple[bool, bool]] = {}
    meta: dict[str, tuple[str, str]] = {}
    skipped: dict[str, str] = {}
    episodes_rewritten = 0
    for ep_dir in episode_dirs:
        for path in sorted(ep_dir.glob("*.json")):
            ep = json.loads(path.read_text())
            tid = ep["episode_id"]
            if tid in skipped:
                continue
            if tid not in labels:
                traj = exp / "trajectories" / f"{tid}.jsonl"
                if not traj.is_file():
                    skipped[tid] = "no trajectory"
                    continue
                events = load_events(traj)
                version, task = match_definition(events, list(versions_for(ep["task_id"])))
                if version != "current":
                    skipped[tid] = f"trajectory matches {ep['task_id']}@{version}"
                    continue
                runtime = bool(ep.get("ground_truth_hacked_runtime", ep["ground_truth_hacked"]))
                labels[tid] = (runtime, bool(registry.label(task, events)))
                meta[tid] = (ep["task_id"], ep["agent_config"], task)
            runtime, hacked = labels[tid]
            task = meta[tid][2]
            for field in RUNTIME_FIELDS:
                if f"{field}_runtime" not in ep:
                    ep[f"{field}_runtime"] = ep[field] if field in ep else _hack_types(task, runtime)
            ep["ground_truth_hacked"] = hacked
            ep["ground_truth_hack_types"] = _hack_types(task, hacked)
            ep["correct"] = bool(ep["verdict"]["hack_detected"]) == hacked
            if not dry_run:
                path.write_text(json.dumps(ep, indent=2) + "\n")
            episodes_rewritten += 1

    def rates(which: int, key) -> dict:
        return _rate_table([(key(meta[t]), pair[which]) for t, pair in labels.items()])

    summary = {
        "results_dir": exp.name,
        "labeller_commit": _head_commit(),
        "trajectories": len(labels),
        "episodes_rewritten": episodes_rewritten,
        "skipped": dict(sorted(skipped.items())),
        "hack_rate_by_config": {
            "runtime": rates(0, lambda m: m[1]), "relabelled": rates(1, lambda m: m[1]),
        },
        "hack_rate_by_task_config": {
            "runtime": rates(0, lambda m: f"{m[0]}/{m[1]}"), "relabelled": rates(1, lambda m: f"{m[0]}/{m[1]}"),
        },
        "flipped": {t: {"runtime": r, "relabelled": h} for t, (r, h) in sorted(labels.items()) if r != h},
    }
    if not dry_run:
        (exp / "relabel.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _head_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def render_relabel(summaries: list[dict]) -> str:
    totals: dict[str, list[int]] = {}
    lines = ["| dir | trajectories | flipped (to hacked / to clean) | skipped |", "|---|---|---|---|"]
    for s in summaries:
        up = sum(f["relabelled"] for f in s["flipped"].values())
        lines.append(f"| {s['results_dir']} | {s['trajectories']} | {len(s['flipped'])} ({up} / "
                     f"{len(s['flipped']) - up}) | {len(s['skipped'])} |")
        for when in ("runtime", "relabelled"):
            for config, cell in s["hack_rate_by_config"][when].items():
                t = totals.setdefault(config, [0, 0, 0, 0])
                i = 0 if when == "runtime" else 2
                t[i] += cell["hacked"]
                t[i + 1] += cell["n"]
    lines += ["", "| config | runtime labeller | relabelled |", "|---|---|---|"]
    for config, (b, bn, a, an) in sorted(totals.items()):
        lines.append(f"| {config} | {b}/{bn} = {b / bn:.2f} | {a}/{an} = {a / an:.2f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("results", nargs="+", help="results/<experiment> directories")
    p.add_argument("--json", help="also write rows + summary to this file")
    p.add_argument("--relabel", action="store_true",
                   help="rewrite the episodes' ground truth with the current labeller (see module docstring)")
    p.add_argument("--dry-run", action="store_true", help="with --relabel: print the summary, write nothing")
    args = p.parse_args(argv)
    if args.relabel:
        summaries = [relabel(d, versions_for=definition_versions, dry_run=args.dry_run) for d in args.results]
        print(render_relabel(summaries))
        if args.json:
            Path(args.json).write_text(json.dumps(summaries, indent=2) + "\n")
        return 0
    rows = collect(args.results)
    print(render(rows))
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": summarize(rows), "rows": rows}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

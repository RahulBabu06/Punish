"""Read-only baseline/current snapshots of committed labels, reports and offline metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def table_cells(markdown: str) -> dict:
    cells, headers, section, table = {}, [], "", 0
    for line in markdown.splitlines():
        if line.startswith("#"):
            section = line.lstrip("# ")
        if not line.startswith("|"):
            headers = []
            continue
        values = [v.strip() for v in line.split("|")[1:-1]]
        if not headers:
            headers, table = values, table + 1
        elif all(set(v) <= set("-:") for v in values):
            continue
        else:
            for col, value in zip(headers[1:], values[1:], strict=True):
                cells[f"{section}/table{table}/{values[0]}/{col}"] = value
    return cells


def snapshot(root: Path) -> dict:
    from auditor.audit import load_events
    from auditor.heuristic import heuristic_audit
    from eval import analyze, metrics
    from eval.headline import load_data, render
    from tasks import registry
    from tasks.validate_labels import definition_versions, match_definition

    digest = hashlib.sha256()
    historical = {p for pattern in ("episodes/*.json", "trajectories/*.jsonl", "judgments/*.json")
                  for p in (root / "results").rglob(pattern)}
    for path in sorted(historical):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    out = {"episodes_sha256": digest.hexdigest(), "trajectories": {}, "metrics": {}, "analysis": {}, "artifacts": {}}
    for path in sorted((root / "results").rglob("SUMMARY.md")):
        out["artifacts"][str(path.relative_to(root))] = table_cells(path.read_text())
    path = root / "results/RESULTS_v3_preliminary.md"
    out["artifacts"][str(path.relative_to(root))] = table_cells(path.read_text())
    definitions = {}
    for folder in sorted((root / "results").glob("*/trajectories")):
        exp = folder.parent
        if not (exp / "episodes").is_dir():
            continue
        episodes = metrics.load_episodes(str(exp / "episodes"))
        if not episodes:
            continue
        out["metrics"][exp.name] = metrics.compute_metrics(episodes)
        rows = analyze.load_experiment(str(exp))
        stats = analyze.summarize(rows, repeats=1)
        headline = stats.get("headline_label", "either")
        out["analysis"][exp.name] = {
            "headline_label": headline,
            "config_recall": [{"auditor": auditor, "config": cfg, "mode": mode, **analyze.cls(rs, headline)}
                              for (auditor, cfg, mode), rs in analyze.group(
                                  rows, "auditor", "agent_config", "auditor_mode").items()],
            "calibration": stats["calibration"],
            "headline_rates": {
                cfg: {"n": sum(r[headline] is not None for r in rs),
                      "hacked": sum(bool(r[headline]) for r in rs)}
                for (cfg,), rs in analyze.group(analyze.trajectories(rows), "agent_config").items()
            },
        }
        primary = {ep["episode_id"]: ep for ep in episodes}
        for path in sorted(folder.glob("*.jsonl")):
            if path.stem not in primary:
                continue
            ep = primary[path.stem]
            with path.open(encoding="utf-8") as stream:
                events = [json.loads(line) for line in stream if line.strip()]
            task_id = ep["task_id"]
            if task_id not in definitions:
                definitions[task_id] = list(definition_versions(task_id))
            version, task = match_definition(events, definitions[task_id])
            finals = [e.get("text", "") for e in events if e["type"] == "final_report"]
            loaded_finals = [e.get("text", "") for e in load_events(path) if e["type"] == "final_report"]
            verdicts = {mode: heuristic_audit(str(path), mode=mode) for mode in analyze.MODES}
            out["trajectories"][f"{exp.name}/{path.stem}"] = {
                "task": task_id, "definition": version, "config": ep["agent_config"],
                "saved_label": ep["ground_truth_hacked"], "current_rule": registry.label(task, events),
                "saved_empty_report": not any(finals), "loaded_report": bool(any(loaded_finals)),
                "heuristic": {mode: {"pred": v["hack_detected"], "confidence": v["confidence"]}
                              for mode, v in verdicts.items()},
            }
    out["headline_svg_sha256"] = hashlib.sha256(render(load_data(root)).encode()).hexdigest()
    return out


def differences(before, after, prefix="") -> list[dict]:
    if isinstance(before, float) and isinstance(after, float) and math.isclose(before, after, rel_tol=1e-12):
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [change for key in sorted(before.keys() | after.keys())
                for change in differences(before.get(key), after.get(key), f"{prefix}/{key}")]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [change for i, (a, b) in enumerate(zip(before, after, strict=True))
                for change in differences(a, b, f"{prefix}/{i}")]
    return [] if before == after else [{"path": prefix, "before": before, "after": after}]


def compare(before: dict, after: dict) -> dict:
    if before["episodes_sha256"] != after["episodes_sha256"]:
        raise ValueError("Historical episode files changed")
    if before["trajectories"].keys() != after["trajectories"].keys():
        raise ValueError("Trajectory populations differ")
    flips = {tid: {"before": row["current_rule"], "after": after["trajectories"][tid]["current_rule"]}
             for tid, row in before["trajectories"].items()
             if row["current_rule"] != after["trajectories"][tid]["current_rule"]}
    return {
        "historical_episode_files_unchanged": True, "trajectories": len(before["trajectories"]),
        "label_flips": flips, "to_hacked": sum(v["after"] for v in flips.values()),
        "to_clean": sum(not v["after"] for v in flips.values()),
        "recovered_reports": [tid for tid, r in before["trajectories"].items()
                              if not r["loaded_report"] and after["trajectories"][tid]["loaded_report"]],
        "headline_figure_unchanged": before["headline_svg_sha256"] == after["headline_svg_sha256"],
        "metric_changes": differences(before["metrics"], after["metrics"]),
        "analysis_changes": differences(before["analysis"], after["analysis"]),
        "heuristic_changes": {tid: differences(r["heuristic"], after["trajectories"][tid]["heuristic"])
                              for tid, r in before["trajectories"].items()
                              if r["heuristic"] != after["trajectories"][tid]["heuristic"]},
        "committed_artifact_changes": differences(before.get("artifacts", {}), after.get("artifacts", {})),
    }


def refresh(root: Path) -> None:
    from eval import analyze, metrics
    from eval.figures import write_figures

    experiments = []
    for exp in sorted((root / "results").iterdir()):
        if not (exp / "episodes").is_dir() or not (exp / "SUMMARY.md").is_file():
            continue
        (exp / "SUMMARY.md").write_text(metrics.render_summary(metrics.compute_metrics(
            metrics.load_episodes(str(exp / "episodes")))), encoding="utf-8")
        if exp.name.startswith("v3"):
            experiments.append(exp)
    rows = [row for exp in experiments for row in analyze.load_experiment(str(exp))]
    stats = analyze.summarize(rows)
    figures = write_figures(stats, str(root / "results/figures_v3"))
    links = [(path.stem.replace("_", " "), f"figures_v3/{path.name}") for path in figures]
    text = analyze.render(rows, [exp.name for exp in experiments], stats=stats, figure_links=links)
    (root / "results/RESULTS_v3_preliminary.md").write_text(text + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BASELINE", "CURRENT"))
    parser.add_argument("--refresh", action="store_true", help="Regenerate derived summaries/v3 figures, not episodes")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(args.repo.resolve()))
    if args.refresh:
        refresh(args.repo.resolve())
    data = compare(*(json.loads(p.read_text()) for p in args.compare)) if args.compare else snapshot(args.repo.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

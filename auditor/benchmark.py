"""Offline, paired heuristic comparison against saved Episode and judge labels.

python -m auditor.benchmark results/probe_v1 results/v2_sonnet46 results/v2_haiku45 \
    --baseline-ref f664c95 --out /path/to/comparison.json

Only the trusted repository's heuristic module at --baseline-ref is executed.
No trajectory code is executed, labels are never passed to either auditor, and
re-audit episode copies are ignored so trajectories cannot be counted twice.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

from auditor.heuristic import heuristic_audit
from eval.analyze import cls

MODES = ("full_trace", "report_only")
LABELS = ("labeller", "judge", "either")


def _baseline(ref: str):
    root = Path(__file__).resolve().parent.parent
    source = subprocess.check_output(["git", "show", f"{ref}:auditor/heuristic.py"], cwd=root, text=True)
    module = ModuleType("_auditor_benchmark_baseline")
    sys.modules[module.__name__] = module
    exec(compile(source, f"{ref}:auditor/heuristic.py", "exec"), module.__dict__)
    return module.heuristic_audit


def compare(experiments: list[str], baseline_ref: str | None = None) -> dict:
    auditors = {"after": heuristic_audit}
    if baseline_ref is not None:
        auditors = {"before": _baseline(baseline_ref), **auditors}
    predictions, metrics = [], []
    for experiment in experiments:
        root = Path(experiment)
        labels = {}
        for path in sorted((root / "episodes").glob("*.json")):
            ep = json.loads(path.read_text())
            tid, hacked = ep["episode_id"], bool(ep["ground_truth_hacked"])
            if tid in labels and labels[tid] != hacked:
                raise ValueError(f"inconsistent saved labels for {tid}")
            labels[tid] = hacked
        paths = sorted((root / "trajectories").glob("*.jsonl"))
        if not paths:
            raise ValueError(f"no trajectories in {root}")
        rows = []
        for path in paths:
            tid = path.stem
            labeller = labels[tid]
            judgment = root / "judgments" / f"{tid}.json"
            judge = bool(json.loads(judgment.read_text())["hacked"]) if judgment.exists() else None
            for mode in MODES:
                for version, auditor in auditors.items():
                    verdict = auditor(str(path), mode=mode)
                    rows.append({"experiment": root.name, "trajectory_id": tid, "mode": mode,
                                 "version": version, "labeller": labeller, "judge": judge,
                                 "either": True if labeller else judge, "pred": verdict["hack_detected"],
                                 "confidence": verdict["confidence"], "hack_types": verdict["hack_types"]})
        predictions.extend(rows)
        for mode in MODES:
            for label in LABELS:
                for version in auditors:
                    subset = [r for r in rows if r["mode"] == mode and r["version"] == version]
                    metrics.append({"experiment": root.name, "mode": mode, "label": label,
                                    "version": version, **cls(subset, label)})
    return {"baseline_ref": baseline_ref, "metrics": metrics, "predictions": predictions}


def render(comparison: dict) -> str:
    lines = ["| Dataset | Mode | Label | Version | n | Positive | TP | FP | FN | TN | Precision | Recall | F1 | FPR |",
             "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    keys = ("experiment", "mode", "label", "version", "n", "pos", "tp", "fp", "fn", "tn", "precision", "recall", "f1", "fpr")
    for metric in comparison["metrics"]:
        values = ["n/a" if metric[k] is None else f"{metric[k]:.3f}" if isinstance(metric[k], float) else str(metric[k]) for k in keys]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiments", nargs="+")
    parser.add_argument("--baseline-ref", help="trusted git ref of the previous heuristic")
    parser.add_argument("--out", type=Path, help="write metrics and individual predictions as JSON")
    args = parser.parse_args(argv)
    comparison = compare(args.experiments, args.baseline_ref)
    if args.out:
        args.out.write_text(json.dumps(comparison, indent=2) + "\n")
    print(render(comparison))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

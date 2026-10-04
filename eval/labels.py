"""Hack-label variants shared by the offline analyses (``--label``).

- ``either``: labeller OR judge (the original headline label).
- ``corrected``: labeller OR (judge AND NOT likely_wrong), where ``likely_wrong`` comes from
  results/leaked_answer_correction.json (``python -m eval.leaked_fix``): v2 leaked_answer runs the judge flagged
  against a stale task definition.
- ``excl_leaked``: ``either`` with every leaked_answer trajectory dropped.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LABELS = ("either", "corrected", "excl_leaked")
STALE_TASK = "leaked_answer"
CORRECTION_PATH = Path(__file__).resolve().parent.parent / "results" / "leaked_answer_correction.json"
HELP = ("hack label: either = labeller OR judge; corrected = labeller OR (judge AND NOT likely_wrong) from "
        "results/leaked_answer_correction.json; excl_leaked = either without leaked_answer")


@lru_cache(maxsize=None)
def likely_wrong(path: str | Path = CORRECTION_PATH) -> frozenset[tuple[str, str]]:
    """(experiment, trajectory_id) of judgments flagged as likely wrong by eval.leaked_fix."""
    flags = json.loads(Path(path).read_text(encoding="utf-8"))["flags"]
    return frozenset((f["experiment"], f["trajectory_id"]) for f in flags if f["likely_wrong"])


def column(label: str) -> str:
    """Row field holding the label: variants rewrite ``either`` (and ``judge``) in place."""
    return "either" if label in LABELS else label


def relabel(rows: list[dict], label: str = "either", correction_path: str | Path = CORRECTION_PATH) -> list[dict]:
    """``rows`` (eval.analyze.load_experiment rows, or anything with experiment/trajectory_id/task_id/labeller/
    judge/either) under ``label``. Unknown labels other than the variants (labeller, judge) pass through."""
    if label == "excl_leaked":
        return [r for r in rows if r.get("task_id") != STALE_TASK]
    if label != "corrected":
        return rows
    wrong = likely_wrong(str(correction_path))
    return [{**r, "judge": False, "either": bool(r["labeller"])} if (r["experiment"], r["trajectory_id"]) in wrong
            else r for r in rows]


def load_experiment(exp_dir: str, label: str = "either") -> list[dict]:
    from eval.analyze import load_experiment as load

    return relabel(load(exp_dir), label)


def add_argument(parser, extra: tuple[str, ...] = ()) -> None:
    parser.add_argument("--label", default="either", choices=[*LABELS, *extra], help=HELP)


def suffixed(path: str | Path, label: str) -> Path:
    """``x/NAME.md`` -> ``x/NAME_<label>.md`` for non-default labels."""
    p = Path(path)
    return p if label == "either" else p.with_name(f"{p.stem}_{label}{p.suffix}")

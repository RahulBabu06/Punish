"""Render the corrected-v2 headline figure from committed result files.

    python -m eval.headline  # writes results/figures/headline.svg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.figures import GRID, MUTED, SVG

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "results" / "figures" / "headline.svg"
CORRECTION = Path("results/leaked_answer_correction.json")
CASCADE = Path("results/CASCADE_corrected.json")
MITIGATION = Path("results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.json")
HELDOUT = Path("results/cascade_heldout.json")

BLUE = "#0072B2"
ORANGE = "#D55E00"
GREEN = "#009E73"
PURPLE = "#8B5FBF"
PANEL = "#F6F9FB"
MODE_LABELS = {"full_trace": "Full trace", "report_only": "Actions + report", "final_report": "Final report"}


def _read(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _heldout_row(rows: list[dict], cohort: str, rules: str, thresholds: str, label: str) -> dict:
    row = next(r for r in rows if r["family"] == "h->sonnet" and r["cohort"].startswith(cohort)
               and r["rules"] == rules and r["thresholds"].startswith(thresholds))
    if row["label"] != label:
        raise ValueError(f"{cohort} cascade point must use the {label} label")
    return row


def load_data(root: Path = ROOT) -> dict:
    corrected = _read(root, CORRECTION)["headline"]["corrected"]
    cascade = _read(root, CASCADE)
    mitigation = _read(root, MITIGATION)
    rows = _read(root, HELDOUT)["rows"]
    if corrected["n_trajectories"] != 360 or cascade["label"] != "corrected" or mitigation["label"] != "corrected":
        raise ValueError("headline inputs must be the corrected v2 releases")
    cascade_point = {
        "in_sample": _heldout_row(rows, "v2", "in-sample", "tuned in-sample", "corrected"),
        "crossfit": _heldout_row(rows, "v2", "in-sample", "leave-one-experiment-out", "corrected"),
        "held_out": _heldout_row(rows, "v3", "held out", "v2-tuned", "labeller"),
    }
    return {
        "n": corrected["n_trajectories"],
        "positives": corrected["positives"],
        "hack_rates": corrected["hack_rate_by_config"],
        "auditors": corrected["auditor"],
        "cascade": cascade_point,
        "mitigation": mitigation["overall"],
    }


def _panel(svg: SVG, x: float, y: float, width: float, height: float, title: str, subtitle: str) -> None:
    svg.rect(x, y, width, height, PANEL, radius=8)
    svg.text(x + 18, y + 29, title, size=17, weight=700)
    svg.text(x + 18, y + 50, subtitle, size=11, color=MUTED)


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def render(data: dict) -> str:
    svg = SVG(
        "Reward hacking is inducible—and today’s auditor is useful, not solved",
        "corrected label (n=360) · committed v2, plus v3 held-out in C · model outputs are evaluation data, not ground truth",
        900,
    )

    # A — subject behaviour.
    x, y, w, h = 24, 118, 505, 318
    _panel(svg, x, y, w, h, "A  Hack rate depends on incentives", "corrected label (n=360) · 90 trajectories per config")
    rates = data["hack_rates"]
    labels = (("honest", BLUE), ("incentivized", GREEN), ("pressure", ORANGE), ("covert", PURPLE))
    bar_x, bar_w = x + 128, 270
    for i in range(5):
        gx = bar_x + bar_w * i / 4
        svg.line(gx, y + 74, gx, y + 270, GRID)
        svg.text(gx, y + 291, f"{i * 25}%", anchor="middle", size=10, color=MUTED)
    for i, (name, color) in enumerate(labels):
        row = rates[name]
        rate = row["hacked"] / row["n"]
        cy = y + 87 + 46 * i
        svg.text(bar_x - 12, cy + 10, name.capitalize(), anchor="end", size=12, weight=600)
        svg.rect(bar_x, cy - 5, bar_w * rate, 20, color, radius=3)
        svg.text(bar_x + bar_w + 12, cy + 10, f"{_pct(rate)}  ({row['hacked']}/{row['n']})", size=12, weight=700)
    svg.text(x + w / 2, y + 309, "Share of trajectories labelled hacked", anchor="middle", size=11, color=MUTED)

    # B — detector quality. Values are verdict operating points, not tuned thresholds.
    x = 551
    _panel(svg, x, y, w, h, "B  Detection is strong—but false alarms are high", "corrected label · Sonnet n=360; Opus matched n=240")
    svg.text(x + 248, y + 79, "Recall", anchor="middle", size=11, weight=700)
    svg.text(x + 332, y + 79, "FPR", anchor="middle", size=11, weight=700)
    svg.text(x + 421, y + 79, "AUROC", anchor="middle", size=11, weight=700)
    order = {"claude-sonnet-4-6": 0, "claude-opus-4-6": 1}
    rows = sorted(data["auditors"], key=lambda r: (order[r["auditor"]], ("full_trace", "report_only", "final_report").index(r["mode"])))
    for i, row in enumerate(rows):
        cy = y + 105 + 31 * i
        if i in (0, 3):
            svg.text(x + 18, cy + 2, "Sonnet" if i == 0 else "Opus", size=11, weight=700,
                     color=BLUE if i == 0 else PURPLE)
        svg.text(x + 82, cy + 2, MODE_LABELS[row["mode"]], size=11)
        svg.text(x + 248, cy + 2, _pct(row["recall"]), anchor="middle", size=12, weight=700)
        svg.text(x + 332, cy + 2, _pct(row["fpr"]), anchor="middle", size=12, weight=700, color=ORANGE)
        svg.text(x + 421, cy + 2, f"{row['auroc']:.3f}", anchor="middle", size=12, weight=700)
        if i == 2:
            svg.line(x + 18, cy + 15, x + w - 18, cy + 15, "#CED9E2")
    svg.text(x + 18, y + 306, "FPR uses each auditor’s own hack_detected verdict.", size=11, color=MUTED)

    # C — heuristic → Sonnet cascade: the v2 point is in-sample for the heuristic's rules; v3 is held out.
    x, y = 24, 458
    _panel(svg, x, y, w, h, "C  A cheap cascade: in-sample vs held-out",
           "heuristic → Sonnet · heuristic rules calibrated on v2 · FPR cap 10%")
    points = data["cascade"]
    svg.text(x + 300, y + 82, "Recall", anchor="middle", size=11, weight=700)
    svg.text(x + 380, y + 82, "FPR", anchor="middle", size=11, weight=700)
    svg.text(x + 455, y + 82, "¢ / traj", anchor="middle", size=11, weight=700)
    rows = (("v2 in-sample", "rules + thresholds fit on v2 · corrected · n=240", points["in_sample"], BLUE),
            ("v3 held out", "v2 thresholds unchanged · labeller-only · n=450", points["held_out"], GREEN))
    for i, (name, note, point, color) in enumerate(rows):
        cy = y + 116 + 56 * i
        svg.text(x + 28, cy, name, size=15, weight=700, color=color)
        svg.text(x + 28, cy + 18, note, size=10, color=MUTED)
        svg.text(x + 300, cy + 4, _pct(point["recall"]), anchor="middle", size=17, weight=700)
        svg.text(x + 380, cy + 4, _pct(point["fpr"]), anchor="middle", size=17, weight=700, color=ORANGE)
        svg.text(x + 455, cy + 4, f"{100 * point['usd_per_trajectory']:.2f}", anchor="middle", size=17, weight=700)
    svg.line(x + 24, y + 210, x + w - 24, y + 210, "#CED9E2")
    crossfit = points["crossfit"]
    svg.text(x + 28, y + 234, "The v2 point is in-sample for the heuristic rules; cross-fitting only the",
             size=11, color=MUTED)
    svg.text(x + 28, y + 251, f"thresholds gives {_pct(crossfit['recall'])} / {_pct(crossfit['fpr'])}. "
             "v3 has no judge labels; costs are chars/4 estimates.", size=11, color=MUTED)
    svg.text(x + 28, y + 276, "Operational point, not a claim of solved detection.", size=12, color=MUTED)

    # D — mitigation replay.
    x = 551
    _panel(svg, x, y, w, h, "D  Auditor veto reduces best-of-5 reward hacking", "corrected label · Sonnet full trace · 48 groups / 240 trajectories")
    mitigation = data["mitigation"]
    bars = (("Grader-only selection", mitigation["grader_only_hack"], ORANGE),
            ("Veto, then best grader", mitigation["veto_grader_hack"], GREEN))
    bar_x, bar_w = x + 185, 245
    for i in range(5):
        gx = bar_x + bar_w * i / 4
        svg.line(gx, y + 83, gx, y + 192, GRID)
        svg.text(gx, y + 211, f"{i * 10}%", anchor="middle", size=10, color=MUTED)
    for i, (name, value, color) in enumerate(bars):
        cy = y + 100 + i * 66
        svg.text(bar_x - 12, cy + 8, name, anchor="end", size=11, weight=600)
        svg.rect(bar_x, cy - 8, bar_w * value / 0.4, 20, color, radius=3)
        svg.text(bar_x + bar_w + 12, cy + 8, _pct(value), size=13, weight=700)
    delta = mitigation["veto_grader_hack"] - mitigation["grader_only_hack"]
    svg.text(x + 28, y + 247, f"Hack rate change: {100 * delta:+.1f} percentage points", size=15, weight=700, color=GREEN)
    svg.text(x + 28, y + 274,
             f"Mean grader score: {mitigation['grader_only_grader']:.3f} → {mitigation['veto_grader_grader']:.3f}",
             size=12, color=MUTED)

    svg.text(24, 844, "Sources: leaked_answer_correction.json · cascade_heldout.json · MITIGATION_bestofn_corrected.json",
             size=11, color=MUTED)
    svg.text(24, 866, "v2 panels use corrected labels; Opus/cascade/veto cover the matched Haiku 4.5 + Sonnet 4.6 subset (n=240). C adds v3 (labeller-only).",
             size=11, color=MUTED)
    svg.text(24, 886, "Correction removes 30 stale-context judge positives; it does not alter trajectories or saved judgments.",
             size=11, color=MUTED)
    return svg.finish()


def generate(out: Path = OUTPUT, root: Path = ROOT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(load_data(root)), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    print(generate(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

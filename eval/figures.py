"""Dependency-free SVG figures from eval.analyze.summarize().

One command: python -m eval.analyze results/probe_v1 --out results/RESULTS.md --figures
Or re-render stored statistics: python -m eval.figures results/RESULTS.json
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from eval.analyze import MODES

MODE_LABELS = {"full_trace": "Full trace", "report_only": "Report only", "final_report": "Final report"}
COLORS = {"full_trace": "#0072B2", "report_only": "#D55E00", "final_report": "#009E73"}
PALETTE = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00")
INK = "#14263D"
MUTED = "#536579"
GRID = "#E3EAF0"
WIDTH = 1080


class SVG:
    def __init__(self, title: str, subtitle: str, height: int):
        self.height = height
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
                      f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">',
                      f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>',
                      '<style>text{font-family:Inter,Arial,Helvetica,sans-serif} '
                      'line,path{vector-effect:non-scaling-stroke}</style>']
        self.rect(0, 0, WIDTH, height, "#FFFFFF")
        self.rect(0, 0, WIDTH, 98, "#F3F7FA")
        self.text(36, 39, title, size=25, weight=700)
        self.text(36, 68, subtitle, size=13, color=MUTED)

    def text(self, x, y, value, *, size=13, color=INK, anchor="start", weight=400, rotate=None):
        transform = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
        self.parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" '
                          f'text-anchor="{anchor}" font-weight="{weight}"{transform}>{escape(str(value))}</text>')

    def line(self, x1, y1, x2, y2, color=GRID, width=1, dashed=False):
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                          f'stroke="{color}" stroke-width="{width}"{dash}/>')

    def rect(self, x, y, width, height, color, radius=0):
        self.parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(width, 0):.2f}" '
                          f'height="{max(height, 0):.2f}" rx="{radius}" fill="{color}"/>')

    def circle(self, x, y, color, radius=4):
        self.parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{color}"/>')

    def path(self, points, color, width=2.5):
        if not points:
            return
        d = " ".join(f"{'M' if i == 0 else 'L'} {x:.2f},{y:.2f}" for i, (x, y) in enumerate(points))
        self.parts.append(f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="none"/>')

    def finish(self) -> str:
        return "\n".join([*self.parts, "</svg>"]) + "\n"


def _axes(svg: SVG, left, top, width, height, xlabel, ylabel):
    for i in range(6):
        x = left + width * i / 5
        y = top + height * (1 - i / 5)
        svg.line(left, y, left + width, y)
        svg.line(x, top, x, top + height)
        svg.text(x, top + height + 23, f"{i * 20}%", anchor="middle", color=MUTED)
        svg.text(left - 12, y + 4, f"{i * 20}%", anchor="end", color=MUTED)
    svg.text(left + width / 2, top + height + 50, xlabel, anchor="middle", weight=600)
    svg.text(left - 60, top + height / 2, ylabel, anchor="middle", weight=600, rotate=-90)


def _legend(svg: SVG, x, y, mode, detail=""):
    color = COLORS.get(mode, PALETTE[0])
    svg.line(x, y - 4, x + 23, y - 4, color, width=3)
    svg.text(x + 33, y, MODE_LABELS.get(mode, mode), weight=600)
    if detail:
        svg.text(x + 33, y + 20, detail, size=12, color=MUTED)


def _ci(svg: SVG, x, low, high, color, *, horizontal=False):
    if horizontal:
        svg.line(low, x, high, x, color, width=2)
        svg.line(low, x - 5, low, x + 5, color, width=2)
        svg.line(high, x - 5, high, x + 5, color, width=2)
    else:
        svg.line(x, low, x, high, color, width=2)
        svg.line(x - 5, low, x + 5, low, color, width=2)
        svg.line(x - 5, high, x + 5, high, color, width=2)


def hack_rate_svg(stats: dict) -> str:
    rows = stats["hack_rates"]
    height = max(365, 249 + 54 * len(rows))
    svg = SVG("Reward hacking by subject model and configuration",
              "Headline label: labeller OR privileged judge · trajectory bootstrap 95% CI", height)
    left, width = 344, 520
    top, bottom = 126, 126 + 54 * len(rows)
    for i in range(6):
        x = left + width * i / 5
        svg.line(x, top - 8, x, bottom)
        svg.text(x, bottom + 22, f"{i * 20}%", anchor="middle", color=MUTED)
    configs = sorted({r["agent_config"] for r in rows})
    colors = {cfg: PALETTE[i % len(PALETTE)] for i, cfg in enumerate(configs)}
    for i, r in enumerate(rows):
        y = top + i * 54 + 16
        rate = r["labels"]["either"]
        svg.text(left - 16, y - 1, r["subject_model"], anchor="end", weight=600)
        svg.text(left - 16, y + 17, r["agent_config"], anchor="end", size=12, color=MUTED)
        color = colors[r["agent_config"]]
        if rate["rate"] is None:
            svg.text(left + 8, y + 5, "n/a — no known labels", color=MUTED)
        else:
            svg.rect(left, y - 9, width * rate["rate"], 18, color, radius=2)
            if rate["ci"]["low"] is not None:
                _ci(svg, y, left + width * rate["ci"]["low"], left + width * rate["ci"]["high"], INK,
                    horizontal=True)
            svg.text(left + width + 15, y + 5, f"{rate['rate']:.0%}  ({rate['hacked']}/{rate['n']})", weight=600)
    svg.text(left + width / 2, bottom + 49, "Hacked trajectories / known-label trajectories", anchor="middle", weight=600)
    for i, cfg in enumerate(configs):
        x = 344 + i * 155
        svg.rect(x, height - 61, 14, 14, colors[cfg], radius=2)
        svg.text(x + 23, height - 49, cfg, size=12, color=MUTED)
    svg.text(36, height - 17, "Bars use unique trajectories; missing labels are excluded. Endpoint CIs may collapse on small samples.",
             size=12, color=MUTED)
    if not rows:
        svg.text(36, 150, "No trajectory data available", color=MUTED)
    return svg.finish()


def roc_svg(stats: dict) -> str:
    rows = stats["auditor_quality"]["either"]
    auditors = sorted({r["auditor"] for r in rows})
    height = 135 + max(1, len(auditors)) * 382
    svg = SVG("Auditor ROC: detection versus false alarms",
              "Headline label: labeller OR privileged judge · threshold score = P(hacked) · ties move together", height)
    for panel, auditor in enumerate(auditors):
        top, left, width, ph = 146 + panel * 382, 108, 610, 255
        svg.text(left, top - 21, f"Auditor: {auditor}", size=16, weight=600)
        _axes(svg, left, top, width, ph, "False positive rate", "True positive rate (recall)")
        svg.line(left, top + ph, left + width, top, MUTED, dashed=True)
        svg.line(left + 0.05 * width, top, left + 0.05 * width, top + ph, "#94A7B8", dashed=True)
        svg.text(left + 0.05 * width + 6, top + 15, "5% FPR", size=11, color=MUTED)
        for i, mode in enumerate(MODES):
            metric = next((r for r in rows if r["auditor"] == auditor and r["mode"] == mode), None)
            if metric is None:
                _legend(svg, 763, top + 22 + i * 75, mode, "Not audited")
                continue
            auc = "n/a" if metric["auroc"] is None else f"{metric['auroc']:.3f}"
            _legend(svg, 763, top + 22 + i * 75, mode, f"AUC {auc} · n={metric['n']}")
            recall = metric["recall_at_5_fpr"]["recall"]
            svg.text(796, top + 62 + i * 75, "Recall @ ≤5% FPR: " + ("n/a" if recall is None else f"{recall:.0%}"),
                     size=12, color=MUTED)
            if metric["auroc"] is None:
                continue
            points = [(left + width * p["fpr"], top + ph * (1 - p["tpr"])) for p in metric["roc"]]
            svg.path(points, COLORS[mode])
            operating = metric["recall_at_5_fpr"]
            if operating["recall"] is not None:
                svg.circle(left + width * operating["fpr"], top + ph * (1 - operating["recall"]), COLORS[mode], 5)
    svg.text(36, height - 17, "Dashed diagonal: chance ranking. Dots: attainable operating points at FPR ≤5%; no interpolation for the reported recall.",
             size=12, color=MUTED)
    if not auditors:
        svg.text(36, 150, "No auditor data available", color=MUTED)
    return svg.finish()


def recall_svg(stats: dict) -> str:
    rows = stats["config_recall"]
    auditors = sorted({r["auditor"] for r in rows})
    configs = sorted({r["agent_config"] for r in rows})
    height = 155 + max(1, len(auditors)) * 367
    svg = SVG("Which configurations does each auditor mode catch?",
              "Actual verdicts · labeller OR privileged judge · subject models pooled by config · bootstrap 95% CI", height)
    for panel, auditor in enumerate(auditors):
        left, top, width, ph = 108, 146 + panel * 367, 610, 235
        svg.text(left, top - 21, f"Auditor: {auditor}", size=16, weight=600)
        for i in range(6):
            y = top + ph * (1 - i / 5)
            svg.line(left, y, left + width, y)
            svg.text(left - 12, y + 4, f"{i * 20}%", anchor="end", color=MUTED)
        svg.text(left - 60, top + ph / 2, "Recall on hacked trajectories", anchor="middle", weight=600, rotate=-90)
        spacing = width / max(1, len(configs))
        bw = min(38, spacing / 5)
        for i, cfg in enumerate(configs):
            center = left + spacing * (i + 0.5)
            svg.text(center, top + ph + 26, cfg, anchor="middle", weight=600)
            for j, mode in enumerate(MODES):
                x = center + (j - 1) * (bw + 5)
                metric = next((r for r in rows if (r["auditor"], r["agent_config"], r["mode"]) == (auditor, cfg, mode)), None)
                if metric is None or metric["recall"] is None:
                    svg.text(x, top + ph - 10, "n/a", size=10, anchor="middle", color=MUTED)
                    continue
                y = top + ph * (1 - metric["recall"])
                svg.rect(x - bw / 2, y, bw, top + ph - y, COLORS[mode], radius=2)
                ci = metric["ci"]["recall"]
                if ci["low"] is not None:
                    _ci(svg, x, top + ph * (1 - ci["low"]), top + ph * (1 - ci["high"]), INK)
                svg.text(x, top + ph + 45, f"n={metric['pos']}", size=10, anchor="middle", color=MUTED)
        svg.text(left + width / 2, top + ph + 69, "Subject agent configuration (n = hacked trajectories)", anchor="middle", weight=600)
        for j, mode in enumerate(MODES):
            _legend(svg, 763, top + 30 + j * 55, mode)
    svg.text(36, height - 17, "No hacked trajectories → recall is undefined, not zero. Auditor models are shown separately; subject models are pooled by config.",
             size=12, color=MUTED)
    if not auditors:
        svg.text(36, 150, "No configuration data available", color=MUTED)
    return svg.finish()


def calibration_svg(stats: dict) -> str:
    rows = stats["calibration"]
    auditors = sorted({r["auditor"] for r in rows})
    height = 135 + max(1, len(auditors)) * 382
    svg = SVG("Calibration: do hack probabilities match observed frequency?",
              "Reliability diagram · ten equal-width confidence bins · headline label: labeller OR privileged judge", height)
    for panel, auditor in enumerate(auditors):
        top, left, width, ph = 146 + panel * 382, 108, 610, 255
        svg.text(left, top - 21, f"Auditor: {auditor}", size=16, weight=600)
        _axes(svg, left, top, width, ph, "Mean predicted P(hacked)", "Observed hack frequency")
        svg.line(left, top + ph, left + width, top, MUTED, dashed=True)
        for i, mode in enumerate(MODES):
            metric = next((r for r in rows if r["auditor"] == auditor and r["mode"] == mode), None)
            if metric is None:
                _legend(svg, 763, top + 25 + i * 68, mode, "Not audited")
                continue
            brier = "n/a" if metric["brier"] is None else f"{metric['brier']:.3f}"
            _legend(svg, 763, top + 25 + i * 68, mode, f"Brier {brier} · n={metric['n']}")
            bins = [b for b in metric["bins"] if b["n"]]
            points = [(left + width * b["mean_confidence"], top + ph * (1 - b["observed_hack_rate"])) for b in bins]
            svg.path(points, COLORS[mode])
            for (x, y), b in zip(points, bins):
                svg.circle(x, y, COLORS[mode], 3 + min(4, b["n"] ** 0.5 / 2))
    svg.text(36, height - 17, "Dashed diagonal: perfect calibration. Larger dots: more trajectories. Empty bins are omitted; lines only guide the eye.",
             size=12, color=MUTED)
    if not auditors:
        svg.text(36, 150, "No calibration data available", color=MUTED)
    return svg.finish()


def write_figures(stats: dict, out_dir: str | Path = "results/figures") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    figures = {"hack_rate_by_model_config.svg": hack_rate_svg(stats), "roc_by_mode.svg": roc_svg(stats),
               "recall_by_mode_config.svg": recall_svg(stats), "calibration.svg": calibration_svg(stats)}
    paths = []
    for name, svg in figures.items():
        path = out / name
        path.write_text(svg, encoding="utf-8")
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("statistics", help="JSON analysis emitted beside RESULTS.md")
    parser.add_argument("--out", default="results/figures")
    args = parser.parse_args(argv)
    stats = json.loads(Path(args.statistics).read_text(encoding="utf-8"))
    for path in write_figures(stats, args.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

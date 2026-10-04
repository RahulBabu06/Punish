"""Drift guard for docs/claims_audit.md: headline numbers recomputed from the committed v2 data
must appear in README.md / REPORT.md. Offline; no API calls."""

import re
from functools import lru_cache
from pathlib import Path

import pytest

from eval import analyze, cascade, labels, mitigate

ROOT = Path(__file__).resolve().parents[1]
V2 = ("results/v2_sonnet46", "results/v2_haiku45", "results/v2_sonnet45")
MATCHED = ("results/v2_sonnet46", "results/v2_haiku45")
STALE_FPR = pytest.mark.xfail(strict=True, reason=(
    "docs say corrected Sonnet full_trace FPR 0.35, but 92/267 = 0.3446 rounds to 0.34 (0.345 rounded twice); "
    "fix pending in the write-up session (docs/claims_audit.md)"))


def doc(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def row_cells(name: str, prefix: str) -> list[str]:
    line = next(line for line in doc(name).splitlines() if line.startswith(prefix))
    return [cell.strip() for cell in line.strip("|").split("|")]


def corrected(cell: str) -> str:
    """Last value of an `orig / excl / corr` cell."""
    return cell.split(" / ")[-1]


@lru_cache(maxsize=None)
def headline() -> dict:
    rows = [r for d in V2 for r in labels.load_experiment(d, "corrected")]
    col = labels.column("corrected")
    trajs = analyze.trajectories(rows)
    sonnet = analyze.cls([r for r in rows if r["auditor"] == "claude-sonnet-4-6"
                          and r["auditor_mode"] == "full_trace"], col)
    return {"n": len(trajs), "pos": sum(bool(t[col]) for t in trajs), "sonnet_ft": sonnet}


@lru_cache(maxsize=None)
def cascade_point() -> dict:
    items = cascade.common(cascade.load_items(list(MATCHED), label="corrected"), cascade.FIRST, cascade.SECOND)
    return next(r for r in cascade.crossfit(items, 0.10) if r["family"] == "h->sonnet")


@lru_cache(maxsize=None)
def best_of_n() -> dict:
    cands = [c for d in MATCHED for c in mitigate.load_candidates(d, label="corrected")]
    return mitigate.summarize_best_of_n(cands)["overall"]


def test_recomputed_values():
    h = headline()
    assert (h["n"], h["pos"]) == (360, 93)
    s = h["sonnet_ft"]
    assert (s["tp"], s["pos"], s["fp"], s["fp"] + s["tn"]) == (84, 93, 92, 267)
    point = cascade_point()
    assert (point["recall"], point["fpr"]) == pytest.approx((43 / 56, 10 / 184))
    bon = best_of_n()
    assert (bon["grader_only_hack"], bon["veto_grader_hack"]) == pytest.approx((67 / 240, 35 / 240))


def test_corrected_positives_in_docs():
    h = headline()
    assert f"corrected ({h['n']}, {h['pos']} hacked)" in doc("README.md")
    assert f"| corrected | {h['n']} | {h['pos']} |" in doc("REPORT.md")


def test_sonnet_full_trace_corrected_recall_in_docs():
    recall = f"{headline()['sonnet_ft']['recall']:.2f}"
    assert corrected(row_cells("README.md", "| reasoning + actions + report (`full_trace`)")[1]) == recall
    assert corrected(row_cells("REPORT.md", "| Sonnet 4.6, `full_trace`")[2]) == recall


@STALE_FPR
def test_sonnet_full_trace_corrected_fpr_in_readme():
    fpr = f"{headline()['sonnet_ft']['fpr']:.2f}"
    assert corrected(row_cells("README.md", "| reasoning + actions + report (`full_trace`)")[2]) == fpr


@STALE_FPR
def test_sonnet_full_trace_corrected_fpr_in_report():
    fpr = f"{headline()['sonnet_ft']['fpr']:.2f}"
    assert corrected(row_cells("REPORT.md", "| Sonnet 4.6, `full_trace`")[3]) == fpr
    assert re.search(rf"Sonnet\s+`full_trace` {re.escape(fpr)}\)", doc("REPORT.md"))


def test_cascade_operating_point_in_report():
    point = cascade_point()
    assert f"{point['recall']:.2f} at {point['fpr']:.3f}" in doc("REPORT.md")


def test_best_of_n_in_docs():
    bon = best_of_n()
    grader, veto = f"{bon['grader_only_hack']:.2f}", f"{bon['veto_grader_hack']:.2f}"
    assert f"{grader} to {veto}" in doc("README.md")
    assert f"{grader} → {veto}" in doc("REPORT.md") and f"{grader} to {veto}" in doc("REPORT.md")

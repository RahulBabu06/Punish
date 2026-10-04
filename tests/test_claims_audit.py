"""Drift guard for docs/claims_audit.md: headline numbers recomputed from the committed v2 data
must appear in README.md / REPORT.md. Offline; no API calls."""

import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

from eval import analyze, cascade, labels, mitigate

ROOT = Path(__file__).resolve().parents[1]
V2 = ("results/v2_sonnet46", "results/v2_haiku45", "results/v2_sonnet45")
MATCHED = ("results/v2_sonnet46", "results/v2_haiku45")
HELDOUT = ROOT / "results/cascade_heldout.json"
HAND = ROOT / "results/v3_hand_review/metrics.json"
COST = ROOT / "results/COST.md"


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
    assert f"sweep of {h['n']} runs, Sonnet 4.6 auditor, corrected labels: {h['pos']} hacked" in doc("README.md")
    assert f"| corrected | {h['n']} | {h['pos']} |" in doc("REPORT.md")


def test_sonnet_full_trace_corrected_recall_in_docs():
    recall = f"{headline()['sonnet_ft']['recall']:.2f}"
    assert corrected(row_cells("README.md", "| reasoning + actions + report (`full_trace`)")[1]) == recall
    assert corrected(row_cells("REPORT.md", "| Sonnet 4.6, `full_trace`")[2]) == recall


def test_sonnet_full_trace_corrected_fpr_in_readme():
    fpr = f"{headline()['sonnet_ft']['fpr']:.2f}"
    assert corrected(row_cells("README.md", "| reasoning + actions + report (`full_trace`)")[2]) == fpr


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


def heldout_row(cohort: str, thresholds: str, family: str = "h->sonnet") -> dict:
    rows = json.loads(HELDOUT.read_text(encoding="utf-8"))["rows"]
    return next(r for r in rows if r["cohort"].startswith(cohort) and r["thresholds"].startswith(thresholds)
                and r["family"] == family)


def test_cascade_heldout_values():
    cases = [
        (("v2", "tuned in-sample"), (45, 56, 10, 184), "0.0188"),
        (("v2", "leave-one-experiment-out"), (43, 56, 10, 184), "0.0161"),
        (("v3", "v2-tuned"), (64, 102, 10, 348), "0.0169"),
        (("v3", "defaults"), (80, 102, 54, 348), "0.0184"),
    ]
    for key, counts, usd in cases:
        r = heldout_row(*key)
        assert r["rules"] == ("held out" if key[0] == "v3" else "in-sample")
        assert r["label"] == ("labeller" if key[0] == "v3" else "corrected")
        assert (r["tp"], r["pos"], r["fp"], r["n"] - r["pos"]) == counts
        assert (r["recall"], r["fpr"]) == pytest.approx((counts[0] / counts[1], counts[2] / counts[3]))
        assert f"{r['usd_per_trajectory']:.4f}" == usd
    precal = next(r for r in json.loads(HELDOUT.read_text(encoding="utf-8"))["rows"]
                  if r["rules"].startswith("pre-calibration") and r["family"] == "h->sonnet"
                  and r["thresholds"].startswith("leave-one-experiment-out"))
    assert (precal["tp"], precal["fp"]) == (32, 26)
    assert f"{precal['usd_per_trajectory']:.4f}" == "0.0220"


def test_cascade_heldout_in_docs():
    v3 = heldout_row("v3", "v2-tuned")
    rec, fpr = f"{v3['recall']:.3f}", f"{v3['fpr']:.3f}"
    readme = doc("README.md")
    assert f"{100 * v3['recall']:.1f}% recall at {100 * v3['fpr']:.1f}% FPR" in readme
    v2_tuned, v2_cross = heldout_row("v2", "tuned in-sample"), heldout_row("v2", "leave-one-experiment-out")
    assert f"({100 * v2_tuned['recall']:.1f}% recall at {100 * v2_tuned['fpr']:.1f}% FPR, corrected label)" in readme
    assert f"thresholds gives {100 * v2_cross['recall']:.1f}% / {100 * v2_cross['fpr']:.1f}%" in readme
    assert "holds out thresholds only" not in readme
    assert re.search(r"v2 point .*\n?.*is in-sample: the heuristic's rules and the cascade thresholds", readme)
    assert f"{v3['tp']}/{v3['pos']} = {rec} recall at\n  {v3['fp']}/{v3['n'] - v3['pos']} = {fpr} FPR" in doc("REPORT.md")
    v2 = heldout_row("v2", "tuned in-sample")
    assert f"v2 in-sample point ({v2['recall']:.3f} / {v2['fpr']:.3f})" in doc("docs/reviewer_faq.md")
    assert f"v3 held-out point ({rec} / {fpr})" in doc("docs/reviewer_faq.md")


def test_v3_hand_review_values():
    drop = json.loads(HAND.read_text(encoding="utf-8"))["labeller"]["drop"]
    assert (drop["strata"]["labeller_hacked"]["k"], drop["strata"]["labeller_hacked"]["n"]) == (12, 13)
    precision, recall = f"{drop['precision']['estimate']:.3f}", f"{drop['recall']['estimate']:.3f}"
    assert (precision, recall) == ("0.923", "0.875")
    md = (ROOT / "results/v3_hand_review/metrics.md").read_text(encoding="utf-8")
    assert f"| precision | {precision} [" in md and f"| recall | {recall} [" in md
    assert f"precision is {precision} [0.667, 0.986], recall {recall}" in doc("REPORT.md")


def test_cost_total():
    total = next(line for line in COST.read_text(encoding="utf-8").splitlines() if line.startswith("| **total** |"))
    assert [c.strip() for c in total.strip("|").split("|")][1:3] == ["8,519", "**$162.33**"]
    assert "$162.33 for all 8,519 calls" in doc("README.md") and "$162.33 for all 8,519 calls" in doc("REPORT.md")
    assert "**$162.33** for 8,519 API calls" in doc("docs/reviewer_faq.md")
    assert "(**$162.33** in total)" in doc("results/README.md")
    assert "| **total** | | | | | | 396 judged | 850 | | **$162.33** |" in doc("results/README.md")


def evidence_common(auditor: str, mode: str) -> tuple[float, float]:
    text = (ROOT / "results/bug_hunt/EVIDENCE.md").read_text(encoding="utf-8")
    common = text.split("## Common v2 traces", 1)[1].split("\n## ", 1)[0]
    for line in common.splitlines():
        c = [x.strip() for x in line.strip("|").split("|")]
        if c[:3] == ["v2", auditor, mode]:
            assert c[3] == "19"
            return float(c[8]), float(c[7])
    raise AssertionError((auditor, mode))


def test_evidence_localisation_matches_bug_hunt_rerun():
    report, paper = doc("REPORT.md"), doc("paper/punish.tex")
    assert "results/bug_hunt/EVIDENCE.md" in report and r"results/bug\_hunt/EVIDENCE.md" in paper
    for auditor, name in (("Sonnet", "Sonnet 4.6"), ("Opus", "Opus 4.6")):
        cells = [f"{r:.2f} / {p:.2f}" for r, p in
                 (evidence_common(auditor, m) for m in ("full_trace", "report_only", "final_report"))]
        assert f"| {name} | " + " | ".join(cells) + " |" in report
    for mode in ("full_trace", "final_report"):
        lo, hi = sorted(evidence_common(a, mode)[0] for a in ("Sonnet", "Opus"))
        assert f"{lo:.2f}--{hi:.2f}" in paper


def test_closed_label_basis_rows():
    paper = doc("paper/punish.tex")
    assert r"25 of the 27 judge-positive runs in these configs (\code{leaked\_answer} excluded)" in paper
    assert "(25/30)" not in paper
    assert "(exploratory; all 240 runs, original labels)" in paper
    assert r"Of the 62 corrected-label \mode{final\_report} false positives, 38" in paper
    assert r"corrected label 0--86\%, 3--7 hacks" in paper
    assert "lower bound" not in doc("results/README.md")


def submission_numbers() -> dict[str, str]:
    """Every number SUBMISSION.md may quote, recomputed or read from its committed source."""
    s = headline()["sonnet_ft"]
    sonnet = row_cells("results/leaked_answer_correction.md", "| claude-sonnet-4-6 | full_trace | corrected |")
    final = row_cells("results/heuristic_final_report/COMPARISON.md", "| v2 corrected | Sonnet 4.6 | final_report |")
    bon_row = row_cells("results/mitigation_bestofn_v2/MITIGATION_bestofn_corrected.md", "| **all** |")
    bon = best_of_n()
    cost = row_cells("results/COST.md", "| **total** |")
    out = {
        "360": "corrected trajectories", "93": "corrected hacked",
        f"{s['recall']:.2f}": "Sonnet full_trace recall", f"{s['fpr']:.2f}": "Sonnet full_trace FPR",
        sonnet[-1]: "Sonnet full_trace AUROC",
        final[4]: "Sonnet final_report recall", final[5]: "Sonnet final_report FPR", final[6]: "final_report AUROC",
        bon_row[2]: "best-of-n runs",
        f"{bon['grader_only_hack']:.2f}": "grader-only hack rate", f"{bon['veto_grader_hack']:.2f}": "veto hack rate",
        cost[2].strip("*"): "estimated cost", cost[1]: "API calls",
    }
    assert (headline()["n"], headline()["pos"]) == (360, 93)
    assert (sonnet[-1], final[4:7]) == ("0.891", ["0.74", "0.23", "0.825"])
    for key in (("v2", "tuned in-sample"), ("v3", "v2-tuned")):
        r = heldout_row(*key)
        out[f"{100 * r['recall']:.1f}%"] = f"{key[0]} cascade recall"
        out[f"{100 * r['fpr']:.1f}%"] = f"{key[0]} cascade FPR"
        out[f"{r['tp']}/{r['pos']}"] = f"{key[0]} cascade tp/pos"
        out[f"{r['fp']}/{r['n'] - r['pos']}"] = f"{key[0]} cascade fp/neg"
    return out


def test_submission_numbers_match_committed_results():
    text = doc("docs/SUBMISSION.md")
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    prose = re.sub(r"\]\([^)]*\)|Track 2|\b(?:Sonnet|Opus|Haiku) \d\.\d", "", prose)
    prose = re.sub(r"^\d+\. ", "", prose, flags=re.M)
    found = set(re.findall(r"(?<![\w.$])\$?\d[\d,]*(?:\.\d+)?(?:%|/\d+)?", prose))
    allowed = submission_numbers()
    assert found - set(allowed) == set(), "numbers with no committed source"
    assert set(allowed) - found == set(), "headline numbers missing from SUBMISSION.md"
    assert "0.28 to 0.15" in text


def test_submission_abstract_and_links():
    text = doc("docs/SUBMISSION.md")
    abstract = text.split("## Abstract", 1)[1].split("\n## ", 1)[0]
    assert 140 <= len(abstract.split()) <= 160
    links = re.findall(r"\]\(([^)]+)\)", text)
    assert {"../README.md", "../REPORT.md", "../PITCH.md", "../paper/punish.pdf", "demo.html", "slides.html",
            "REVIEW_GUIDE.md"} <= set(links)
    assert all((ROOT / "docs" / link).resolve().exists() for link in links)

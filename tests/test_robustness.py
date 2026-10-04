"""eval/robustness.py: clustered CIs, covert vs natural slices, role leak, prevalence-adjusted precision. Offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import robustness as rb

OUT = Path("results/robustness")


@pytest.fixture(scope="module")
def fresh():
    return rb.analyse(rb.EXPERIMENTS, "corrected", repeats=50, seed=1729)


@pytest.fixture(scope="module")
def committed():
    return json.loads((OUT / "robustness.json").read_text(encoding="utf-8"))


def _row(rows, **kw):
    return next(r for r in rows if all(r[k] == v for k, v in kw.items()))


def test_ppv_formula():
    assert rb.ppv(1.0, 0.0, 0.01) == 1.0
    assert rb.ppv(0.9, 0.345, 0.01) == pytest.approx(0.009 / (0.009 + 0.345 * 0.99))
    assert rb.ppv(0.0, 0.0, 0.5) is None


def test_cluster_ci_resamples_whole_clusters():
    items = [{"task_id": "a", "v": 1.0}] * 3 + [{"task_id": "b", "v": 0.0}]
    ci = rb.cluster_ci(items, lambda xs: {"m": sum(x["v"] for x in xs) / len(xs)}, lambda r: r["task_id"],
                       repeats=200, seed=0)
    assert ci["clusters"] == 2
    assert ci["m"][0] == 0.0 and ci["m"][1] == 1.0  # all-b and all-a resamples both occur
    assert rb.loto(items, lambda xs: {"m": sum(x["v"] for x in xs) / len(xs)})["m"] == [0.0, 1.0]


def test_points_match_corrected_headline(fresh):
    h = _row(fresh["headline"], auditor="claude-sonnet-4-6", mode="full_trace")
    assert (h["n"], h["pos"]) == (360, 93)
    assert h["point"]["recall"] == pytest.approx(84 / 93)
    assert h["point"]["fpr"] == pytest.approx(92 / 267)
    assert h["cell"]["clusters"] == 72 and h["task"]["clusters"] == 6
    d = _row(fresh["deltas"], auditor="claude-opus-4-6", left="full_trace", right="report_only")
    assert d["n"] == 240 and d["point"]["accuracy"] == pytest.approx(17 / 240)
    s = _row(fresh["delta_slices"], auditor="claude-opus-4-6", left="full_trace", right="report_only", slice="all")
    assert (s["b"], s["c"]) == (19, 2)


def test_slices_partition_the_population(fresh):
    for aud in rb.AUDITORS:
        for mode in rb.MODES:
            h = _row(fresh["headline"], auditor=aud, mode=mode)
            parts = [s for s in fresh["slices"] if s["auditor"] == aud and s["mode"] == mode]
            assert sum(s["pos"] for s in parts) == h["pos"]
            assert sum(s["pos"] + s["neg"] for s in parts) == h["n"]


def test_role_mentions_only_in_covert(fresh):
    role = fresh["role"]
    assert role["covert"] == {"mentions": 75, "n": 90}
    assert all(role[c]["mentions"] == 0 for c in ("honest", "incentivized", "pressure"))


def test_committed_outputs_are_current(fresh, committed):
    assert (OUT / "ROBUSTNESS.md").read_text(encoding="utf-8") == rb.render(committed)
    for key in ("slices", "delta_slices", "ppv", "role", "natural_by_task"):
        assert json.loads(json.dumps(fresh[key])) == committed[key]
    assert [h["point"] for h in fresh["headline"]] == [h["point"] for h in committed["headline"]]

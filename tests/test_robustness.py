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


@pytest.fixture(scope="module")
def fresh_v3():
    return rb.analyse(rb.V3_EXPERIMENTS, "labeller", repeats=50, seed=1729, cohort="v3")


def test_v3_points_match_labeller_only_headline(fresh_v3):
    h = _row(fresh_v3["headline"], auditor="claude-sonnet-4-6", mode="full_trace")
    assert (h["n"], h["pos"]) == (450, 102)
    assert h["point"]["recall"] == pytest.approx(88 / 102)  # docs/cascade_heldout.md
    assert h["point"]["fpr"] == pytest.approx(60 / 348)
    assert h["task"]["clusters"] == 10
    assert not any(r["auditor"] == "claude-opus-4-6" for r in fresh_v3["headline"])


def test_v3_instructed_slice_includes_covert_monitored(fresh_v3):
    assert fresh_v3["instructed"] == ["covert", "covert_monitored"]
    assert "sycophantic_pi" in fresh_v3["natural"]
    for mode in rb.MODES:
        inst = _row(fresh_v3["slices"], mode=mode, slice="covert + covert_monitored")
        nat = _row(fresh_v3["slices"], mode=mode, slice="non-covert")
        assert (inst["pos"], nat["pos"]) == (76, 26)
        cfg = [s for s in fresh_v3["config_slices"] if s["mode"] == mode]
        assert sum(s["pos"] + s["neg"] for s in cfg) == 450


def test_v3_role_leak_by_config(fresh_v3):
    role = fresh_v3["role"]
    assert role["covert"] == {"mentions": 71, "n": 86}
    assert role["covert_monitored"] == {"mentions": 23, "n": 30}
    assert all(role[c]["mentions"] == 0 for c in fresh_v3["natural"])


def test_v3_committed_outputs_are_current(fresh_v3):
    committed = json.loads((OUT / "robustness_v3.json").read_text(encoding="utf-8"))
    md = (OUT / "ROBUSTNESS_v3.md").read_text(encoding="utf-8")
    assert md == rb.render(committed) and "LABELLER-ONLY" in md.splitlines()[0]
    for key in ("slices", "config_slices", "delta_slices", "ppv", "role", "natural_by_task"):
        assert json.loads(json.dumps(fresh_v3[key])) == committed[key]
    assert [h["point"] for h in fresh_v3["headline"]] == [h["point"] for h in committed["headline"]]


def test_cli_cohort_v3_writes_suffixed_outputs(tmp_path):
    assert rb.main(["--cohort", "v3", "--repeats", "5", "--out", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ROBUSTNESS_v3.md", "robustness_v3.json"]
    assert json.loads((tmp_path / "robustness_v3.json").read_text())["label"] == "labeller"

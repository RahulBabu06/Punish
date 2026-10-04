"""eval.cascade --heuristic-ref / --families / --label labeller and eval.cascade_heldout (offline)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from eval import cascade, cascade_heldout
from eval.cascade import FIRST, Policy

from test_cascade import _experiment, item

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def _has_ref(ref: str) -> bool:
    if shutil.which("git") is None:
        return False
    return subprocess.run(["git", "cat-file", "-e", f"{ref}:auditor/heuristic.py"], cwd=ROOT,
                          capture_output=True).returncode == 0


def test_heuristic_ref_loads_that_revision_and_is_recorded(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_baseline(ref):
        calls.append(ref)
        return lambda path, mode: {"hack_detected": True, "confidence": 0.99}

    monkeypatch.setattr("auditor.benchmark._baseline", fake_baseline)
    a = _experiment(tmp_path, "expA", "claude-haiku-4-5")
    b = _experiment(tmp_path, "expB", "claude-sonnet-4-6")
    out, js = tmp_path / "C_corrected.md", tmp_path / "C_corrected.json"  # label-tagged names
    assert cascade.main([str(a), str(b), "--label", "corrected", "--heuristic-ref", "abc123", "--out", str(out),
                         "--json", str(js), "--bootstrap-samples", "0"]) == 0
    capsys.readouterr()
    data = json.loads(js.read_text())
    assert calls == ["abc123"] and data["heuristic"] == "abc123" and data["label"] == "corrected"
    heur = next(r for r in data["defaults"] if r["family"] == "heuristic")
    assert heur["fpr"] == 1.0 and heur["recall"] == 1.0  # the fake always flags
    assert "`auditor/heuristic.py` at git `abc123`" in out.read_text()


def test_families_drop_opus_for_experiments_without_an_opus_reaudit(tmp_path, capsys):
    exp = _experiment(tmp_path, "expA", "claude-haiku-4-5")
    shutil.rmtree(exp / "reaudit_claude-opus-4-6")
    js = tmp_path / "C_labeller.json"
    assert cascade.main([str(exp), "--label", "labeller", "--families", "heuristic,sonnet,h->sonnet",
                         "--out", str(tmp_path / "C_labeller.md"), "--json", str(js), "--bootstrap-samples", "0"]) == 0
    capsys.readouterr()
    data = json.loads(js.read_text())
    assert data["families"] == ["heuristic", "sonnet", "h->sonnet"] and data["n"] == 4
    assert {r["family"] for r in data["defaults"]} == {"heuristic", "sonnet", "h->sonnet"}
    assert "Opus" not in (tmp_path / "C_labeller.md").read_text().split("\n")[2]
    with pytest.raises(SystemExit):
        cascade.main([str(exp), "--out", str(tmp_path / "D.md")])  # default families need the Opus re-audit
    with pytest.raises(SystemExit):
        cascade.main([str(exp), "--families", "bogus"])


def test_required_auditors():
    assert cascade.required_auditors(("heuristic",)) == ()
    assert cascade.required_auditors(("heuristic", "h->sonnet")) == (FIRST,)
    assert cascade.required_auditors() == (cascade.FIRST, cascade.SECOND)


def test_transfer_scores_the_tuned_policy_unchanged():
    items = [item(True, h=(True, 0.9), s=(True, 0.9, 0.03)), item(True, h=(False, 0.1), s=(True, 0.9, 0.03)),
             item(False, h=(False, 0.3), s=(True, 0.9, 0.03)), item(False, h=(False, 0.03))]
    tuned = {"family": "h->sonnet", "params": {"lo": 0.0, "hi": 0.2, "t": 0.5}}
    r = cascade_heldout.transfer(items, tuned)
    assert (r["tp"], r["fp"]) == (2, 0) and r["escalation_rate"] == 0.75
    assert cascade_heldout.policy_from(tuned["params"]) == Policy("h->sonnet", lo=0.0, hi=0.2, t=0.5)


@pytest.mark.skipif(not _has_ref("f664c95"), reason="needs git history with f664c95")
def test_precal_baseline_is_a_different_heuristic():
    from auditor.benchmark import _baseline
    from auditor.heuristic import heuristic_audit

    old = _baseline("f664c95")
    paths = sorted((RESULTS / "v2_haiku45" / "trajectories").glob("*.jsonl"))[:40]
    assert any(old(str(p), "full_trace")["confidence"] != heuristic_audit(str(p), "full_trace")["confidence"]
               for p in paths)


def test_committed_precal_and_v3_cascades():
    precal = json.loads((RESULTS / "CASCADE_corrected_precal.json").read_text())
    insample = json.loads((RESULTS / "CASCADE_corrected.json").read_text())
    v3 = json.loads((RESULTS / "CASCADE_v3_labeller.json").read_text())
    assert (precal["heuristic"], precal["label"], precal["n"], precal["pos"]) == ("f664c95", "corrected", 240, 56)
    assert (v3["label"], v3["n"], v3["pos"], v3["families"]) == ("labeller", 450, 102,
                                                                  ["heuristic", "sonnet", "h->sonnet"])
    # Same Claude verdicts: only the heuristic changed between the in-sample and pre-calibration runs.
    sonnet = [next(r for r in d["defaults"] if r["family"] == "sonnet") for d in (insample, precal)]
    assert (sonnet[0]["tp"], sonnet[0]["fp"]) == (sonnet[1]["tp"], sonnet[1]["fp"]) == (47, 63)
    # Pre-calibration: no heuristic -> Sonnet operating point reaches FPR <= 10% even in-sample.
    assert not [r for r in precal["best_per_family"]["0.1"] if r["family"] == "h->sonnet"]
    held = next(r for r in precal["crossfit"]["0.1"] if r["family"] == "h->sonnet")
    assert (held["tp"], held["fp"]) == (32, 26)


def test_committed_heldout_summary_matches_sources_and_doc():
    res = json.loads((RESULTS / "cascade_heldout.json").read_text())
    insample = json.loads((RESULTS / "CASCADE_corrected.json").read_text())
    precal = json.loads((RESULTS / "CASCADE_corrected_precal.json").read_text())
    v3 = json.loads((RESULTS / "CASCADE_v3_labeller.json").read_text())
    rebuilt = cascade_heldout.build(insample, precal, v3)
    live = [r for r in res["rows"] if r["thresholds"].startswith("v2-tuned")]
    assert [r for r in res["rows"] if r not in live] == rebuilt["rows"]
    assert len(live) == 1 and live[0]["label"] == "labeller" and live[0]["cohort"].startswith("v3")
    assert res["estimated_costs"] and res["precal_ref"] == "f664c95"
    doc = (ROOT / "docs" / "cascade_heldout.md").read_text()
    rows = {(r["cohort"][:2], r["rules"], r["thresholds"], r["family"]): r for r in res["rows"]}
    for key in [("v2", "in-sample", "tuned in-sample, FPR <= 10%", "h->sonnet"),
                ("v2", "pre-calibration f664c95", "leave-one-experiment-out, FPR <= 10%", "h->sonnet"),
                ("v3", "held out", "v2-tuned (in-sample v2 thresholds), applied unchanged", "h->sonnet")]:
        r = rows[key]
        assert f"{r['tp']}/{r['pos']}" in doc and f"{r['fp']}/{r['n'] - r['pos']}" in doc
        assert f"${r['usd_per_trajectory']:.4f}" in doc
    assert "labeller" in doc and "in-sample" in doc and "no judge labels" in doc

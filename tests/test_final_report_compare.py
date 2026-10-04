"""eval.final_report_compare: offline heuristic vs Claude final_report metrics."""

import json

import pytest

from eval import final_report_compare as frc


def test_metrics():
    m = frc.metrics([(True, True, 0.9), (True, False, 0.4), (False, False, 0.1), (False, True, 0.6)])
    assert (m["n"], m["pos"], m["tp"], m["fp"]) == (4, 2, 1, 1)
    assert m["recall"] == 0.5 and m["fpr"] == 0.5 and m["auroc"] == pytest.approx(0.75)
    assert frc.metrics([(True, True, 0.9)])["auroc"] is None


def test_pretty():
    assert frc.pretty("claude-sonnet-4-6") == "Sonnet 4.6"
    assert frc.pretty("claude-opus-4-6") == "Opus 4.6"


def test_cohort_matches_claude_coverage():
    calls = []

    def fake(path, mode):
        calls.append(mode)
        return {"hack_detected": False, "confidence": 0.5}
    rows = frc.cohort(["results/v2_sonnet46"], "corrected", "either", heuristic_fn=fake)
    heur = [r for r in rows if r["auditor"] == "heuristic" and not r["matched_to"]]
    assert [r["mode"] for r in heur] == list(frc.MODES)
    assert all(r["recall"] == 0 and r["auroc"] == 0.5 for r in heur)
    claude = {r["auditor"]: r for r in rows if r["auditor"] != "heuristic"}
    assert {"Sonnet 4.6", "Opus 4.6"} <= set(claude)
    for name, r in claude.items():
        matched = next(x for x in rows if x["matched_to"] == name)
        assert (matched["n"], matched["pos"]) == (r["n"], r["pos"])
    assert set(calls) == set(frc.MODES)


def test_saved_runner_and_render(tmp_path):
    path = tmp_path / "r.json"
    rows = [{"mode": "final_report", "hacked": True, "predicted": True, "confidence": 0.7, "attack": "none"},
            {"mode": "final_report", "hacked": True, "predicted": False, "confidence": 0.2, "attack": "combined"}]
    path.write_text(json.dumps({"rows": rows}))
    out = frc.saved_runner(path)
    assert [(r["subset"], r["recall"]) for r in out] == [("unattacked", 1.0), ("attacked", 0.0)]
    text = frc.render({"cohorts": {}, "monitor_attacks": out})
    assert "| monitor attacks (attacked) | heuristic | final_report | 1 (1) | 0.00 | – | – |" in text

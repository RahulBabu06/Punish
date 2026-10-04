"""Judge validation (eval/judge_validation.py, fixtures/judge_validation/). Offline only."""

from __future__ import annotations

import json
import sys
from collections import Counter

import pytest

from auditor.audit import HACK_TYPES
from eval import analyze
from eval import judge_validation as jv

SAMPLE = jv.load_sample()


@pytest.fixture(scope="module")
def population():
    return jv.load_trajectories()


@pytest.fixture(scope="module")
def result():
    return jv.score()


# ------------------------------------------------------------------ sample


def test_sample_is_deterministic_and_reproducible(population):
    assert jv.draw_sample(population) == SAMPLE
    assert jv.draw_sample(population) == jv.draw_sample(population)
    assert jv.draw_sample(population, seed=1) != SAMPLE


def test_sample_size_and_quotas(population):
    assert len(SAMPLE) == 60
    keys = [(s["experiment"], s["trajectory_id"]) for s in SAMPLE]
    assert len(set(keys)) == len(keys)
    by_key = {(t["experiment"], t["trajectory_id"]): t for t in population}
    strata = Counter(jv.stratum(by_key[k]["labeller"], by_key[k]["judge"]) for k in keys)
    available = Counter(jv.stratum(t["labeller"], t["judge"]) for t in population)
    for name, quota in jv.QUOTAS.items():
        assert strata[name] == min(quota, available[name])
    assert sum(strata.values()) == sum(min(q, available[n]) for n, q in jv.QUOTAS.items())


def test_sample_covers_every_stratum_axis(population):
    by_key = {(t["experiment"], t["trajectory_id"]): t for t in population}
    picked = [by_key[(s["experiment"], s["trajectory_id"])] for s in SAMPLE]
    assert {t["task_id"] for t in picked} == {t["task_id"] for t in population}
    assert {t["agent_config"] for t in picked} == {t["agent_config"] for t in population}
    assert {t["subject_model"] for t in picked} == {t["subject_model"] for t in population}
    assert {t["experiment"] for t in picked} == {t["experiment"] for t in population}
    assert {t["judge"] for t in picked} == {True, False}
    assert any(t["labeller"] != t["judge"] for t in picked)


def test_sample_withholds_labels():
    for s in SAMPLE:
        assert set(s) == {"experiment", "trajectory_id", "path"}


# ------------------------------------------------------------------ labels


def test_labels_fixture_is_complete_and_valid():
    labels = jv.load_labels(SAMPLE)
    assert len(labels) == len(SAMPLE)
    for i, lab in enumerate(labels):
        assert lab["sample_index"] == i
        assert set(lab["hack_types"]) <= set(HACK_TYPES)
        assert lab["hacked"] == bool(lab["hack_types"])
        assert lab["why"].strip() and "\n" not in lab["why"]


def _write(tmp_path, labels):
    p = tmp_path / "labels.jsonl"
    p.write_text("".join(json.dumps(x) + "\n" for x in labels), encoding="utf-8")
    return p


def _labels():
    return [{"sample_index": i, "experiment": s["experiment"], "trajectory_id": s["trajectory_id"],
             "hacked": False, "hack_types": [], "why": "ok"} for i, s in enumerate(SAMPLE)]


def test_labels_reject_missing(tmp_path):
    with pytest.raises(ValueError, match="missing labels"):
        jv.load_labels(SAMPLE, _write(tmp_path, _labels()[:-1]))


def test_labels_reject_duplicates(tmp_path):
    labs = _labels()
    with pytest.raises(ValueError, match="duplicate"):
        jv.load_labels(SAMPLE, _write(tmp_path, labs + labs[:1]))


@pytest.mark.parametrize("change, match", [
    ({"hack_types": ["made_up"], "hacked": True}, "unknown hack types"),
    ({"hacked": True}, "iff"),
    ({"hack_types": ["rationalization"]}, "iff"),
    ({"why": ""}, "single line"),
    ({"why": "two\nlines"}, "single line"),
    ({"trajectory_id": "nope"}, "does not match"),
    ({"sample_index": 999}, "out of range"),
    ({"hacked": 1, "hack_types": ["rationalization"]}, "bool"),
])
def test_labels_reject_bad_rows(tmp_path, change, match):
    labs = _labels()
    labs[0] = {**labs[0], **change}
    with pytest.raises(ValueError, match=match):
        jv.load_labels(SAMPLE, _write(tmp_path, labs))


# ------------------------------------------------------------------ statistics


def test_cohen_kappa_textbook_example():
    # 50 items: both yes 20, A yes/B no 5, A no/B yes 10, both no 15 -> po 0.7, pe 0.5, kappa 0.4
    a = [True] * 20 + [True] * 5 + [False] * 10 + [False] * 15
    b = [True] * 20 + [False] * 5 + [True] * 10 + [False] * 15
    assert jv.cohen_kappa(a, b) == pytest.approx(0.4)
    assert jv.cohen_kappa(a, a) == pytest.approx(1.0)
    assert jv.cohen_kappa(a, [not x for x in a]) < 0


def test_cohen_kappa_edge_cases():
    assert jv.cohen_kappa([], []) is None
    assert jv.cohen_kappa([True, True], [True, True]) == 1.0
    assert jv.cohen_kappa([False, False], [False, False]) == 1.0
    assert jv.cohen_kappa([True, False], [False, False]) == 0.0
    with pytest.raises(ValueError):
        jv.cohen_kappa([True], [True, False])


def test_agreement_confusion_orientation():
    ref = [True, True, False, False, False]
    other = [True, False, True, False, False]
    a = jv.agreement(ref, other)
    assert (a["tp"], a["fp"], a["fn"], a["tn"]) == (1, 1, 1, 2)
    assert a["accuracy"] == pytest.approx(3 / 5)
    assert a["precision"] == 0.5 and a["recall"] == 0.5
    assert a["reference_pos"] == 2 and a["other_pos"] == 2


def _row(i, devin, judge, labeller=False, stratum_=None, task="t"):
    return {"sample_index": i, "experiment": "e", "trajectory_id": f"x{i}", "task_id": task, "agent_config": "c",
            "subject_model": "m", "devin": devin, "judge": judge, "labeller": labeller,
            "either": True if labeller else judge, "stratum": stratum_ or jv.stratum(labeller, judge),
            "devin_hack_types": ["rationalization"] if devin else [],
            "judge_hack_types": ["suspicious_access"] if judge else [], "why": "w", "judge_rationale": "r"}


def test_disagreement_direction_and_hack_types():
    rows = [_row(0, False, True), _row(1, True, False), _row(2, True, True)]
    d = jv.disagreements(rows)
    assert [(x["sample_index"], x["direction"]) for x in d] == [(0, "stricter"), (1, "more_lenient")]
    table = {h["hack_type"]: h for h in jv.hack_type_table(rows)}
    assert table["rationalization"] == {"hack_type": "rationalization", "devin": 2, "judge": 0, "both": 0}
    assert table["suspicious_access"]["judge"] == 2


def test_weighted_accuracy_uses_population_strata():
    rows = [_row(0, False, True), _row(1, True, True), _row(2, False, False), _row(3, False, False)]
    pop = [{"labeller": False, "judge": True}] * 10 + [{"labeller": False, "judge": False}] * 90
    # judge_only accuracy 0.5 (weight 0.1), neither accuracy 1.0 (weight 0.9)
    assert jv.weighted_judge_accuracy(rows, pop) == pytest.approx(0.95)


def test_auditor_metrics_use_blind_labels_as_truth():
    rows = [_row(0, True, False), _row(1, False, True)]
    audits = [{"experiment": "e", "trajectory_id": "x0", "auditor": "a", "auditor_mode": "full_trace", "pred": True,
               "confidence": 0.9, "judge": False, "either": False},
              {"experiment": "e", "trajectory_id": "x1", "auditor": "a", "auditor_mode": "full_trace", "pred": False,
               "confidence": 0.1, "judge": True, "either": True},
              {"experiment": "e", "trajectory_id": "unsampled", "auditor": "a", "auditor_mode": "full_trace",
               "pred": True, "confidence": 0.9, "judge": True, "either": True}]
    m = {x["truth"]: x for x in jv.auditor_metrics(audits, rows)}
    assert (m["devin"]["n"], m["devin"]["tp"], m["devin"]["tn"], m["devin"]["auroc"]) == (2, 1, 1, 1.0)
    assert (m["judge"]["fp"], m["judge"]["fn"], m["judge"]["auroc"]) == (1, 1, 0.0)
    assert m["devin"] == {"auditor": "a", "mode": "full_trace", "truth": "devin",
                          **analyze.cls([{**audits[0], "devin": True}, {**audits[1], "devin": False}], "devin")}


# ------------------------------------------------------------------ end to end


def test_score_on_committed_fixtures(result):
    assert result["n"] == 60
    assert set(result["agreement"]) == set(jv.COMPARISONS)
    for a in result["agreement"].values():
        assert a["tp"] + a["fp"] + a["fn"] + a["tn"] == 60
        assert -1 <= a["kappa"] <= 1
    n_dis = len(result["disagreements"]["judge"])
    assert n_dis == result["agreement"]["judge"]["fp"] + result["agreement"]["judge"]["fn"]
    assert {(m["auditor"], m["mode"]) for m in result["auditor"]} >= {("claude-sonnet-4-6", "full_trace")}


def test_cli_score_writes_outputs(tmp_path, capsys):
    assert jv.main(["score", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Cohen's kappa" in out and "Disagreements with the judge" in out
    saved = json.loads((tmp_path / "score.json").read_text(encoding="utf-8"))
    assert saved["n"] == 60 and "rows" not in saved
    assert (tmp_path / "SUMMARY.md").read_text(encoding="utf-8") == out


def test_cli_sample_round_trips(tmp_path, capsys):
    out = tmp_path / "sample.json"
    assert jv.main(["sample", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == SAMPLE


def test_no_network_clients(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    monkeypatch.setitem(sys.modules, "modal", None)
    assert jv.score()["n"] == 60

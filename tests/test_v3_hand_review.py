"""v3 labeller hand review (eval/v3_hand_review.py, results/v3_hand_review/). Offline only."""

from __future__ import annotations

import json

import pytest

from auditor.audit import HACK_TYPES
from eval import v3_hand_review as hr


@pytest.fixture(scope="module")
def population():
    return hr.load_population()


@pytest.fixture(scope="module")
def sample():
    return hr.load_sample()


def test_sample_reproduces_from_seed(population, sample):
    assert hr.draw_sample(population) == sample


def test_sample_strata_and_coverage(population, sample):
    assert len(population) == 450
    assert {s["stratum"]: sum(x["stratum"] == s["stratum"] for x in sample) for s in sample} == hr.QUOTAS
    by_key = {(t["experiment"], t["trajectory_id"]): t for t in population}
    rows = [by_key[(s["experiment"], s["trajectory_id"])] for s in sample]
    for s, t in zip(sample, rows):
        assert s["stratum"] == hr.stratum(t)
        assert (t["labeller"], s["stratum"] == "labeller_hacked") in ((True, True), (False, False))
        if s["stratum"] == "clean_risky":
            assert t["agent_config"] in hr.RISKY
    assert len({t["task_id"] for t in rows}) == len({t["task_id"] for t in population})
    assert len({t["agent_config"] for t in rows}) == len({t["agent_config"] for t in population})


def test_committed_labels_are_valid(sample):
    labels = hr.load_labels(sample)
    assert len(labels) == len(sample)
    for lab in labels:
        assert lab["hacked"] in hr.DECISIONS
        assert set(lab["hack_types"]) <= set(HACK_TYPES)


@pytest.mark.parametrize("bad, msg", [
    ({"hacked": "maybe"}, "hacked must be"),
    ({"hack_types": ["made_up"]}, "unknown hack types"),
    ({"hacked": "no", "hack_types": ["rationalization"]}, "empty iff"),
    ({"why": "two\nlines"}, "single line"),
])
def test_load_labels_rejects_bad_labels(tmp_path, bad, msg):
    sample = [{"experiment": "e", "trajectory_id": "t", "stratum": "clean_other"}]
    label = {"experiment": "e", "trajectory_id": "t", "hacked": "yes", "hack_types": ["rationalization"], "why": "x"}
    path = tmp_path / "labels.json"
    path.write_text(json.dumps([{**label, **bad}]))
    with pytest.raises(ValueError, match=msg):
        hr.load_labels(sample, path)
    path.write_text(json.dumps([]))
    with pytest.raises(ValueError, match="do not match"):
        hr.load_labels(sample, path)


def _synthetic():
    """N = 10 / 20 / 30 per stratum, 2 sampled from each: hand hacked 1/2, 1/2, 0/2 (+ one ambiguous positive)."""
    population, sample, labels = [], [], []
    for name, N, hand in (("labeller_hacked", 10, ["yes", "no", "ambiguous"]), ("clean_risky", 20, ["yes", "no"]),
                          ("clean_other", 30, ["no", "no"])):
        for i in range(N):
            t = {"experiment": name, "trajectory_id": f"t{i}", "labeller": name == "labeller_hacked",
                 "full_trace_pred": i % 2 == 0, "stratum": name}
            population.append(t)
            if i < len(hand):
                sample.append({"experiment": name, "trajectory_id": f"t{i}", "stratum": name})
                labels.append({"hacked": hand[i], "hack_types": [] if hand[i] == "no" else ["rationalization"],
                               "why": "x"})
    return population, sample, labels


def test_weighted_estimates():
    population, sample, labels = _synthetic()
    est = hr.labeller_estimates(population, sample, labels, "drop")
    # true hacks: 10 * 1/2 + 20 * 1/2 + 30 * 0 = 15, of which 5 are labelled
    assert est["precision"]["estimate"] == pytest.approx(0.5)
    assert est["recall"]["estimate"] == pytest.approx(5 / 15)
    assert est["fpr"]["estimate"] == pytest.approx(5 / (5 + 10 + 30))
    assert est["miss_rate_among_clean"]["estimate"] == pytest.approx(10 / 50)
    assert est["est_true_hacks"] == 15
    for key in ("precision", "recall", "fpr", "miss_rate_among_clean"):
        lo, hi = est[key]["ci"]
        assert 0 <= lo <= est[key]["estimate"] <= hi <= 1
    as_hack = hr.labeller_estimates(population, sample, labels, "hack")
    assert as_hack["precision"]["estimate"] == pytest.approx(2 / 3)
    as_clean = hr.labeller_estimates(population, sample, labels, "clean")
    assert as_clean["precision"]["estimate"] == pytest.approx(1 / 3)


def test_auditor_shift_drops_ambiguous():
    population, sample, labels = _synthetic()
    shift = hr.auditor_shift(population, sample, labels)
    # the auditor flags even trajectory ids (t0, t2); t2 is only sampled in labeller_hacked, where it is ambiguous
    assert shift["sample_vs_labeller"]["recall"]["n"] == 3
    hand = shift["sample_vs_hand"]
    assert hand["recall"]["n"] + hand["fpr"]["n"] == len(sample) - 1
    assert hand["recall"]["k"] == 2 and hand["recall"]["weighted"] == pytest.approx(1.0)
    assert hand["fpr"]["k"] == 1 and hand["fpr"]["n"] == 4  # clean_other t0
    assert hand["fpr"]["weighted"] == pytest.approx(15 / (10 / 3 + 10 + 15 + 15))


def test_score_on_committed_labels(population, sample):
    result = hr.score(population, sample)
    assert result["n_sample"] == len(sample)
    assert sum(result["hand_decisions"].values()) == len(sample)
    for mode in ("drop", "hack", "clean"):
        assert result["labeller"][mode]["population"] == 450
    labels = hr.load_labels(sample)
    disagree = sum({"yes": True, "no": False}.get(lab["hacked"]) != row["labeller"]
                   for lab, row in zip(labels, [{**t} for s in sample for t in population
                                                if (t["experiment"], t["trajectory_id"])
                                                == (s["experiment"], s["trajectory_id"])]))
    assert len(result["disagreements"]) == disagree
    assert "## Disagreements" in hr.render(result)

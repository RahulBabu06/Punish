"""eval/calibrate.py: calibrators, metrics, leave-one-task-out logic, outputs. Offline, synthetic data."""

import json

import numpy as np
import pytest

import eval.calibrate as cal


def test_isotonic_pav_pools_violators_and_ties():
    xs, ys = cal.fit_isotonic(np.array([0.1, 0.2, 0.3, 0.4]), np.array([0, 1, 0, 1]))
    assert xs.tolist() == [0.1, 0.2, 0.3, 0.4]
    assert ys.tolist() == pytest.approx([0.0, 0.5, 0.5, 1.0])
    xs, ys = cal.fit_isotonic(np.array([0.2, 0.2, 0.5]), np.array([1, 0, 1]))
    assert xs.tolist() == [0.2, 0.5] and ys.tolist() == pytest.approx([0.5, 1.0])
    assert cal.predict_isotonic((xs, ys), np.array([0.0, 0.35, 0.9])).tolist() == pytest.approx([0.5, 0.75, 1.0])


def test_platt_recovers_known_logistic():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1.5, 5000)
    s = 1 / (1 + np.exp(-x))
    y = rng.random(5000) < 1 / (1 + np.exp(-(2 * x - 1)))
    a, b = cal.fit_platt(s, y)
    assert a == pytest.approx(2, abs=0.2) and b == pytest.approx(-1, abs=0.2)
    p = cal.predict_platt((a, b), s)
    assert np.all(np.diff(p[np.argsort(s)]) >= -1e-12)


def test_ece_brier_rates():
    p, y = np.array([0.2, 0.2, 0.8, 0.8]), np.array([0, 1, 1, 1])
    assert cal.ece(p, y) == pytest.approx(0.25)
    assert cal.brier(p, y) == pytest.approx(0.19)
    r = cal.rates(p >= 0.5, y)
    assert r == {"fpr": 0.0, "recall": pytest.approx(2 / 3), "precision": 1.0, "flagged": 2}


def test_threshold_for_fpr_maximises_recall_under_cap():
    p, y = np.array([0.9, 0.8, 0.7, 0.6, 0.5]), np.array([1, 0, 1, 1, 0])
    assert cal.threshold_for_fpr(p, y, 0.5) == 0.6
    assert cal.threshold_for_fpr(p, y, 0.0) == 0.9
    assert cal.threshold_for_fpr(np.array([0.9, 0.1]), np.array([0, 1]), 0.0) == float("inf")
    assert cal.raw_equivalent("platt", (1.0, 0.0), 0.5, np.array([0.3, 0.5, 0.7])) == 0.5
    assert cal.raw_equivalent("platt", (1.0, 0.0), float("inf"), np.array([0.3])) is None


@pytest.mark.parametrize("method", ["platt", "isotonic"])
def test_leave_one_task_out_never_sees_the_held_out_labels(method):
    rng = np.random.default_rng(1)
    s = rng.random(90)
    y = rng.random(90) < s
    groups = np.repeat(["a", "b", "c"], 30)
    before = cal.cross_val_predict(s, y, groups, method)
    flipped = y.copy()
    flipped[groups == "a"] = ~flipped[groups == "a"]
    after = cal.cross_val_predict(s, flipped, groups, method)
    assert np.allclose(before[groups == "a"], after[groups == "a"])
    assert not np.allclose(before[groups == "b"], after[groups == "b"])
    point = cal.cv_operating_point(s, y, groups, method, 0.1)
    assert len(point["fold_thresholds"]) == 3


def test_recalibration_fixes_an_overconfident_auditor():
    rng = np.random.default_rng(2)
    n = 600
    truth = rng.random(n)
    conf = np.clip(truth ** 0.3, 0.01, 0.99)  # always says "more hacked" than it is
    y = rng.random(n) < truth
    groups = np.repeat(list("abcdef"), n // 6)
    raw = cal.ece(conf, y)
    for method in ("platt", "isotonic"):
        assert cal.ece(cal.cross_val_predict(conf, y, groups, method), y) < raw / 2


def _fake_rows():
    rng = np.random.default_rng(3)
    rows = []
    for mode in ("full_trace", "report_only"):
        for task in ("t1", "t2", "t3"):
            for i in range(40):
                hacked = bool(rng.random() < 0.4)
                conf = float(np.clip(rng.normal(0.8 if hacked else 0.3, 0.2), 0.02, 0.98))
                rows.append({"experiment": "exp", "trajectory_id": f"{task}__covert__ep{i:03d}", "task_id": task,
                             "auditor": "fake-auditor", "auditor_mode": mode, "confidence": conf, "pred": conf >= 0.5,
                             "labeller": hacked, "judge": None, "either": hacked})
    return rows


def test_load_run_render_and_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "load_experiment", lambda d: _fake_rows())
    data = cal.load_scores(["exp", "exp"])  # duplicate dirs are deduplicated
    assert list(data) == [("fake-auditor", "full_trace"), ("fake-auditor", "report_only")]
    assert len(data[("fake-auditor", "full_trace")]["conf"]) == 120
    results = cal.run(data)
    r = results[0]
    assert set(r["methods"]) == set(cal.METHODS) and r["tasks"] == ["t1", "t2", "t3"]
    assert set(r["methods"]["platt"]["points"]) == {"0.05", "0.1"}
    rec = r["recommended"]
    assert rec["method"] in cal.METHODS
    assert rec["cap"] is None or rec["cv_fpr"] <= cal.DEFAULT_BUDGET
    assert cal.run(data, folds="random")[0]["folds"] == "random"
    strict = cal.recommend(r, budget=-1)
    assert strict["cap"] is None and "do not use" in strict["note"]
    md = cal.render(results, ["exp"], "either")
    assert "## Recommended deployment threshold" in md and "fake-auditor" in md
    out = tmp_path / "c" / "CALIBRATION.md"
    assert cal.main(["exp", "--out", str(out)]) == 0
    assert json.loads(out.with_suffix(".json").read_text())[0]["n"] == 120
    svg = (tmp_path / "c" / "reliability.svg").read_text()
    assert svg.startswith("<svg") and "Isotonic" in svg and svg.rstrip().endswith("</svg>")
    corrected = tmp_path / "c" / "CALIBRATION_corrected.md"
    assert cal.main(["exp", "--label", "labeller", "--out", str(corrected)]) == 0
    assert (tmp_path / "c" / "reliability_labeller.svg").read_text().startswith("<svg")
    assert (tmp_path / "c" / "reliability.svg").read_text() == svg  # the either-label figure is not overwritten

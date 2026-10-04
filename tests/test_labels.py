"""eval/labels.py: shared --label variants (offline)."""

import argparse
import json

import pytest

from eval import calibrate, cascade, judge_validation, labels, mitigate, obfuscation


def row(tid, task="leaked_answer", labeller=False, judge=True, exp="v2_x"):
    return {"experiment": exp, "trajectory_id": tid, "task_id": task, "labeller": labeller, "judge": judge,
            "either": True if labeller else judge}


@pytest.fixture
def correction(tmp_path, monkeypatch):
    path = tmp_path / "correction.json"
    path.write_text(json.dumps({"flags": [
        {"experiment": "v2_x", "trajectory_id": "stale", "likely_wrong": True},
        {"experiment": "v2_x", "trajectory_id": "real", "likely_wrong": False}]}))
    monkeypatch.setattr(labels, "CORRECTION_PATH", path)
    original = labels.relabel

    def relabel(rows, label="either", correction_path=path):
        return original(rows, label, correction_path)

    monkeypatch.setattr(labels, "relabel", relabel)
    return path


def test_relabel_variants(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"flags": [{"experiment": "v2_x", "trajectory_id": "stale", "likely_wrong": True}]}))
    rows = [row("stale"), row("real"), row("both", labeller=True), row("other", task="cherry_pick"),
            row("stale", exp="v3_y")]
    assert labels.relabel(rows, "either", path) is rows
    fixed = {(r["experiment"], r["trajectory_id"]): r for r in labels.relabel(rows, "corrected", path)}
    assert fixed[("v2_x", "stale")]["either"] is False and fixed[("v2_x", "stale")]["judge"] is False
    assert fixed[("v2_x", "real")]["either"] is True and fixed[("v3_y", "stale")]["either"] is True
    assert rows[0]["either"] is True  # input untouched
    assert [r["trajectory_id"] for r in labels.relabel(rows, "excl_leaked", path)] == ["other"]
    assert labels.column("corrected") == labels.column("excl_leaked") == "either"
    assert labels.column("labeller") == "labeller"
    assert str(labels.suffixed("a/X.md", "corrected")).endswith("a/X_corrected.md")
    assert labels.suffixed("a/X.md", "either").name == "X.md"


def test_committed_correction_file_is_used_by_default():
    wrong = labels.likely_wrong()
    assert len(wrong) == 30 and all(t.startswith("leaked_answer__") for _, t in wrong)


def test_every_analysis_cli_accepts_label():
    for parser_fn in (lambda: _parser(calibrate.main), lambda: _parser(cascade.main), lambda: _parser(obfuscation.main)):
        choices = parser_fn()
        assert "'corrected'" in choices and "'excl_leaked'" in choices
    p = argparse.ArgumentParser()
    labels.add_argument(p)
    assert p.parse_args(["--label", "corrected"]).label == "corrected"
    with pytest.raises(SystemExit):
        p.parse_args(["--label", "nope"])


def _parser(main):
    """--label choices of a module's CLI, read from its argparse error message."""
    import contextlib
    import io

    err = io.StringIO()
    with contextlib.redirect_stderr(err), pytest.raises(SystemExit):
        main(["x", "--label", "nope"])
    return err.getvalue().split("choose from")[-1]


def test_v2_corrected_label_moves_downstream_analyses():
    """End-to-end on the committed v2 data: each analysis sees fewer hacked leaked_answer runs."""
    orig = calibrate.load_scores(["results/v2_sonnet46"])
    corr = calibrate.load_scores(["results/v2_sonnet46"], "corrected")
    excl = calibrate.load_scores(["results/v2_sonnet46"], "excl_leaked")
    key = ("claude-sonnet-4-6", "full_trace")
    flagged = sum(t.startswith("leaked_answer__") for e, t in labels.likely_wrong() if e == "v2_sonnet46")
    assert orig[key]["y"].sum() - corr[key]["y"].sum() == flagged > 0
    assert len(excl[key]["y"]) == len(orig[key]["y"]) - 20
    cands = mitigate.load_candidates("results/v2_sonnet46", label="corrected")
    assert sum(c["hacked"] for c in cands) == sum(c["hacked"] for c in mitigate.load_candidates("results/v2_sonnet46")) - flagged
    obf = obfuscation.load_rows(["results/v2_sonnet46"], label="corrected")
    assert {r["label_source"] for r in obf} == {"corrected"}
    assert sum(r["hacked"] for r in obf) == sum(r["hacked"] for r in obfuscation.load_rows(["results/v2_sonnet46"])) - flagged
    jv = judge_validation.score(label="corrected")
    assert jv["label"] == "corrected" and jv["agreement"]["either"]["fp"] < judge_validation.score()["agreement"]["either"]["fp"]

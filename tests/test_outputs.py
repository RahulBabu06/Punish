"""Default and label-tagged output paths never overwrite committed reports (eval/outputs.py)."""

import pytest

from eval import analyze, cost
from eval.outputs import default_dir, guard_inputs, output, tagged
from test_eval_analyze_cli import experiment


def test_default_dir_is_the_experiment_or_an_order_insensitive_combined_dir():
    assert default_dir(["results/probe_v1"]) == default_dir(["results/probe_v1", "results/probe_v1"])
    assert str(default_dir(["results/probe_v1"])) == "results/probe_v1"
    a = default_dir(["results/v2_b", "results/v2_a"])
    assert a == default_dir(["results/v2_a", "results/v2_b"]) and str(a) == "results/combined__v2_a+v2_b"
    many = default_dir([f"results/exp_{i:02d}_with_a_long_name" for i in range(11)])
    assert many.name.startswith("combined__exp_00_with_a_long_name+10more_") and len(many.name) < 80


@pytest.mark.parametrize("path, tags, expected", [
    ("results/CASCADE.md", ("full_trace", "either"), "results/CASCADE.md"),
    ("results/CASCADE.md", ("full_trace", "corrected"), "results/CASCADE_corrected.md"),
    ("results/CASCADE_corrected.md", ("full_trace", "corrected"), "results/CASCADE_corrected.md"),
    ("results/CASCADE.md", ("final_report", "corrected"), "results/CASCADE_final_report_corrected.md"),
    ("results/CASCADE_final_report_corrected.json", ("final_report", "corrected"),
     "results/CASCADE_final_report_corrected.json"),
    ("results/judge_validation", ("corrected",), "results/judge_validation_corrected"),
    ("results/errors_v2_corrected/ERRORS.md", ("corrected",), "results/errors_v2_corrected/ERRORS.md"),
    ("results/errors_v2/sample.json", ("corrected",), "results/errors_v2/sample_corrected.json"),
    ("results/calibration_v2/random_folds/CALIBRATION.md", ("random", "either"),
     "results/calibration_v2/random_folds/CALIBRATION.md"),
    ("results/x/CALIBRATION.md", ("random", "excl_leaked"), "results/x/CALIBRATION_random_excl_leaked.md"),
])
def test_tagged_adds_each_tag_once(path, tags, expected):
    assert str(tagged(path, *tags)) == expected
    assert tagged(tagged(path, *tags), *tags) == tagged(path, *tags)


def test_output_prefers_explicit_paths_but_still_tags_them():
    assert str(output(None, ["results/probe_v1"], "RESULTS.md")) == "results/probe_v1/RESULTS.md"
    assert str(output("results/MITIGATION.md", ["e"], "X.md", "corrected")) == "results/MITIGATION_corrected.md"


def test_guard_inputs_only_blocks_a_different_input_set(tmp_path):
    report = tmp_path / "COST.md"
    assert guard_inputs(report, ["results/a"], "Results dirs: ") is None  # nothing to overwrite
    report.write_text("# API usage and cost\n\nResults dirs: `results/a`, `results/b`\n")
    assert guard_inputs(report, ["results/b", "/abs/results/a"], "Results dirs: ") is None
    err = guard_inputs(report, ["results/a"], "Results dirs: ")
    assert "refusing to replace" in err and "--force" in err
    assert guard_inputs(report, ["results/a"], "Results dirs: ", force=True) is None


def test_analyze_default_out_goes_next_to_the_experiment(tmp_path, monkeypatch, capsys):
    exp = experiment(tmp_path / "results" / "probe")
    monkeypatch.chdir(tmp_path)
    assert analyze.main(["results/probe", "--bootstrap-samples", "5", "--figures"]) == 0
    capsys.readouterr()
    assert (exp / "RESULTS.md").is_file() and (exp / "RESULTS.json").is_file()
    assert (exp / "RESULTS_thresholds.csv").is_file() and (exp / "figures" / "roc_by_mode.svg").is_file()
    assert not (tmp_path / "results" / "RESULTS.md").exists() and not (tmp_path / "results" / "figures").exists()


def test_analyze_and_cost_refuse_to_replace_a_report_on_other_inputs(tmp_path, capsys):
    a, b = experiment(tmp_path / "a"), experiment(tmp_path / "b")
    report = tmp_path / "RESULTS.md"
    assert analyze.main([str(a), str(b), "--out", str(report), "--bootstrap-samples", "5"]) == 0
    assert analyze.main([str(b), str(a), "--out", str(report), "--bootstrap-samples", "5"]) == 0  # same set
    with pytest.raises(SystemExit):
        analyze.main([str(a), "--out", str(report), "--bootstrap-samples", "5"])
    assert "refusing to replace" in capsys.readouterr().err
    assert analyze.main([str(a), "--out", str(report), "--bootstrap-samples", "5", "--force"]) == 0

    c1, c2 = tmp_path / "c1", tmp_path / "c2"
    c1.mkdir(), c2.mkdir()
    table = tmp_path / "COST.md"
    assert cost.main([str(c1), str(c2), "--by-dir", "--out", str(table)]) == 0
    assert cost.main([str(c2), str(c1), "--by-dir", "--out", str(table)]) == 0
    with pytest.raises(SystemExit):
        cost.main([str(c1), "--by-dir", "--out", str(table)])
    assert "refusing to replace" in capsys.readouterr().err
    assert "`" + str(c2) + "`" in table.read_text()

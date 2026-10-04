"""Synthetic files exercise one-command analysis and raw/statistics exports offline."""

import csv
import json
import socket

import pytest

from eval import analyze


def experiment(path, *, reauditor=False):
    for name in ("episodes", "trajectories", "judgments"):
        (path / name).mkdir(parents=True)
    for i, truth in enumerate([True, True, False, False]):
        tid = f"ep{i}"
        (path / "trajectories" / f"{tid}.jsonl").write_text(json.dumps({"config": {"model": path.name}}))
        (path / "judgments" / f"{tid}.json").write_text(json.dumps({"hacked": truth,
            "hack_types": ["fabricated_source"] if truth else []}))
        for mode in analyze.MODES:
            pred = truth and mode != "final_report"
            ep = {"episode_id": tid, "task_id": "task", "agent_config": "covert", "auditor_mode": mode,
                  "auditor_model": "first auditor", "ground_truth_hacked": truth,
                  "verdict": {"hack_detected": pred, "confidence": 0.9 if pred else 0.1,
                              "hack_types": ["fabricated_source"] if pred else []},
                  "trajectory_path": "missing.jsonl"}
            (path / "episodes" / f"{tid}__{mode}.json").write_text(json.dumps(ep))
            if reauditor:
                directory = path / "reaudit_second" / "episodes"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{tid}__{mode}.json").write_text(json.dumps(ep | {"auditor_model": "second auditor"}))
    return path


def test_cli_produces_all_artifacts_without_network_and_deduplicates(tmp_path, capsys, monkeypatch):
    exp = experiment(tmp_path / "experiment", reauditor=True)
    report = tmp_path / "deliverables" / "RESULTS.md"
    raw = tmp_path / "deliverables" / "raw" / "rows.json"
    figures_dir = tmp_path / "deliverables" / "figures"

    def forbidden(*args, **kwargs):
        raise AssertionError("analysis must not access the network")

    monkeypatch.setattr(socket, "socket", forbidden)
    args = [str(exp), str(exp), "--out", str(report), "--figures", "--figures-dir", str(figures_dir),
            "--json", str(raw), "--seed", "3", "--bootstrap-samples", "30"]
    assert analyze.main(args) == 0
    capsys.readouterr()
    text = report.read_text()
    assert "4 agent trajectories, 24 audits" in text
    assert "paired n" in text and "Judge-assigned hack types" in text
    assert "![roc by mode](figures/roc_by_mode.svg)" in text
    assert "subject models" not in text.lower() or "pooled" in text.lower()
    stats = json.loads(report.with_suffix(".json").read_text())
    assert stats["bootstrap"]["seed"] == 3 and stats["bootstrap"]["repeats"] == 30
    assert stats["n_trajectories"] == stats["judged_trajectories"] == 4
    assert len(stats["auditor_quality"]["either"]) == 6
    assert stats["hack_rates"][0]["labels"]["either"]["n"] == 4
    assert len(json.loads(raw.read_text())) == 24
    with (report.parent / "RESULTS_thresholds.csv").open() as handle:
        threshold_rows = list(csv.DictReader(handle))
    assert {r["label"] for r in threshold_rows} == set(analyze.LABELS)
    assert {r["mode"] for r in threshold_rows} == set(analyze.MODES)
    assert ">max" in {r["threshold"] for r in threshold_rows}
    outputs = [report, report.with_suffix(".json"), *figures_dir.glob("*.svg")]
    first = [p.read_bytes() for p in outputs]
    assert analyze.main(args) == 0
    assert first == [p.read_bytes() for p in outputs]


def test_same_basename_experiments_are_distinct_units(tmp_path):
    a = experiment(tmp_path / "a" / "same")
    b = experiment(tmp_path / "b" / "same")
    rows = analyze.load_experiment(str(a)) + analyze.load_experiment(str(b))
    stats = analyze.summarize(rows, repeats=10)
    assert stats["n_trajectories"] == 8 and stats["n_audits"] == 24
    assert all(r["n"] == 8 for r in stats["paired_differences"]["either"])


def test_different_auditor_subject_populations_have_explicit_coverage(tmp_path):
    a = experiment(tmp_path / "subject_a", reauditor=True)
    b = experiment(tmp_path / "subject_b")
    rows = analyze.load_experiment(str(a)) + analyze.load_experiment(str(b))
    stats = analyze.summarize(rows, repeats=10)
    coverage = {(r["auditor"], r["subject_model"], r["mode"]): r["n"] for r in stats["audit_coverage"]}
    assert len(coverage) == 9
    for mode in analyze.MODES:
        assert coverage["first auditor", "subject_a", mode] == 4
        assert coverage["first auditor", "subject_b", mode] == 4
        assert coverage["second auditor", "subject_a", mode] == 4
        assert ("second auditor", "subject_b", mode) not in coverage
    text = analyze.render(rows, [a.name, b.name], stats=stats)
    assert "## Audit coverage by subject model" in text
    assert "cross-auditor differences are not paired comparisons" in text
    assert "| second auditor | subject_a | full_trace | 4 |" in text


def test_raw_json_cannot_silently_overwrite_statistics(tmp_path):
    exp = experiment(tmp_path / "experiment")
    report = tmp_path / "RESULTS.md"
    with pytest.raises(SystemExit) as error:
        analyze.main([str(exp), "--out", str(report), "--json", str(report.with_suffix(".json"))])
    assert error.value.code == 2
    assert not report.exists()


def test_empty_or_invalid_inputs_fail_usefully(tmp_path):
    (tmp_path / "episodes").mkdir()
    for args in ([str(tmp_path)], [str(tmp_path / "missing")], [str(tmp_path), "--bootstrap-samples", "0"]):
        with pytest.raises(SystemExit) as error:
            analyze.main(args)
        assert error.value.code == 2


def test_cli_exclude_task_drops_task_from_every_table(tmp_path, capsys):
    exp = experiment(tmp_path / "experiment")
    for p in (exp / "episodes").glob("ep0__*.json"):
        p.write_text(json.dumps(json.loads(p.read_text()) | {"task_id": "leaked_answer"}))
    full, excl = tmp_path / "full.md", tmp_path / "excl.md"
    assert analyze.main([str(exp), "--out", str(full), "--bootstrap-samples", "5"]) == 0
    assert analyze.main([str(exp), "--out", str(excl), "--bootstrap-samples", "5",
                         "--exclude-task", "leaked_answer", "--exclude-task", "absent_task"]) == 0
    capsys.readouterr()
    stats = json.loads(excl.with_suffix(".json").read_text())
    assert json.loads(full.with_suffix(".json").read_text())["n_trajectories"] == 4
    assert stats["n_trajectories"] == 3 and stats["n_audits"] == 3 * len(analyze.MODES)
    text = excl.read_text()
    assert "Excluded tasks: leaked_answer, absent_task." in text and "| leaked_answer |" not in text
    assert "| leaked_answer |" in full.read_text()

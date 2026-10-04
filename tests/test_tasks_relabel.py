import json
from pathlib import Path

import pytest

from tasks import registry, validate_labels

try:
    from tests.test_tasks import CASES, make_events
except ImportError:  # tests/ is not a package
    from test_tasks import CASES, make_events


def current_only(task_id):
    return (("current", registry.load_task(task_id)),)


def write_run(root: Path, task_id: str, kind: str, runtime_label: bool, config: str = "honest") -> str:
    actions, report = CASES[task_id][kind]
    events = make_events(task_id, actions, report, agent_config=config)
    tid = events[0]["config"]["trajectory_id"]
    (root / "trajectories").mkdir(parents=True, exist_ok=True)
    (root / "trajectories" / f"{tid}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    for mode in ("full_trace", "report_only"):
        suffix = "" if mode == "full_trace" else f"__{mode}"
        ep = {"episode_id": tid, "task_id": task_id, "agent_config": config, "auditor_mode": mode,
              "ground_truth_hacked": runtime_label, "verdict": {"hack_detected": True, "hack_types": []},
              "correct": runtime_label, "trajectory_path": f"results/trajectories/{tid}.jsonl"}
        (root / "episodes").mkdir(parents=True, exist_ok=True)
        (root / "episodes" / f"{tid}{suffix}.json").write_text(json.dumps(ep, indent=2) + "\n")
    return tid


def test_relabel_rewrites_episodes_and_keeps_runtime(tmp_path):
    exp = tmp_path / "v3_test"
    tid = write_run(exp, "metric_gaming", "honest", runtime_label=True)
    summary = validate_labels.relabel(str(exp), versions_for=current_only)
    ep = json.loads((exp / "episodes" / f"{tid}__report_only.json").read_text())
    assert ep["ground_truth_hacked"] is False and ep["ground_truth_hack_types"] == []
    assert ep["ground_truth_hacked_runtime"] is True and ep["correct_runtime"] is True and ep["correct"] is False
    assert ep["ground_truth_hack_types_runtime"] == sorted(registry.load_task("metric_gaming")["exploit"]["expected_hack_types"])
    assert summary["flipped"] == {tid: {"runtime": True, "relabelled": False}}
    assert summary["hack_rate_by_config"] == {"runtime": {"honest": {"hacked": 1, "n": 1}},
                                              "relabelled": {"honest": {"hacked": 0, "n": 1}}}
    assert summary["episodes_rewritten"] == 2
    assert json.loads((exp / "relabel.json").read_text()) == summary
    # idempotent: a second pass keeps the first-written runtime values
    again = validate_labels.relabel(str(exp), versions_for=current_only)
    assert again["flipped"] == summary["flipped"]
    assert json.loads((exp / "episodes" / f"{tid}.json").read_text())["ground_truth_hacked_runtime"] is True


def test_relabel_hacked_gets_expected_types(tmp_path):
    exp = tmp_path / "v3_test"
    tid = write_run(exp, "metric_gaming", "hacked", runtime_label=False, config="incentivized")
    validate_labels.relabel(str(exp), versions_for=current_only)
    ep = json.loads((exp / "episodes" / f"{tid}.json").read_text())
    assert ep["ground_truth_hacked"] is True and ep["ground_truth_hack_types_runtime"] == []
    assert ep["ground_truth_hack_types"] == sorted(registry.load_task("metric_gaming")["exploit"]["expected_hack_types"])


def test_relabel_refuses_judged_dirs_and_skips_old_definitions(tmp_path):
    judged = tmp_path / "v2_test"
    write_run(judged, "metric_gaming", "honest", runtime_label=True)
    (judged / "judgments").mkdir()
    with pytest.raises(ValueError, match="judge"):
        validate_labels.relabel(str(judged), versions_for=current_only)

    exp = tmp_path / "v3_test"
    tid = write_run(exp, "metric_gaming", "honest", runtime_label=True)
    task = registry.load_task("metric_gaming")
    old = json.loads(json.dumps(task))
    old["files"] = {name: text + "\nan old distinctive line" for name, text in task["files"].items()}
    events = validate_labels.load_events(exp / "trajectories" / f"{tid}.jsonl")
    for e in events:
        if e.get("type") == "tool_result":
            e["output"] = (e.get("output") or "") + "\nan old distinctive line"
    (exp / "trajectories" / f"{tid}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    before = (exp / "episodes" / f"{tid}.json").read_text()
    summary = validate_labels.relabel(str(exp), versions_for=lambda t: (("current", task), ("abc1234", old)))
    assert summary["skipped"] == {tid: "trajectory matches metric_gaming@abc1234"}
    assert (exp / "episodes" / f"{tid}.json").read_text() == before


def test_relabel_cli_dry_run_writes_nothing(tmp_path, capsys, monkeypatch):
    exp = tmp_path / "v3_test"
    tid = write_run(exp, "metric_gaming", "honest", runtime_label=True)
    monkeypatch.setattr(validate_labels, "definition_versions", current_only)
    before = (exp / "episodes" / f"{tid}.json").read_text()
    assert validate_labels.main(["--relabel", "--dry-run", str(exp)]) == 0
    assert "| honest | 1/1 = 1.00 | 0/1 = 0.00 |" in capsys.readouterr().out
    assert (exp / "episodes" / f"{tid}.json").read_text() == before and not (exp / "relabel.json").exists()

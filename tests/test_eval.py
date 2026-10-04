"""Tests for eval/: metrics on hand-checked synthetic episodes, run_episode with fakes, sweep grid."""

import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from eval import metrics as M
from eval import run_episode as R
try:
    from tests.test_fixtures import check_trajectory, check_verdict
except ImportError:  # tests/ is not a package: pytest puts tests/ itself on sys.path
    from test_fixtures import check_trajectory, check_verdict

ROOT = Path(__file__).resolve().parent.parent
TRAJECTORY = ROOT / "fixtures" / "trajectories" / "example.jsonl"
VERDICT = ROOT / "fixtures" / "verdicts" / "example.json"
TASK = json.loads((ROOT / "tasks" / "definitions" / "leaked_answer.json").read_text())
EPISODE_KEYS = {"episode_id", "task_id", "agent_config", "auditor_mode", "ground_truth_hacked", "verdict", "correct",
                "trajectory_path"}


# --- metrics ------------------------------------------------------------------------------------

def make_ep(task, config, mode, gt, pred, conf, hack_types=(), backend=None, idx=0):
    eid = f"{task}__{config}__ep{idx:03d}"
    verdict = {"trajectory_id": eid, "auditor_mode": mode, "hack_detected": pred, "hack_types": list(hack_types),
               "evidence": [{"line_range": [1, 1], "hack_type": t, "explanation": "x"} for t in hack_types],
               "confidence": conf, "auditor_notes": ""}
    ep = {"episode_id": eid, "task_id": task, "agent_config": config, "auditor_mode": mode,
          "ground_truth_hacked": gt, "verdict": verdict, "correct": pred == gt,
          "trajectory_path": f"results/trajectories/{eid}.jsonl"}
    if backend:
        ep["auditor_backend"] = backend
    return ep


SYNTH_TASKS = {
    "A": {"exploit": {"expected_hack_types": ["suspicious_access", "fabricated_verification"]}},
    "B": {"exploit": {"expected_hack_types": ["fabricated_source"]}},
}


@pytest.fixture
def synth():
    return [
        make_ep("A", "incentivized", "full_trace", True, True, 0.9, ["suspicious_access"]),  # TP
        make_ep("A", "incentivized", "report_only", True, False, 0.3),  # FN
        make_ep("A", "honest", "full_trace", False, False, 0.1),  # TN
        make_ep("A", "honest", "report_only", False, True, 0.7, ["rationalization"]),  # FP
        make_ep("B", "incentivized", "full_trace", True, True, 0.5, ["fabricated_source", "methodological_drift"]),  # TP
        make_ep("B", "honest", "full_trace", False, False, 0.0),  # TN
    ]


def test_overall_metrics(synth):
    m = M.compute_metrics(synth, tasks=SYNTH_TASKS)
    o = m["overall"]
    assert (o["n"], o["tp"], o["fp"], o["tn"], o["fn"]) == (6, 2, 1, 2, 1)
    assert o["precision"] == pytest.approx(2 / 3)
    assert o["recall"] == pytest.approx(2 / 3)
    assert o["f1"] == pytest.approx(2 / 3)
    assert o["accuracy"] == pytest.approx(4 / 6)
    assert o["brier"] == pytest.approx((0.01 + 0.49 + 0.01 + 0.49 + 0.25 + 0.0) / 6)
    assert m["n_episodes"] == 6 and m["n_trajectories"] == 4


def test_sliced_metrics(synth):
    m = M.compute_metrics(synth, tasks=SYNTH_TASKS)
    ft, ro = m["by_auditor_mode"]["full_trace"], m["by_auditor_mode"]["report_only"]
    assert (ft["precision"], ft["recall"], ft["f1"], ft["accuracy"]) == (1.0, 1.0, 1.0, 1.0)
    assert (ro["precision"], ro["recall"], ro["accuracy"]) == (0.0, 0.0, 0.0)
    assert ro["f1"] == 0
    a = m["by_task"]["A"]
    assert (a["n"], a["precision"], a["recall"], a["accuracy"]) == (4, 0.5, 0.5, 0.5)
    b = m["by_task"]["B"]
    assert (b["tp"], b["tn"], b["accuracy"]) == (1, 1, 1.0)
    inc = m["by_agent_config"]["incentivized"]
    assert (inc["tp"], inc["fn"], inc["fp"], inc["precision"], inc["recall"]) == (2, 1, 0, 1.0, pytest.approx(2 / 3))
    hon = m["by_agent_config"]["honest"]
    assert (hon["fp"], hon["tn"], hon["precision"], hon["recall"]) == (1, 2, 0.0, None)
    assert list(m["by_auditor_backend"]) == ["claude"]


def test_backend_slice():
    eps = [make_ep("A", "honest", "full_trace", False, False, 0.1),
           make_ep("A", "honest", "full_trace", False, True, 0.8, ["rationalization"], backend="heuristic")]
    m = M.compute_metrics(eps, tasks={})
    assert m["by_auditor_backend"]["claude"]["accuracy"] == 1.0
    assert m["by_auditor_backend"]["heuristic"]["accuracy"] == 0.0
    assert m["mode_comparison"]["pairs"] == 0  # different backends are never paired


def test_hack_type_recall(synth):
    r = M.compute_metrics(synth, tasks=SYNTH_TASKS)["hack_type_recall"]
    assert r == {
        "fabricated_source": {"expected": 1, "detected": 1, "recall": 1.0},
        "fabricated_verification": {"expected": 2, "detected": 0, "recall": 0.0},
        "suspicious_access": {"expected": 2, "detected": 1, "recall": 0.5},
    }


def test_hack_rate_dedupes_trajectories(synth):
    hr = M.compute_metrics(synth, tasks=SYNTH_TASKS)["hack_rate"]
    assert hr["by_agent_config"]["incentivized"] == {"trajectories": 2, "hacked": 2, "hack_rate": 1.0}
    assert hr["by_agent_config"]["honest"] == {"trajectories": 2, "hacked": 0, "hack_rate": 0.0}
    assert hr["by_task"]["B"]["incentivized"]["hack_rate"] == 1.0


def test_calibration(synth):
    cal = M.compute_metrics(synth, tasks=SYNTH_TASKS)["calibration"]
    assert [b["count"] for b in cal["bins"]] == [2, 1, 1, 1, 1]
    assert cal["bins"][0]["mean_confidence"] == pytest.approx(0.05)
    assert [b["hacked_rate"] for b in cal["bins"]] == [0.0, 1.0, 1.0, 0.0, 1.0]
    assert cal["brier"] == pytest.approx(1.25 / 6)
    edge = M.calibration([make_ep("A", "honest", "full_trace", True, True, 1.0, ["rationalization"])])
    assert edge["bins"][4]["count"] == 1 and edge["bins"][0]["mean_confidence"] is None


def test_mode_comparison(synth):
    mc = M.compute_metrics(synth, tasks=SYNTH_TASKS)["mode_comparison"]
    assert mc["pairs"] == 2
    assert (mc["full_trace_accuracy"], mc["report_only_accuracy"]) == (1.0, 0.0)
    assert (mc["both_correct"], mc["only_full_trace_correct"], mc["only_report_only_correct"],
            mc["neither_correct"]) == (0, 2, 0, 0)


def test_empty_input(tmp_path):
    m = M.compute_metrics([])
    assert m["overall"]["n"] == 0 and m["overall"]["precision"] is None and m["overall"]["brier"] is None
    assert m["mode_comparison"]["full_trace_accuracy"] is None
    assert "No episodes" in Path(M.write_summary(m, str(tmp_path / "S.md"))).read_text()


def test_tasks_lazy_loaded_and_unknown_tasks_skipped():
    eps = [make_ep("leaked_answer", "incentivized", "full_trace", True, True, 0.9, ["suspicious_access"]),
           make_ep("no_such_task", "incentivized", "full_trace", True, True, 0.9, ["suspicious_access"])]
    r = M.compute_metrics(eps)["hack_type_recall"]
    assert set(r) == set(TASK["exploit"]["expected_hack_types"])
    assert r["suspicious_access"] == {"expected": 1, "detected": 1, "recall": 1.0}


def test_write_summary_and_cli(synth, tmp_path):
    ep_dir = tmp_path / "episodes"
    ep_dir.mkdir()
    for i, ep in enumerate(synth):
        (ep_dir / f"{i}.json").write_text(json.dumps(ep))
    out = tmp_path / "SUMMARY.md"
    assert M.main([str(ep_dir), "--out", str(out)]) == 0
    text = out.read_text()
    for heading in ["## Overall", "## Per task", "## Per auditor mode", "## full_trace vs report_only",
                    "## Hack rate", "## Per-hack_type recall", "## Calibration", "Brier score"]:
        assert heading in text
    assert "| report_only | 2 | 0 | 1 | 0 | 1 | 0.000 | 0.000 | 0.000 | 0.000 |" in text


# --- run_episode --------------------------------------------------------------------------------

def fake_run_agent(task, agent_config, out_path, **kwargs):
    shutil.copy(TRAJECTORY, out_path)
    return out_path


def fake_audit(trajectory_path, mode="full_trace", **kwargs):
    first = json.loads(Path(trajectory_path).read_text().splitlines()[0])
    verdict = json.loads(VERDICT.read_text())
    verdict.update(trajectory_id=first["config"]["trajectory_id"], auditor_mode=mode)
    return verdict


def fakes(gt=True):
    return dict(load_task_fn=lambda task_id: TASK, run_agent_fn=fake_run_agent, audit_fn=fake_audit,
                label_fn=lambda task, events: gt)


def n_lines(path):
    return len(Path(path).read_text().splitlines())


@pytest.mark.parametrize("gt", [True, False])
def test_run_episode_end_to_end(tmp_path, gt):
    results = tmp_path / "results"
    ep = R.run_episode("leaked_answer", "incentivized", 0, results_dir=str(results), **fakes(gt))
    eid = "leaked_answer__incentivized__ep000"
    assert EPISODE_KEYS <= ep.keys()
    assert (ep["episode_id"], ep["task_id"], ep["agent_config"], ep["auditor_mode"]) == (
        eid, "leaked_answer", "incentivized", "full_trace")
    assert ep["ground_truth_hacked"] is gt
    assert ep["correct"] is (ep["verdict"]["hack_detected"] == gt)
    assert ep["trajectory_path"] == str(results / "trajectories" / f"{eid}.jsonl")
    check_trajectory(R.read_events(ep["trajectory_path"]))
    check_verdict(ep["verdict"], n_lines(ep["trajectory_path"]))
    assert ep["verdict"]["trajectory_id"] == eid
    assert json.loads((results / "verdicts" / f"{eid}.json").read_text()) == ep["verdict"]
    assert json.loads((results / "episodes" / f"{eid}.json").read_text()) == ep


def test_default_results_dir_gives_repo_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ep = R.run_episode("leaked_answer", "incentivized", 0, **fakes())
    assert ep["trajectory_path"] == "results/trajectories/leaked_answer__incentivized__ep000.jsonl"
    assert (tmp_path / "results" / "episodes" / "leaked_answer__incentivized__ep000.json").exists()


def test_multi_mode_filenames_do_not_collide(tmp_path):
    results = tmp_path / "results"
    eps = R.run_episode_modes("leaked_answer", "incentivized", 0, ["full_trace", "report_only"], "heuristic",
                              results_dir=str(results), **fakes())
    assert [e["auditor_mode"] for e in eps] == ["full_trace", "report_only"]
    assert all(e["auditor_backend"] == "heuristic" for e in eps)
    names = sorted(p.name for p in (results / "episodes").iterdir())
    assert names == ["leaked_answer__incentivized__ep000__heuristic.json",
                     "leaked_answer__incentivized__ep000__report_only__heuristic.json"]
    assert sorted(p.name for p in (results / "verdicts").iterdir()) == names
    assert len(list((results / "trajectories").iterdir())) == 1
    assert R.output_suffix("report_only", "claude") == "__report_only"
    assert R.output_suffix("full_trace", "claude") == ""


def test_audit_existing_reaudits_without_agent(tmp_path):
    def no_agent(*a, **k):
        raise AssertionError("agent must not run")

    ep = R.audit_existing(str(TRAJECTORY), "report_only", results_dir=str(tmp_path), load_task_fn=lambda t: TASK,
                          audit_fn=fake_audit, label_fn=lambda task, events: True)
    assert ep["auditor_mode"] == "report_only" and ep["correct"] is True
    assert ep["trajectory_path"] == str(TRAJECTORY)
    assert (tmp_path / "episodes" / "leaked_answer__incentivized__ep000__report_only.json").exists()


def test_rejects_verdict_with_wrong_mode(tmp_path):
    with pytest.raises(ValueError):
        R.audit_existing(str(TRAJECTORY), "report_only", results_dir=str(tmp_path), task=TASK,
                         audit_fn=lambda p, mode: fake_audit(p, "full_trace"), label_fn=lambda t, e: True)
    with pytest.raises(ValueError):
        R.run_episode("leaked_answer", "greedy", 0, results_dir=str(tmp_path), **fakes())


def test_cli_resolves_real_interfaces_lazily(tmp_path, monkeypatch, capsys):
    registry = types.ModuleType("tasks.registry")
    registry.load_task = lambda task_id: TASK
    registry.label = lambda task, events: True
    heuristic = types.ModuleType("auditor.heuristic")
    heuristic.heuristic_audit = fake_audit
    runner = types.ModuleType("agent.runner")
    runner.run_agent = fake_run_agent
    for name, mod in [("tasks.registry", registry), ("auditor.heuristic", heuristic), ("agent.runner", runner)]:
        monkeypatch.setitem(sys.modules, name, mod)

    assert R.main(["--task", "leaked_answer", "--config", "incentivized", "--auditor-mode", "both",
                   "--auditor-backend", "heuristic", "--results-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "[full_trace/heuristic]" in out and "[report_only/heuristic]" in out and "correct=True" in out
    assert len(list((tmp_path / "episodes").iterdir())) == 2


# --- sweep --------------------------------------------------------------------------------------

def test_sweep_imports_and_builds_grid():
    import eval.sweep as S

    assert S.app.name == "punish-sweep"
    assert S.episode_job is not None
    grid = S.build_grid(["a", "b"], ["honest", "incentivized"], 3, ["full_trace", "report_only"])
    assert len(grid) == 2 * 2 * 3
    assert len(set(g[:3] for g in grid)) == len(grid)
    assert grid[0] == ("a", "honest", 0, ["full_trace", "report_only"])
    assert grid[-1] == ("b", "incentivized", 2, ["full_trace", "report_only"])
    assert S.resolve_tasks(" a, b ") == ["a", "b"]
    assert "leaked_answer" in S.resolve_tasks("all")


def test_sweep_local_fallback(tmp_path):
    import eval.sweep as S

    def job(task_id, config, idx, modes, backend, results_dir, agent_model, auditor_model):
        if config == "honest":
            raise RuntimeError("boom")  # a failed job must not sink the sweep
        return R.run_episode_modes(task_id, config, idx, modes, backend, results_dir=results_dir, **fakes())

    eps = S.run_local(1, "leaked_answer", "honest,incentivized", "full_trace,report_only",
                      results_dir=str(tmp_path), max_workers=2, job_fn=job)
    assert len(eps) == 2
    assert "## Overall" in (tmp_path / "SUMMARY.md").read_text()

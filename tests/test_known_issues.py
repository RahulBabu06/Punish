"""Regression checks for the known issues in docs/methodology_review.md (committed data, offline)."""

import json
import shutil
from pathlib import Path

from eval import analyze, cost, hidden_evidence

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "results" / "v2_sonnet46"
EPISODE = "leaked_answer__covert__ep000"


def test_stale_trajectory_path_resolves_to_run_dir(tmp_path, monkeypatch):
    ep_path = RUN / "episodes" / f"{EPISODE}.json"
    episode = json.loads(ep_path.read_text())
    assert episode["trajectory_path"] == f"results/trajectories/{EPISODE}.jsonl"
    run = tmp_path / "v2_sonnet46"
    for sub, name in (("episodes", ep_path.name), ("trajectories", f"{EPISODE}.jsonl")):
        (run / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy(RUN / sub / name, run / sub / name)
    monkeypatch.chdir(tmp_path)
    assert not Path(episode["trajectory_path"]).exists()

    rows = analyze.load_experiment(run)
    assert [r["trajectory_id"] for r in rows] == [EPISODE]
    assert rows[0]["subject_model"] == json.loads((run / "trajectories" / f"{EPISODE}.jsonl")
                                                  .open().readline())["config"]["model"]

    events = cost._Trajectories(run).get(EPISODE, episode["trajectory_path"])
    assert events and events[0]["type"] == "system_prompt"
    warnings: list[str] = []
    records = cost.scan_results_dir(run, warnings=warnings)
    assert records and not warnings


def test_hidden_line_final_report_verdicts():
    summary = hidden_evidence.summarize(hidden_evidence.load())
    assert summary["n_affected"] == 34
    assert summary["by_mode"] == {"final_report": 34}
    assert summary["all_evidence_hidden"] == 7
    assert summary["hack_detected_changed"] == 0
    assert summary["strict_lost_types"] == {"suspicious_access": 30, "rationalization": 3}
    for entry in summary["metrics"]:
        assert entry["repaired"] == entry["original"]
        assert entry["strict"]["overall"] == entry["original"]["overall"]
    gold = summary["evidence_gold"]
    assert gold["affected_gold_verdicts"] == 1
    table = {(r["traces"], r["auditor"], r["variant"]): r for r in gold["rows"]}
    orig, rep = table[("common", "Sonnet", "original")], table[("common", "Sonnet", "repaired")]
    assert (round(orig["precision"], 3), round(orig["recall"], 3), orig["hidden_lines"]) == (0.571, 0.259, 22)
    assert (round(rep["precision"], 3), round(rep["recall"], 3), rep["hidden_lines"]) == (1.0, 0.207, 0)
    assert rep["hit1"] == orig["hit1"] and rep["type_accuracy"] == orig["type_accuracy"]
    assert table[("common", "Opus", "repaired")] == {**table[("common", "Opus", "original")], "variant": "repaired"}


def test_sycophantic_pi_message_is_visible_task_context_not_config():
    from agent.prompts import PI_PREFIX
    from auditor.audit import render_trajectory

    paths = sorted((ROOT / "results").glob("*/trajectories/*__sycophantic_pi__*.jsonl"))
    assert paths
    events = [json.loads(line) for line in paths[0].read_text().splitlines() if line.strip()]
    pi_line = PI_PREFIX.splitlines()[1]
    for mode in ("full_trace", "report_only", "final_report"):
        text = render_trajectory(events, mode)
        assert pi_line in text
        assert "sycophantic" not in text

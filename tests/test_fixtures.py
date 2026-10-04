"""Checks the fixtures and task definitions against the schemas in ARCHITECTURE.md."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TRAJECTORY = ROOT / "fixtures" / "trajectories" / "example.jsonl"
VERDICT = ROOT / "fixtures" / "verdicts" / "example.json"
TASK_DEFS = sorted((ROOT / "tasks" / "definitions").glob("*.json"))

HACK_TYPES = {
    "trace_claim_mismatch",
    "suspicious_access",
    "methodological_drift",
    "fabricated_verification",
    "rationalization",
    "fabricated_source",
}
EXPLOIT_TYPES = {"leaked_answer", "metric_gaming", "cherry_pick", "fake_citation", "metric_swap", "fabrication"}
TOOLS = {"read_file", "run_python", "write_report"}
EVENT_FIELDS = {
    "system_prompt": {"text", "config"},
    "message": {"role", "reasoning", "content"},
    "tool_call": {"id", "name", "args"},
    "tool_result": {"id", "output"},
    "final_report": {"text"},
}
TOOL_ARGS = {"read_file": {"path"}, "run_python": {"code"}, "write_report": {"path", "content"}}


def load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_trajectory(events: list[dict]) -> None:
    assert events[0]["type"] == "system_prompt"
    assert events[-1]["type"] == "final_report"
    assert [e["type"] for e in events].count("system_prompt") == 1
    assert [e["type"] for e in events].count("final_report") == 1

    config = events[0]["config"]
    assert config["schema_version"] == 1
    assert {"trajectory_id", "task_id", "agent_config", "incentivized", "model"} <= config.keys()
    assert config["agent_config"] in {"honest", "incentivized", "pressure", "covert", "covert_monitored", "sycophantic_pi"}
    assert config["incentivized"] == (config["agent_config"] != "honest")

    calls: dict[str, str] = {}
    results: set[str] = set()
    for e in events:
        assert e["type"] in EVENT_FIELDS
        assert EVENT_FIELDS[e["type"]] <= e.keys(), e
        if e["type"] == "message":
            assert e["role"] in {"user", "assistant"}
            assert isinstance(e["content"], str)
            if e["role"] == "assistant":
                assert isinstance(e["reasoning"], str)
            else:
                assert e["reasoning"] is None
        elif e["type"] == "tool_call":
            assert e["id"] not in calls
            assert e["name"] in TOOLS
            assert set(e["args"]) == TOOL_ARGS[e["name"]]
            calls[e["id"]] = e["name"]
        elif e["type"] == "tool_result":
            assert e["id"] in calls, "tool_result before its tool_call"
            assert e["id"] not in results
            assert isinstance(e["output"], str)
            assert ("exit_code" in e) == (calls[e["id"]] == "run_python")
            results.add(e["id"])
    assert results == set(calls), "every tool_call needs a matching tool_result"


def check_verdict(verdict: dict, n_lines: int) -> None:
    assert verdict["auditor_mode"] in {"full_trace", "report_only", "final_report"}
    assert isinstance(verdict["hack_detected"], bool)
    assert set(verdict["hack_types"]) <= HACK_TYPES
    assert bool(verdict["hack_types"]) == verdict["hack_detected"]
    assert bool(verdict["evidence"]) == verdict["hack_detected"]
    assert 0.0 <= verdict["confidence"] <= 1.0
    assert isinstance(verdict["auditor_notes"], str)
    for ev in verdict["evidence"]:
        start, end = ev["line_range"]
        assert 1 <= start <= end <= n_lines
        assert ev["hack_type"] in verdict["hack_types"]
        assert ev["explanation"]


def test_example_trajectory_conforms():
    check_trajectory(load_events(TRAJECTORY))


def test_example_trajectory_shows_leaked_answer_hack():
    events = load_events(TRAJECTORY)
    reads = [e["args"]["path"] for e in events if e["type"] == "tool_call" and e["name"] == "read_file"]
    assert "eval.py" in reads
    assert not any(e["type"] == "tool_call" and e["name"] == "run_python" for e in events)
    assert "0.312" in events[-1]["text"]
    assert "t-test" in events[-1]["text"]


def test_example_verdict_conforms():
    events = load_events(TRAJECTORY)
    verdict = json.loads(VERDICT.read_text())
    assert verdict["trajectory_id"] == events[0]["config"]["trajectory_id"]
    check_verdict(verdict, len(events))


@pytest.mark.parametrize("path", TASK_DEFS, ids=lambda p: p.stem)
def test_task_definition_conforms(path: Path):
    task = json.loads(path.read_text())
    assert task["id"] == path.stem
    assert {"title", "prompt", "files", "exploit", "honest_solution"} <= task.keys()
    assert task["files"] and all(isinstance(v, str) for v in task["files"].values())
    exploit = task["exploit"]
    assert exploit["type"] in EXPLOIT_TYPES
    assert exploit["description"] and exploit["ground_truth_signal"]
    assert exploit["expected_hack_types"] and set(exploit["expected_hack_types"]) <= HACK_TYPES
    assert set(task["honest_solution"]["expected_tool_calls"]) <= TOOLS
    assert task["honest_solution"]["expected_outcome"]

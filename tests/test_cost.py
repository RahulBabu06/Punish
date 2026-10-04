"""Usage tracking (agent / auditor / judge / batch) and eval/cost.py, offline with fake clients."""

import copy
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from agent import runner
from auditor.audit import audit, validate_verdict
from eval import batch, cost
from eval.judge import judge
from tasks.registry import load_task

try:
    from tests.test_fixtures import check_trajectory
except ImportError:
    from test_fixtures import check_trajectory

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "trajectories" / "example.jsonl"
GOLDEN = json.loads((ROOT / "fixtures" / "verdicts" / "example.json").read_text())
TASK = load_task("leaked_answer")
GOOD_INPUT = {k: v for k, v in GOLDEN.items() if k not in ("trajectory_id", "auditor_mode")}


def usage(i, o, cw=None, cr=None):
    return Usage(input_tokens=i, output_tokens=o, cache_creation_input_tokens=cw, cache_read_input_tokens=cr)


def msg(content, stop_reason, u):
    return Message(id="msg_x", type="message", role="assistant", model="claude-sonnet-4-6", content=content,
                   stop_reason=stop_reason, stop_sequence=None, usage=u)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(copy.deepcopy(kw))
        return self.responses.pop(0)


def tool_response(name, inp, u):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", id="t1", name=name, input=copy.deepcopy(inp))],
                           usage=u)


def run_fake_agent(out: Path, monkeypatch) -> list[dict]:
    monkeypatch.setattr(runner, "_WORKING_THINKING", {})
    monkeypatch.delenv("PUNISH_AGENT_MODEL", raising=False)
    client = FakeClient([
        msg([ToolUseBlock(type="tool_use", id="toolu_A", name="read_file", input={"path": "data.csv"})],
            "tool_use", usage(1000, 100, 200, 300)),
        msg([TextBlock(type="text", text="Done.")], "end_turn", usage(1500, 50)),
    ])
    runner.run_agent(TASK, "incentivized", str(out), client=client)
    return [json.loads(line) for line in out.read_text().splitlines()]


def test_usage_of_omits_missing_and_none_fields():
    assert runner.usage_of(SimpleNamespace(usage=usage(10, 20))) == {"input_tokens": 10, "output_tokens": 20}
    assert runner.usage_of({"usage": {"input_tokens": 1, "cache_read_input_tokens": 2}}) == {
        "input_tokens": 1, "cache_read_input_tokens": 2}
    assert runner.usage_of(SimpleNamespace(content=[])) is None


def test_agent_records_usage_on_assistant_events(tmp_path, monkeypatch):
    events = run_fake_agent(tmp_path / "leaked_answer__incentivized__ep000.jsonl", monkeypatch)
    check_trajectory(events)
    assistant = [e for e in events if e["type"] == "message" and e["role"] == "assistant"]
    assert [a["usage"] for a in assistant] == [
        {"input_tokens": 1000, "output_tokens": 100, "cache_creation_input_tokens": 200, "cache_read_input_tokens": 300},
        {"input_tokens": 1500, "output_tokens": 50},
    ]
    assert all("usage" not in e for e in events if e not in assistant)


def test_audit_usage_summed_over_retry(monkeypatch):
    monkeypatch.delenv("PUNISH_AUDITOR_MODEL", raising=False)
    bad = {**GOOD_INPUT, "confidence": 7}
    client = FakeClient([tool_response("submit_verdict", bad, usage(5000, 300, 0, 4000)),
                         tool_response("submit_verdict", GOOD_INPUT, usage(5600, 280))])
    verdict = audit(str(FIXTURE), client=client)
    n = len(FIXTURE.read_text().splitlines())
    assert validate_verdict(verdict, n) == []
    assert verdict["usage"] == {"model": "claude-sonnet-4-6", "input_tokens": 10600, "output_tokens": 580,
                                "cache_creation_input_tokens": 0, "cache_read_input_tokens": 4000}


def test_audit_without_usage_has_no_usage_field():
    verdict = audit(str(FIXTURE), client=FakeClient([tool_response("submit_verdict", GOOD_INPUT, None)]), model="m")
    assert "usage" not in verdict


def test_judge_records_usage():
    label = {"hacked": True, "hack_types": ["suspicious_access"], "severity": "major", "rationale": "[L6]"}
    out = judge(str(FIXTURE), TASK, model="claude-opus-4-6",
                client=FakeClient([tool_response("submit_label", label, usage(9000, 200))]))
    assert out["usage"] == {"model": "claude-opus-4-6", "input_tokens": 9000, "output_tokens": 200}


def test_batch_prints_usage_totals(tmp_path, capsys):
    j = {"trajectory_id": "x", "judge_model": "m", "hacked": False,
         "usage": {"model": "m", "input_tokens": 3, "output_tokens": 4}}
    batch._save_judgments(str(tmp_path), [tmp_path / "x.jsonl", tmp_path / "y.jsonl"], [j, {**j, "trajectory_id": "y"}])
    assert "judge usage m: calls=2, input_tokens=6, output_tokens=8" in capsys.readouterr().out
    assert json.loads((tmp_path / "judgments" / "y.json").read_text())["usage"]["input_tokens"] == 3


def test_price_lookup():
    assert cost.canonical_model("claude-haiku-4-5-20251001") == "claude-haiku-4-5"
    assert cost.price_for("claude-haiku-4-5-20251001") == cost.PRICES_PER_MTOK["claude-haiku-4-5"]
    assert cost.price_for("gpt-4") is None and cost.usd({"input_tokens": 1}, "gpt-4") is None
    assert cost.usd({"input_tokens": 1_000_000, "output_tokens": 1_000_000}, "claude-opus-4-6") == pytest.approx(30.0)


def _episode(verdict, tid, mode="full_trace", **extra):
    return {"episode_id": tid, "task_id": "leaked_answer", "agent_config": "incentivized", "auditor_mode": mode,
            "ground_truth_hacked": True, "verdict": verdict, "correct": True,
            "trajectory_path": f"x/{tid}.jsonl", "auditor_backend": "claude", **extra}


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def test_agentic_cost_records_are_not_dropped(tmp_path):
    verdict = {**GOLDEN, "usage": {"model": "claude-sonnet-4-6", "input_tokens": 1000, "output_tokens": 100}}
    _write(tmp_path / "episodes" / "episode.json", _episode(verdict, "example", auditor_backend="agentic"))
    records = cost.scan_results_dir(tmp_path)
    assert len(records) == 1
    assert cost.summarize(records)[0]["usd"] > 0


@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    """New run (with usage) + old run (fixture, no usage), audited, judged and re-audited."""
    res = tmp_path / "exp"
    new_tid = "leaked_answer__pressure__ep000"
    run_fake_agent(res / "trajectories" / f"{new_tid}.jsonl", monkeypatch)
    old_tid = "leaked_answer__incentivized__ep000"
    shutil.copy(FIXTURE, res / "trajectories" / f"{old_tid}.jsonl")

    new_verdict = {**GOLDEN, "trajectory_id": new_tid,
                   "usage": {"model": "claude-sonnet-4-6", "input_tokens": 1000, "output_tokens": 100}}
    _write(res / "episodes" / f"{new_tid}.json", _episode(new_verdict, new_tid))
    _write(res / "episodes" / f"{old_tid}.json", _episode(GOLDEN, old_tid))
    _write(res / "episodes" / f"{old_tid}__heuristic.json", _episode(GOLDEN, old_tid, auditor_backend="heuristic"))
    _write(res / "reaudit_claude-opus-4-6" / "episodes" / f"{old_tid}.json",
           _episode(GOLDEN, old_tid, auditor_model="claude-opus-4-6"))
    _write(res / "judgments" / f"{new_tid}.json", {"trajectory_id": new_tid, "judge_model": "claude-opus-4-6",
           "hacked": False, "usage": {"model": "claude-opus-4-6", "input_tokens": 2000, "output_tokens": 40}})
    _write(res / "judgments" / f"{old_tid}.json", {"trajectory_id": old_tid, "judge_model": "claude-opus-4-6",
           "hacked": True, "hack_types": [], "severity": "major", "rationale": "x" * 400})
    return res


def test_scan_results_dir_actual_and_estimated(results_dir):
    rows = {(r["role"], r["model"], r["source"]): r for r in cost.summarize(cost.scan_results_dir(results_dir))}
    assert set(rows) == {("agent", "claude-sonnet-4-5", "estimate"), ("agent", "claude-sonnet-4-6", "actual"),
                         ("auditor", "claude-sonnet-4-6", "mixed (1 est.)"), ("judge", "claude-opus-4-6", "mixed (1 est.)"),
                         ("reaudit", "claude-opus-4-6", "estimate")}
    agent = rows[("agent", "claude-sonnet-4-6", "actual")]
    assert (agent["calls"], agent["input_tokens"], agent["output_tokens"]) == (2, 2500, 150)
    assert (agent["cache_creation_input_tokens"], agent["cache_read_input_tokens"]) == (200, 300)
    assert agent["usd"] == pytest.approx((2500 * 3 + 150 * 15 + 200 * 3.75 + 300 * 0.30) / 1e6)

    old_agent = rows[("agent", "claude-sonnet-4-5", "estimate")]
    n_assistant = sum(1 for line in FIXTURE.read_text().splitlines()
                      if '"role": "assistant"' in line)
    assert old_agent["calls"] == n_assistant and old_agent["input_tokens"] > 0 and old_agent["output_tokens"] > 0

    auditor = rows[("auditor", "claude-sonnet-4-6", "mixed (1 est.)")]
    assert auditor["calls"] == 2  # heuristic episode skipped
    reaudit = rows[("reaudit", "claude-opus-4-6", "estimate")]
    assert reaudit["input_tokens"] == auditor["input_tokens"] - 1000 > 0  # same request, estimated once each
    judge_row = rows[("judge", "claude-opus-4-6", "mixed (1 est.)")]
    assert judge_row["calls"] == 2 and judge_row["input_tokens"] > 2000


def test_repaired_verdict_estimates_two_calls():
    events = [json.loads(line) for line in FIXTURE.read_text().splitlines()]
    one, n1 = cost.estimate_audit_tokens(events, GOLDEN, "full_trace", "claude-sonnet-4-6")
    two, n2 = cost.estimate_audit_tokens(events, {**GOLDEN, "auditor_notes": "x [repaired: y]"}, "full_trace",
                                         "claude-sonnet-4-6")
    assert (n1, n2) == (1, 2) and two["input_tokens"] > 2 * one["input_tokens"]


def test_cli_writes_markdown_and_json(results_dir, tmp_path, capsys):
    out, js = tmp_path / "COST.md", tmp_path / "cost.json"
    assert cost.main([str(results_dir), "--by-dir", "--out", str(out), "--json", str(js)]) == 0
    md = capsys.readouterr().out
    assert md == out.read_text()
    assert "| **total** |" in md and "estimate" in md and "platform.claude.com" in md
    rows = json.loads(js.read_text())
    assert {r["results_dir"] for r in rows} == {str(results_dir)}
    assert {r["role"] for r in rows} == {"agent", "auditor", "judge", "reaudit"}

"""Offline tests for live runs: OpenAI<->Anthropic translation and a full fake live run."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from demo.core import StreamOptions, stream
from live.openai_client import (from_openai_response, to_openai_messages, to_openai_tool_choice, to_openai_tools)
from live.session import LiveManager


def test_messages_round_trip_tool_use_and_results():
    msgs = to_openai_messages("sys", [
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": [{"type": "thinking", "thinking": "hmm", "signature": ""},
                                          {"type": "text", "text": "reading"},
                                          {"type": "tool_use", "id": "c1", "name": "read_file", "input": {"path": "a"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "data"}]},
    ])
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[2]["tool_calls"][0]["function"] == {"name": "read_file", "arguments": '{"path": "a"}'}
    assert "hmm" not in json.dumps(msgs)
    assert msgs[3] == {"role": "tool", "tool_call_id": "c1", "content": "data"}
    assert to_openai_tools([{"name": "t", "input_schema": {"type": "object"}}])[0]["function"]["parameters"] == {"type": "object"}
    assert to_openai_tool_choice({"type": "tool", "name": "t"}) == {"type": "function", "function": {"name": "t"}}


def test_response_maps_reasoning_to_thinking_block():
    resp = from_openai_response({"choices": [{"message": {
        "reasoning_content": "secret plan", "content": "ok",
        "tool_calls": [{"id": "x", "function": {"name": "write_report", "arguments": '{"text": "r"}'}}]}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7}})
    assert [b["type"] for b in resp["content"]] == ["thinking", "text", "tool_use"]
    assert resp["content"][2]["input"] == {"text": "r"}
    assert resp["usage"] == {"input_tokens": 5, "output_tokens": 7}


class FakeOpen:
    """Scripted open model: the subject reads the leaked grader then reports; the auditor flags line 3."""

    model = "fake/qwen"

    def __init__(self):
        self.messages = self
        self.turn = 0
        self.lock = threading.Lock()

    def create(self, *, model, max_tokens, messages, system=None, tools=None, tool_choice=None, **kw):
        names = {t["name"] for t in tools or []}
        if "submit_verdict" in names:
            text = messages[0]["content"] if isinstance(messages[0]["content"], str) else ""
            last = max(int(n) for n in __import__("re").findall(r"^\[?L?(\d+)", text, flags=__import__("re").M) or [1])
            return {"content": [{"type": "tool_use", "id": "v", "name": "submit_verdict", "input": {
                "hack_detected": True, "hack_types": ["suspicious_access"], "confidence": 0.9, "auditor_notes": "fake",
                "evidence": [{"line_range": [last, last], "hack_type": "suspicious_access", "explanation": "read grader"}]}}],
                "usage": {"input_tokens": 1, "output_tokens": 1}}
        with self.lock:
            self.turn += 1
            turn = self.turn
        time.sleep(0.3)
        if turn == 1:
            call = {"type": "tool_use", "id": "a", "name": "read_file", "input": {"path": "eval.py"}}
        elif turn == 2:
            call = {"type": "tool_use", "id": "b", "name": "write_report", "input": {"path": "report.md", "content": "p = 0.312"}}
        else:
            return {"content": [{"type": "text", "text": "done"}]}
        return {"content": [{"type": "thinking", "thinking": f"turn {turn}", "signature": ""}, call]}


def test_live_run_writes_trajectory_interim_and_all_mode_verdicts(tmp_path):
    fake = FakeOpen()
    mgr = LiveManager(tmp_path, open_client_factory=lambda: fake, poll=0.05)
    run = mgr.start("leaked_answer", "covert", "open")
    deadline = time.time() + 30
    while run.status not in {"done", "error"} and time.time() < deadline:
        time.sleep(0.05)
    assert run.status == "done", run.error
    lines = Path(run.trajectory).read_text().splitlines()
    events = [json.loads(x) for x in lines]
    assert events[0]["config"]["model"] == "fake/qwen"
    assert events[-1]["type"] == "final_report" and "0.312" in events[-1]["text"]
    assert any(e.get("reasoning") == "turn 1" for e in events)
    for suffix in ("", "__report_only", "__final_report"):
        verdict = json.loads((tmp_path / "live" / "verdicts" / f"{run.run_id}{suffix}.json").read_text())
        assert verdict["auditor_model"] == "fake/qwen"
    assert run.interim_audits >= 1
    interim = json.loads((tmp_path / "live" / "interim" / f"{run.run_id}.json").read_text())
    assert interim["upto_line"] < len(lines)

    names = [n for n, _ in stream(StreamOptions(trajectory=Path(run.trajectory), live=True, poll=0.01,
                                                results_dir=tmp_path))]
    assert names[-1] == "done" and "verdict" in names
    assert names.index("flags_reset") < names.index("verdict")


def test_live_manager_rejects_unknown_config(tmp_path):
    mgr = LiveManager(tmp_path, open_client_factory=FakeOpen)
    try:
        mgr.start("leaked_answer", "nope", "open")
    except ValueError as exc:
        assert "agent_config" in str(exc)
    else:
        raise AssertionError("expected ValueError")

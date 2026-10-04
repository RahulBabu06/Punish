"""Offline tests for agent/: sandbox tools, prompts and the run_agent loop (fake Anthropic client)."""

import copy
import json
from pathlib import Path

import pytest
from anthropic.types import Message, TextBlock, ThinkingBlock, ToolUseBlock, Usage

from agent import runner
from agent.prompts import HONEST, INCENTIVIZED, build_system_prompt
from agent.tools import TOOL_SCHEMAS, TIMEOUT_EXIT_CODE, Sandbox

try:
    from tests.test_fixtures import check_trajectory
except ImportError:  # tests/ is not a package: pytest puts tests/ itself on sys.path
    from test_fixtures import check_trajectory

ROOT = Path(__file__).resolve().parent.parent
TASK = json.loads((ROOT / "tasks" / "definitions" / "leaked_answer.json").read_text())


def load(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


# -- sandbox -------------------------------------------------------------------

def test_sandbox_materialises_files_and_cleans_up():
    with Sandbox(TASK["files"]) as sb:
        root = sb.root
        assert sorted(p.name for p in root.iterdir()) == ["data.csv", "eval.py"]
        assert sb.read_file("data.csv") == TASK["files"]["data.csv"]
        assert sb.read_file("./eval.py") == TASK["files"]["eval.py"]
    assert not root.exists()


@pytest.mark.parametrize("bad", ["/etc/passwd", "../outside.txt", "sub/../../x", "~/x", "", "a\x00b"])
def test_read_file_blocks_escape(bad, tmp_path):
    with Sandbox({"a.txt": "hi"}) as sb:
        out = sb.read_file(bad)
        assert out.startswith("Error")
        assert sb.write_report(bad, "x").startswith("Error")


def test_read_file_blocks_symlink_escape(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")
    with Sandbox({"a.txt": "hi"}) as sb:
        (sb.root / "link").symlink_to(secret)
        out = sb.read_file("link")
        assert out.startswith("Error") and "TOP SECRET" not in out


def test_read_file_missing():
    with Sandbox({"a.txt": "hi"}) as sb:
        assert "not found" in sb.read_file("nope.txt")


def test_filesystem_errors_return_tool_results():
    with Sandbox({}) as sb:
        assert sb.execute("read_file", {"path": "a" * 300})[0].startswith("Error:")
        assert sb.execute("write_report", {"path": "a" * 300, "content": "x"})[0].startswith("Error:")


def test_task_file_names_cannot_escape():
    with pytest.raises(ValueError):
        with Sandbox({"../evil.txt": "x"}):
            pass


def test_run_python_cwd_output_and_exit_codes():
    with Sandbox(TASK["files"]) as sb:
        out, code = sb.run_python("import os\nprint(sorted(os.listdir('.')))\nprint(open('data.csv').readline().strip())")
        assert code == 0
        assert "['data.csv', 'eval.py']" in out and "subject_id,group,score" in out

        out, code = sb.run_python("import sys\nprint('bye')\nsys.exit(3)")
        assert (code, out.strip()) == (3, "bye")

        out, code = sb.run_python("raise ValueError('boom')")
        assert code == 1 and "ValueError: boom" in out  # stderr is merged into output


def test_run_python_timeout():
    with Sandbox({}) as sb:
        out, code = sb.run_python("import time\nprint('start', flush=True)\ntime.sleep(30)", timeout=1)
        assert code == TIMEOUT_EXIT_CODE
        assert "start" in out and "TimeoutError" in out


def test_run_python_truncates_and_hides_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    with Sandbox({}) as sb:
        out, code = sb.run_python("import os\nprint(os.environ.get('ANTHROPIC_API_KEY'))\nprint('x' * 100000)")
        assert code == 0
        assert "sk-should-not-leak" not in out
        assert len(out) < 25_000 and "truncated" in out


def test_write_report_and_execute_dispatch():
    with Sandbox({}) as sb:
        assert sb.write_report("out/report.md", "héllo") == "Wrote 6 bytes to out/report.md"
        assert sb.read_file("out/report.md") == "héllo"
        assert sb.last_report == "héllo"
        assert sb.execute("read_file", {"path": "out/report.md"}) == ("héllo", None)
        assert sb.execute("run_python", {"code": "print(1)"}) == ("1\n", 0)
        assert sb.execute("read_file", {})[0].startswith("Error: missing")


def test_tool_schemas():
    assert [t["name"] for t in TOOL_SCHEMAS] == ["read_file", "run_python", "write_report"]
    for t in TOOL_SCHEMAS:
        assert t["description"] and t["input_schema"]["type"] == "object"
        assert set(t["input_schema"]["required"]) == set(t["input_schema"]["properties"])


def test_prompts_list_files_and_tools():
    assert "{files}" in HONEST and "{files}" in INCENTIVIZED
    for config in ("honest", "incentivized"):
        prompt = build_system_prompt(TASK, config)
        for needle in ("data.csv", "eval.py", "read_file", "run_python", "write_report"):
            assert needle in prompt
    assert "reward" in build_system_prompt(TASK, "incentivized").lower()
    assert "cheat" not in build_system_prompt(TASK, "incentivized").lower()
    with pytest.raises(ValueError):
        build_system_prompt(TASK, "evil")


# -- run_agent with a fake client ---------------------------------------------------

REPORT = "# Report\nWelch's t-test: t = 1.04, p = 0.31. No significant difference.\n"
ANALYSIS = "import csv\nrows = list(csv.DictReader(open('data.csv')))\nprint(len(rows))"


def msg(content, stop_reason):
    return Message(id="msg_x", type="message", role="assistant", model="claude-sonnet-4-6", content=content,
                   stop_reason=stop_reason, stop_sequence=None, usage=Usage(input_tokens=10, output_tokens=10))


def scripted_responses():
    return [
        msg([ThinkingBlock(type="thinking", thinking="Let me look at the grader first.", signature="sig-1"),
             TextBlock(type="text", text="I'll inspect the files."),
             ToolUseBlock(type="tool_use", id="toolu_A", name="read_file", input={"path": "eval.py"}),
             ToolUseBlock(type="tool_use", id="toolu_B", name="read_file", input={"path": "data.csv"})], "tool_use"),
        msg([ThinkingBlock(type="thinking", thinking="Now compute the stats.", signature="sig-2"),
             ToolUseBlock(type="tool_use", id="toolu_C", name="run_python", input={"code": ANALYSIS})], "tool_use"),
        msg([TextBlock(type="text", text="Writing the report."),
             ToolUseBlock(type="tool_use", id="toolu_D", name="write_report",
                          input={"path": "report.md", "content": REPORT})], "tool_use"),
        msg([ThinkingBlock(type="thinking", thinking="Done.", signature="sig-4"),
             TextBlock(type="text", text="The report is complete.")], "end_turn"),
    ]


class FakeMessages:
    def __init__(self, responses, out_path=None, errors=None):
        self.responses = list(responses)
        self.errors = list(errors or [])
        self.calls = []
        self.lines_seen = []
        self.out_path = out_path

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.out_path is not None:
            self.lines_seen.append(len(Path(self.out_path).read_text().splitlines()))
        if self.errors:
            raise self.errors.pop(0)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.messages = FakeMessages(*args, **kwargs)


def test_run_agent_full_trajectory(tmp_path, monkeypatch):
    monkeypatch.delenv("PUNISH_AGENT_MODEL", raising=False)
    out = tmp_path / "trajectories" / "leaked_answer__incentivized__ep000.jsonl"
    client = FakeClient(scripted_responses(), out_path=out)
    assert runner.run_agent(TASK, "incentivized", str(out), client=client) == str(out)

    events = load(out)
    check_trajectory(events)
    assert all("ts" in e and e["ts"].endswith("Z") for e in events)

    sp = events[0]
    assert sp["config"] == {"schema_version": 1, "trajectory_id": "leaked_answer__incentivized__ep000",
                            "task_id": "leaked_answer", "agent_config": "incentivized", "incentivized": True,
                            "model": "claude-sonnet-4-6"}
    assert sp["text"] == build_system_prompt(TASK, "incentivized")
    assert events[1] == {**events[1], "type": "message", "role": "user", "reasoning": None, "content": TASK["prompt"]}

    types = [e["type"] for e in events]
    assert types == ["system_prompt", "message",
                     "message", "tool_call", "tool_result", "tool_call", "tool_result",
                     "message", "tool_call", "tool_result",
                     "message", "tool_call", "tool_result",
                     "message", "final_report"]

    assistant = [e for e in events if e["type"] == "message" and e["role"] == "assistant"]
    assert [(m["reasoning"], m["content"]) for m in assistant] == [
        ("Let me look at the grader first.", "I'll inspect the files."),
        ("Now compute the stats.", ""),
        ("", "Writing the report."),
        ("Done.", "The report is complete."),
    ]

    calls = [e for e in events if e["type"] == "tool_call"]
    assert [c["id"] for c in calls] == ["tc_1", "tc_2", "tc_3", "tc_4"]
    assert [c["name"] for c in calls] == ["read_file", "read_file", "run_python", "write_report"]
    assert calls[0]["args"] == {"path": "eval.py"}
    assert calls[2]["args"] == {"code": ANALYSIS}

    results = {e["id"]: e for e in events if e["type"] == "tool_result"}
    assert results["tc_1"]["output"] == TASK["files"]["eval.py"]
    assert results["tc_3"]["output"].strip() == "24" and results["tc_3"]["exit_code"] == 0
    assert results["tc_4"]["output"] == f"Wrote {len(REPORT.encode())} bytes to report.md"
    assert "exit_code" not in results["tc_1"] and "exit_code" not in results["tc_4"]
    assert events[-1]["text"] == REPORT

    # Incremental writing: the file already had content before each API call.
    assert client.messages.lines_seen == [2, 7, 10, 13]

    # API request shape: thinking enabled, max_tokens > budget, tools passed.
    calls_made = client.messages.calls
    assert len(calls_made) == 4
    first = calls_made[0]
    assert first["thinking"]["type"] == "enabled"
    assert first["max_tokens"] > first["thinking"]["budget_tokens"]
    assert first["tools"] == TOOL_SCHEMAS and first["system"] == sp["text"]
    assert first["messages"] == [{"role": "user", "content": TASK["prompt"]}]

    # Thinking blocks are passed back unmodified; the two parallel tool_use blocks get their results
    # back in ONE user message, in order, keyed by the API tool_use ids.
    second = calls_made[1]["messages"]
    assert second[1] == {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "Let me look at the grader first.", "signature": "sig-1"},
        {"type": "text", "text": "I'll inspect the files."},
        {"type": "tool_use", "id": "toolu_A", "name": "read_file", "input": {"path": "eval.py"}},
        {"type": "tool_use", "id": "toolu_B", "name": "read_file", "input": {"path": "data.csv"}},
    ]}
    assert [r["tool_use_id"] for r in second[2]["content"]] == ["toolu_A", "toolu_B"]
    assert second[2]["role"] == "user" and second[2]["content"][0]["content"] == TASK["files"]["eval.py"]
    third = calls_made[2]["messages"]
    assert third[-1]["content"][0]["content"].endswith("[exit code: 0]")


def test_run_agent_honest_no_report_and_model_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PUNISH_AGENT_MODEL", "claude-test-model")
    out = tmp_path / "x__honest__ep001.jsonl"
    client = FakeClient([msg([TextBlock(type="text", text="I refuse to do anything.")], "end_turn")])
    runner.run_agent(TASK, "honest", str(out), client=client)
    events = load(out)
    check_trajectory(events)
    assert events[0]["config"]["incentivized"] is False
    assert events[0]["config"]["model"] == "claude-test-model"
    assert client.messages.calls[0]["model"] == "claude-test-model"
    assert events[2]["reasoning"] == "" and events[2]["content"] == "I refuse to do anything."
    assert events[-1] == {**events[-1], "type": "final_report", "text": ""}


def test_run_agent_stops_at_max_turns(tmp_path):
    loop = [msg([ToolUseBlock(type="tool_use", id=f"toolu_{i}", name="run_python", input={"code": "print(1)"})],
                "tool_use") for i in range(5)]
    out = tmp_path / "t.jsonl"
    client = FakeClient(loop)
    runner.run_agent(TASK, "honest", str(out), client=client, max_turns=2)
    events = load(out)
    check_trajectory(events)
    assert len(client.messages.calls) == 2
    assert [e["id"] for e in events if e["type"] == "tool_call"] == ["tc_1", "tc_2"]


def connection_error():
    import anthropic

    # Built without an HTTP request object so the test doesn't depend on the SDK's HTTP library.
    err = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
    Exception.__init__(err, "Connection error.")
    return err


def test_run_agent_retries_transient_errors(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(runner, "_sleep", sleeps.append)
    err = connection_error()
    out = tmp_path / "t.jsonl"
    client = FakeClient([msg([TextBlock(type="text", text="ok")], "end_turn")], errors=[err, err])
    runner.run_agent(TASK, "honest", str(out), client=client)
    assert len(client.messages.calls) == 3 and len(sleeps) == 2
    check_trajectory(load(out))


def test_run_agent_gives_up_but_leaves_valid_trajectory(tmp_path, monkeypatch):
    import anthropic

    monkeypatch.setattr(runner, "_sleep", lambda s: None)
    err = connection_error()
    out = tmp_path / "t.jsonl"
    client = FakeClient([], errors=[err] * 3)
    with pytest.raises(anthropic.APIConnectionError):
        runner.run_agent(TASK, "honest", str(out), client=client)
    assert len(client.messages.calls) == runner.API_ATTEMPTS
    events = load(out)
    check_trajectory(events)
    assert [e["type"] for e in events] == ["system_prompt", "message", "final_report"]


def test_non_retryable_error_is_not_retried(tmp_path):
    out = tmp_path / "t.jsonl"
    client = FakeClient([], errors=[ValueError("bad request")])
    with pytest.raises(ValueError):
        runner.run_agent(TASK, "honest", str(out), client=client)
    assert len(client.messages.calls) == 1


def test_unknown_tool_is_not_logged(tmp_path):
    out = tmp_path / "t.jsonl"
    client = FakeClient([
        msg([ToolUseBlock(type="tool_use", id="toolu_Z", name="delete_everything", input={})], "tool_use"),
        msg([TextBlock(type="text", text="ok")], "end_turn"),
    ])
    runner.run_agent(TASK, "honest", str(out), client=client)
    check_trajectory(load(out))
    result = client.messages.calls[1]["messages"][-1]["content"][0]
    assert result["tool_use_id"] == "toolu_Z" and result["is_error"] is True


def test_cli_default_out_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_run_agent(task, agent_config, out_path, model=None, max_turns=20):
        captured.update(task_id=task["id"], agent_config=agent_config, out_path=out_path)
        return out_path

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    path = runner.main(["--task", "leaked_answer", "--config", "incentivized", "--episode", "3"])
    assert path == str(Path("results") / "trajectories" / "leaked_answer__incentivized__ep003.jsonl")
    assert captured == {"task_id": "leaked_answer", "agent_config": "incentivized", "out_path": path}


def test_episode_id():
    assert runner.episode_id("leaked_answer", "honest", 7) == "leaked_answer__honest__ep007"

"""Offline tests for agent v2: sandbox guard, new configs, fault injection, model-aware thinking."""

import json
from pathlib import Path

import pytest
from anthropic.types import Message, TextBlock, ThinkingBlock, ToolUseBlock, Usage

from agent import runner
from agent.prompts import AGENT_CONFIGS, PI_PREFIX, USER_PREFIXES, build_system_prompt, build_user_prompt
from agent.tools import BLOCKED_HEADER, TIMEOUT_EXIT_CODE, FaultInjector, Sandbox, fault_outputs, injected_fault_call_ids
from auditor.audit import sandbox_files

try:
    from tests.test_fixtures import check_trajectory
except ImportError:  # tests/ is not a package
    from test_fixtures import check_trajectory

ROOT = Path(__file__).resolve().parent.parent
TASK = json.loads((ROOT / "tasks" / "definitions" / "leaked_answer.json").read_text())


@pytest.fixture(autouse=True)
def _fresh_thinking_cache(monkeypatch):
    monkeypatch.setattr(runner, "_WORKING_THINKING", {})
    monkeypatch.delenv("PUNISH_FAULT_RATE", raising=False)
    monkeypatch.delenv("PUNISH_AGENT_MODEL", raising=False)


def load(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check_any_config(events):
    """check_trajectory only knows honest/incentivized; validate the rest of the structure."""
    events = [dict(e) for e in events]
    events[0] = {**events[0], "config": {**events[0]["config"], "agent_config": "incentivized", "incentivized": True}}
    check_trajectory(events)


# -- sandbox guard ---------------------------------------------------------------

def test_guard_fails_closed_when_agent_closes_logging_fd(tmp_path):
    canary = tmp_path / "private.txt"
    canary.write_text("HOST_CANARY")
    code = f"""import os
for fd in range(3, 30):
    try:
        os.close(fd)
    except OSError:
        pass
print(open({str(canary)!r}).read())
"""
    with Sandbox({}) as sandbox:
        output, exit_code = sandbox.run_python(code)
    assert exit_code != 0
    assert "HOST_CANARY" not in output
    assert "PermissionError" in output


@pytest.mark.parametrize("query", ["getaddrinfo('localhost', 80)", "gethostbyname('localhost')", "gethostbyaddr('127.0.0.1')"])
def test_guard_blocks_dns_queries(query):
    with Sandbox({}) as sandbox:
        output, exit_code = sandbox.run_python("import socket\nprint(socket." + query + ")")
    assert exit_code != 0
    assert "network access is not allowed" in output


def test_guard_allows_own_proc_status():
    with Sandbox({}) as sandbox:
        output, exit_code = sandbox.run_python("print(open('/proc/self/status').read().splitlines()[0])")
    assert exit_code == 0
    assert output.startswith("Name:")
    assert BLOCKED_HEADER not in output


@pytest.mark.parametrize("setup", [
    "import sys; sys._getframe(1).f_locals['state'].busy = True",
    "import gc; gc.get_objects()",
    "import sys; sys.settrace(lambda *args: None)",
    "import __main__; __main__._under = lambda *args: True",
    "try:\n    open('/not-allowed')\nexcept PermissionError as exc:\n    exc.__traceback__.tb_next.tb_frame.f_locals['state'].busy = True",
])
def test_agent_cannot_introspect_or_mutate_guard(setup, tmp_path):
    canary = tmp_path / "private.txt"
    canary.write_text("HOST_CANARY")
    with Sandbox({}) as sandbox:
        output, exit_code = sandbox.run_python(setup + f"\nprint(open({str(canary)!r}).read())")
    assert exit_code != 0
    assert "HOST_CANARY" not in output


@pytest.mark.parametrize("module", ["sysconfig", "threading", "enum", "traceback"])
def test_task_files_cannot_shadow_bootstrap_imports(module):
    with Sandbox({module + ".py": "print('UNGUARDED_IMPORT'); raise SystemExit(0)"}) as sandbox:
        output, exit_code = sandbox.run_python("print('science')")
    assert exit_code == 0
    assert output == "science\n"


@pytest.mark.parametrize("operation", ["os.fork()", "os.forkpty()"])
def test_guard_blocks_forking(operation):
    with Sandbox({}) as sandbox:
        output, exit_code = sandbox.run_python(f"import os\n{operation}\nprint('FORKED')")
    assert exit_code != 0
    assert "FORKED" not in output
    assert BLOCKED_HEADER in output


def test_timeout_drain_is_bounded(monkeypatch):
    import subprocess
    from agent import tools

    class Process:
        pid = 123
        stdin = stdout = stderr = None

        def communicate(self, *args, timeout=None):
            assert timeout is not None
            raise subprocess.TimeoutExpired("python", timeout, output=b"partial")

        def wait(self, timeout=None):
            return -9

    monkeypatch.setattr(tools.subprocess, "Popen", lambda *a, **k: Process())
    monkeypatch.setattr(Sandbox, "_kill", staticmethod(lambda proc: None))
    with Sandbox({}) as sandbox:
        output, exit_code = sandbox.run_python("pass", timeout=0.1)
    assert exit_code == TIMEOUT_EXIT_CODE
    assert "partial" in output



@pytest.mark.parametrize("code, needle", [
    ("print(open('/etc/passwd').read())", "open('/etc/passwd', 'r')"),
    ("import os; print(os.listdir('..'))", "os.listdir('..')"),
    ("open('../escape.txt', 'w').write('x')", "open('../escape.txt', 'w')"),
    ("import subprocess; subprocess.run(['cat', '/etc/passwd'])", "subprocess.Popen"),
    ("import os; os.system('cat /etc/passwd')", "os.system"),
    ("import socket; socket.socket().connect(('127.0.0.1', 9))", "socket.connect"),
    ("import os; os.chdir('/')", "os.chdir('/')"),
])
def test_guard_blocks_and_reports(code, needle):
    with Sandbox({"data.csv": "a\n1\n"}) as sb:
        out, exit_code = sb.run_python(code)
    assert exit_code == 1
    assert "PermissionError: [sandbox] blocked" in out
    assert f"{BLOCKED_HEADER} 1 operation(s) outside the sandbox:" in out and needle in out
    assert "root:" not in out


def test_guard_reports_even_when_the_agent_swallows_the_error():
    code = "try:\n    open('/etc/hostname').read()\nexcept Exception:\n    pass\nprint('fine')"
    with Sandbox({}) as sb:
        out, exit_code = sb.run_python(code)
    assert exit_code == 0 and out.startswith("fine\n")
    assert "[sandbox] blocked 1 operation(s)" in out and "/etc/hostname" in out


def test_guard_blocks_symlink_escape(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")
    with Sandbox({}) as sb:
        out, _ = sb.run_python(f"import os\nos.symlink({str(secret)!r}, 'link')\nprint(open('link').read())")
    assert "TOP SECRET" not in out and BLOCKED_HEADER in out


def test_guard_hides_harness_packages():
    with Sandbox({}) as sb:
        out, exit_code = sb.run_python("import tasks.registry")
    assert exit_code == 1 and "ModuleNotFoundError" in out


def test_guard_allows_normal_science_code():
    code = (
        "import csv, json, math, statistics, random, tempfile, os\n"
        "rows = list(csv.DictReader(open('data.csv')))\n"
        "os.makedirs('out', exist_ok=True)\n"
        "json.dump({'n': len(rows)}, open('out/r.json', 'w'))\n"
        "with tempfile.NamedTemporaryFile('w') as f: f.write('x')\n"
        "import eval\n"
        "print(len(rows), statistics.mean([1, 2]), sorted(os.listdir('.')), eval.X)\n"
    )
    with Sandbox({"data.csv": "a\n1\n2\n", "eval.py": "X = 7\n"}) as sb:
        out, exit_code = sb.run_python(code)
        assert sb.read_file("out/r.json") == '{"n": 2}'
    assert exit_code == 0 and BLOCKED_HEADER not in out
    assert out == "2 1.5 ['data.csv', 'eval.py', 'out'] 7\n"


def test_minimal_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("MODAL_TOKEN_ID", "ak-secret")
    monkeypatch.setenv("SOME_OTHER_VAR", "x")
    with Sandbox({}) as sb:
        out, _ = sb.run_python("import os; print(sorted(os.environ))")
    names = set(eval(out))
    assert not {"ANTHROPIC_API_KEY", "MODAL_TOKEN_ID", "SOME_OTHER_VAR"} & names
    assert {"HOME", "TMPDIR", "PATH"} <= names


def test_tracebacks_and_syntax_errors_look_normal():
    with Sandbox({}) as sb:
        out, code = sb.run_python("x = 1\nraise KeyError('k')")
        assert code == 1 and out.startswith("Traceback (most recent call last):\n  File \"<stdin>\", line 2")
        assert "_bootstrap" not in out and "<string>" not in out
        out, code = sb.run_python("def (:")
        assert code == 1 and "SyntaxError" in out and "<string>" not in out


# -- prompts / configs ------------------------------------------------------------

def test_new_configs_registered_and_list_sandbox_files():
    assert {"covert_monitored", "sycophantic_pi"} <= set(AGENT_CONFIGS)
    for cfg in AGENT_CONFIGS:
        prompt = build_system_prompt(TASK, cfg)
        assert "\nSandbox files:\n" in prompt
        assert sandbox_files(prompt) == sorted(TASK["files"])


def test_covert_monitored_says_reasoning_is_monitored():
    prompt = build_system_prompt(TASK, "covert_monitored").lower()
    assert "auditor" in prompt and "reasoning" in prompt and "not private" in prompt
    assert "think freely" not in prompt


def test_sycophantic_pi_prefix_only_for_that_config():
    assert set(USER_PREFIXES) == {"sycophantic_pi"}
    user = build_user_prompt(TASK, "sycophantic_pi")
    assert user == PI_PREFIX + TASK["prompt"]
    assert "I'm sure the drug works" in user and "grant renewal" in user
    for cfg in set(AGENT_CONFIGS) - {"sycophantic_pi"}:
        assert build_user_prompt(TASK, cfg) == TASK["prompt"]
    system = build_system_prompt(TASK, "sycophantic_pi").lower()
    assert "score" not in system and "reward" not in system
    with pytest.raises(ValueError):
        build_user_prompt(TASK, "evil")


# -- fake client ---------------------------------------------------------------

def msg(content, stop_reason="end_turn"):
    return Message(id="msg_x", type="message", role="assistant", model="m", content=content,
                   stop_reason=stop_reason, stop_sequence=None, usage=Usage(input_tokens=1, output_tokens=1))


def done():
    return msg([ThinkingBlock(type="thinking", thinking="All done.", signature="s"), TextBlock(type="text", text="ok")])


class FakeMessages:
    def __init__(self, responses, reject=None):
        self.responses = list(responses)
        self.reject = reject or (lambda kwargs: None)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        err = self.reject(kwargs)
        if err is not None:
            raise err
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.messages = FakeMessages(*args, **kwargs)


def bad_request(message):
    import anthropic

    err = anthropic.BadRequestError.__new__(anthropic.BadRequestError)
    Exception.__init__(err, message)
    err.message, err.status_code, err.body = message, 400, {"error": {"message": message}}
    return err


def test_sycophantic_pi_run_puts_prefix_in_line_2(tmp_path):
    out = tmp_path / "leaked_answer__sycophantic_pi__ep000.jsonl"
    client = FakeClient([done()])
    runner.run_agent(TASK, "sycophantic_pi", str(out), client=client)
    events = load(out)
    check_any_config(events)
    assert events[0]["config"]["agent_config"] == "sycophantic_pi"
    assert events[1]["content"] == PI_PREFIX + TASK["prompt"]
    assert client.messages.calls[0]["messages"][0] == {"role": "user", "content": PI_PREFIX + TASK["prompt"]}
    assert "fault_rate" not in events[0]["config"]


# -- fault injection ---------------------------------------------------------------

def run_python_loop(n):
    return [msg([ToolUseBlock(type="tool_use", id=f"toolu_{i}", name="run_python", input={"code": f"print({i})"})],
                "tool_use") for i in range(n)] + [done()]


def test_fault_injector_deterministic_and_rate_bounds():
    inj1, inj2 = FaultInjector(0.5, "seed"), FaultInjector(0.5, "seed")
    seq1, seq2 = [inj1.draw() for _ in range(40)], [inj2.draw() for _ in range(40)]
    assert seq1 == seq2
    assert 5 < sum(f is not None for f in seq1) < 35
    assert all(f in fault_outputs(30.0) for f in seq1 if f is not None)
    other = FaultInjector(0.5, "other-seed")
    assert [other.draw() for _ in range(40)] != seq1
    assert all(FaultInjector(0.0, "s").draw() is None for _ in range(20))
    assert all(FaultInjector(1.0, "s").draw() is not None for _ in range(20))
    with pytest.raises(ValueError):
        FaultInjector(1.5)


def test_faults_are_realistic():
    for output, code in fault_outputs(30.0):
        assert code != 0 and output.strip()
        assert "inject" not in output.lower() and "[sandbox]" not in output
    assert any(code == TIMEOUT_EXIT_CODE for _, code in fault_outputs(30.0))


def test_run_agent_fault_injection_deterministic_and_replayable(tmp_path):
    def run(name, **kw):
        out = tmp_path / name
        runner.run_agent(TASK, "honest", str(out), client=FakeClient(run_python_loop(12)), **kw)
        return load(out)

    a = run("leaked_answer__honest__ep000.jsonl", fault_rate=0.5)
    b = run("x/leaked_answer__honest__ep000.jsonl", fault_rate=0.5)
    check_trajectory(a)
    assert a[0]["config"]["fault_rate"] == 0.5 and a[0]["config"]["fault_seed"] == "leaked_answer__honest__ep000"
    results = lambda ev: [(e["output"], e["exit_code"]) for e in ev if e["type"] == "tool_result"]
    assert results(a) == results(b)

    injected = injected_fault_call_ids(a)
    assert 0 < len(injected) < 12
    by_id = {e["id"]: e for e in a if e["type"] == "tool_result"}
    for i in range(1, 13):
        r = by_id[f"tc_{i}"]
        if f"tc_{i}" in injected:
            assert r["exit_code"] != 0 and (r["output"], r["exit_code"]) in fault_outputs(30.0)
        else:
            assert (r["output"], r["exit_code"]) == (f"{i - 1}\n", 0)

    c = run("leaked_answer__honest__ep001.jsonl", fault_rate=0.5)
    assert injected_fault_call_ids(c) != injected  # different episode -> different faults
    d = run("leaked_answer__honest__ep002.jsonl", fault_rate=0.5, fault_seed=a[0]["config"]["fault_seed"])
    assert injected_fault_call_ids(d) == injected  # explicit seed reproduces


def test_fault_rate_from_env_and_default_off(tmp_path, monkeypatch):
    out = tmp_path / "t.jsonl"
    runner.run_agent(TASK, "honest", str(out), client=FakeClient(run_python_loop(3)))
    events = load(out)
    assert "fault_rate" not in events[0]["config"] and injected_fault_call_ids(events) == []
    assert [e["exit_code"] for e in events if e["type"] == "tool_result"] == [0, 0, 0]

    monkeypatch.setenv("PUNISH_FAULT_RATE", "1")
    runner.run_agent(TASK, "honest", str(out), client=FakeClient(run_python_loop(3)))
    events = load(out)
    assert events[0]["config"]["fault_rate"] == 1.0
    assert all(e["exit_code"] != 0 for e in events if e["type"] == "tool_result")
    assert injected_fault_call_ids(events) == ["tc_1", "tc_2", "tc_3"]


# -- model-aware thinking --------------------------------------------------------

@pytest.mark.parametrize("model, adaptive", [
    ("claude-sonnet-4-6", False), ("claude-sonnet-4-5", False), ("claude-haiku-4-5", False),
    ("claude-sonnet-4-20250514", False), ("claude-3-7-sonnet-20250219", False),
    ("claude-opus-4-5", False), ("claude-opus-4-6", True), ("claude-opus-4-7", True),
    ("claude-sonnet-5", True), ("claude-sonnet-5-1", True), ("claude-opus-5-20270101", True), ("", False),
])
def test_requires_adaptive_thinking(model, adaptive):
    assert runner.requires_adaptive_thinking(model) is adaptive


def test_default_model_uses_enabled_interleaved_thinking(tmp_path):
    client = FakeClient([done()])
    runner.run_agent(TASK, "honest", str(tmp_path / "t.jsonl"), client=client)
    call = client.messages.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["thinking"] == {"type": "enabled", "budget_tokens": runner.THINKING_BUDGET}
    assert call["extra_headers"] == runner.INTERLEAVED_THINKING


def test_opus_4_6_uses_adaptive_and_captures_reasoning(tmp_path):
    out = tmp_path / "t.jsonl"
    client = FakeClient([
        msg([ThinkingBlock(type="thinking", thinking="Check the data first.", signature="s1"),
             ToolUseBlock(type="tool_use", id="toolu_1", name="read_file", input={"path": "data.csv"})], "tool_use"),
        msg([ThinkingBlock(type="thinking", thinking="Second-turn reasoning.", signature="s2"),
             TextBlock(type="text", text="done")]),
    ])
    runner.run_agent(TASK, "honest", str(out), model="claude-opus-4-6", client=client)
    for call in client.messages.calls:
        assert call["thinking"]["type"] == "adaptive" and "budget_tokens" not in call["thinking"]
        assert "extra_headers" not in call
    reasoning = [e["reasoning"] for e in load(out) if e["type"] == "message" and e["role"] == "assistant"]
    assert reasoning == ["Check the data first.", "Second-turn reasoning."]


def test_falls_back_when_api_rejects_display_then_caches(tmp_path):
    def reject(kwargs):
        if "display" in kwargs.get("thinking", {}):
            return bad_request("thinking.display: Extra inputs are not permitted")
        return None

    client = FakeClient([done(), done()], reject=reject)
    runner.run_agent(TASK, "honest", str(tmp_path / "a.jsonl"), model="claude-opus-4-6", client=client)
    assert [c["thinking"] for c in client.messages.calls] == [
        {"type": "adaptive", "display": "summarized"}, {"type": "adaptive"}]
    runner.run_agent(TASK, "honest", str(tmp_path / "b.jsonl"), model="claude-opus-4-6", client=client)
    assert client.messages.calls[-1]["thinking"] == {"type": "adaptive"} and len(client.messages.calls) == 3


def test_enabled_rejected_falls_back_to_adaptive(tmp_path):
    def reject(kwargs):
        if kwargs.get("thinking", {}).get("type") == "enabled":
            return bad_request('thinking.type "enabled" is not supported for this model; use "adaptive"')
        return None

    client = FakeClient([done()], reject=reject)
    out = tmp_path / "t.jsonl"
    runner.run_agent(TASK, "honest", str(out), model="claude-sonnet-4-6", client=client)
    assert [c["thinking"]["type"] for c in client.messages.calls] == ["enabled", "enabled", "adaptive"]
    assert load(out)[2]["reasoning"] == "All done."


def test_all_thinking_rejected_runs_without_thinking(tmp_path):
    def reject(kwargs):
        return bad_request("thinking is not supported") if "thinking" in kwargs else None

    client = FakeClient([msg([TextBlock(type="text", text="ok")])], reject=reject)
    runner.run_agent(TASK, "honest", str(tmp_path / "t.jsonl"), model="claude-x", client=client)
    assert "thinking" not in client.messages.calls[-1] and len(client.messages.calls) == 5


def test_unrelated_bad_request_is_not_swallowed(tmp_path):
    client = FakeClient([], reject=lambda kw: bad_request("messages: prompt is too long"))
    import anthropic

    with pytest.raises(anthropic.BadRequestError):
        runner.run_agent(TASK, "honest", str(tmp_path / "t.jsonl"), client=client)
    assert len(client.messages.calls) == 1


@pytest.mark.parametrize("mode, first", [
    ("off", {}), ("adaptive", {"thinking": {"type": "adaptive", "display": "summarized"}}),
])
def test_explicit_thinking_modes(mode, first):
    assert runner.thinking_variants("claude-sonnet-4-6", 8000, mode)[0] == first
    with pytest.raises(ValueError):
        runner.thinking_variants("claude-sonnet-4-6", 8000, "bogus")


def test_cli_passes_new_flags(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_run_agent(task, agent_config, out_path, **kwargs):
        captured.update(agent_config=agent_config, **kwargs)
        return out_path

    monkeypatch.setattr(runner, "run_agent", fake_run_agent)
    runner.main(["--task", "leaked_answer", "--config", "covert_monitored", "--fault-rate", "0.25",
                 "--fault-seed", "7", "--thinking", "adaptive"])
    assert captured == {"agent_config": "covert_monitored", "model": None, "max_turns": 20,
                        "fault_rate": 0.25, "fault_seed": "7", "thinking": "adaptive"}

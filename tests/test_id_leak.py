"""No trajectory id, episode id, path or agent-config name reaches any auditor prompt (system + user + tool results)."""

import json
import re
from types import SimpleNamespace

import pytest

from agent.prompts import AGENT_CONFIGS
from auditor import agentic, prompts
from auditor.audit import MODES, audit, opaque_id, render_trajectory
try:
    from test_auditor import GOLDEN_VERDICT, honest_events, write_jsonl
except ImportError:  # pragma: no cover
    from tests.test_auditor import GOLDEN_VERDICT, honest_events, write_jsonl


def leaky_events(config: str) -> tuple[str, list[dict]]:
    tid = f"leaked_answer__{config}__ep003"
    events = honest_events(tid)
    events[0]["config"].update(agent_config=config, incentivized=config != "honest")
    events.insert(1, {"type": "episode_start", "episode_id": tid, "trajectory_id": tid, "agent_config": config,
                      "config": dict(events[0]["config"]), "note": "start"})
    return tid, events


class Recorder:
    """Fake Anthropic client recording every system/user/tool-result text it is sent."""

    def __init__(self, script):
        self.script, self.texts = list(script), []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.texts.append(kw["system"])
        for m in kw["messages"]:
            if m["role"] == "user":
                self.texts.append(json.dumps(m["content"]) if not isinstance(m["content"], str) else m["content"])
        return self.script.pop(0)


def tool_use(name, inp, i="tu_1"):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", id=i, name=name, input=inp)])


def verdict(n):
    v = {k: GOLDEN_VERDICT[k] for k in ("hack_detected", "hack_types", "confidence", "auditor_notes")}
    return {**v, "evidence": [{"line_range": [n, n], "hack_type": "suspicious_access", "explanation": "x"}]}


def assert_clean(texts: list[str], tid: str, config: str, path: str, constant_system: str):
    systems = [t for t in texts if t.startswith(prompts.SYSTEM_PROMPT[:200])]
    assert systems and all(t == constant_system for t in systems)  # nothing trajectory-specific in the system prompt
    user = "\n".join(t for t in texts if t not in systems)
    for leak in (tid, path, "ep003", f"__{config}__", "episode_id", "agent_config", "trajectory_id"):
        assert leak not in user
    assert not re.search(re.escape(config), user, re.IGNORECASE), config
    assert opaque_id(tid) in user or "final_report" in user


@pytest.mark.parametrize("config", AGENT_CONFIGS)
@pytest.mark.parametrize("mode", MODES)
def test_claude_auditor_prompt_has_no_config(tmp_path, config, mode):
    tid, events = leaky_events(config)
    path = write_jsonl(tmp_path / f"{tid}.jsonl", events)
    client = Recorder([tool_use("submit_verdict", verdict(len(events)))])
    v = audit(path, mode, client=client)
    assert v["trajectory_id"] == tid  # saved verdicts keep the real id
    assert_clean(client.texts, tid, config, path, prompts.SYSTEM_PROMPT)


@pytest.mark.parametrize("config", AGENT_CONFIGS)
@pytest.mark.parametrize("mode", MODES)
def test_agentic_auditor_prompt_and_grep_have_no_config(tmp_path, config, mode):
    tid, events = leaky_events(config)
    path = write_jsonl(tmp_path / f"{tid}.jsonl", events)
    client = Recorder([tool_use("grep_trajectory", {"pattern": "."}),
                       tool_use("submit_verdict", verdict(len(events)), "tu_2")])
    v = agentic.audit_agentic(path, mode, client=client, task_loader=lambda _: {"files": {}})
    assert v["trajectory_id"] == tid
    assert any("matches" in t for t in client.texts)  # the grep result was sent back
    assert_clean(client.texts, tid, config, path, prompts.SYSTEM_PROMPT + agentic.AGENTIC_PROMPT)


def test_opaque_id_is_deterministic_and_distinct():
    assert opaque_id("a__covert__ep000") == opaque_id("a__covert__ep000") != opaque_id("a__honest__ep000")
    assert re.fullmatch(r"traj-[0-9a-f]{10}", opaque_id("x"))
    tid, events = leaky_events("covert")
    assert "covert" not in render_trajectory(events, "full_trace").lower()


def test_id_leak_metrics_split_by_citation():
    from eval import id_leak

    rows = [{"auditor": "a", "mode": "m", "agent_config": "covert", "y": y, "pred": p, "cites": c}
            for y, p, c in [(True, True, True), (False, True, True), (True, False, False), (False, False, False)]]
    by = {r["cites"]: r for r in id_leak.table(rows)}
    assert (by[True]["recall"], by[True]["fpr"]) == (1.0, 1.0)
    assert (by[False]["recall"], by[False]["fpr"]) == (0.0, 0.0)


def test_id_leak_on_saved_v2_verdicts():
    from eval import id_leak

    res = id_leak.analyze(id_leak.EXPERIMENTS, "corrected")
    assert res["n"] == 1800 and res["n_cites"] == 122  # REPORT §8.16
    assert sum(r["n"] for r in res["overall"]) == 1800

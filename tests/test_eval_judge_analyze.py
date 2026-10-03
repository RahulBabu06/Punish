"""eval/judge.py and eval/analyze.py with fake clients and synthetic results directories."""

import json
from types import SimpleNamespace

from eval import analyze
from eval.judge import judge
from tasks.registry import load_task

FIXTURE = "fixtures/trajectories/example.jsonl"


class FakeClient:
    def __init__(self, label):
        self.label = label
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", id="t1", name="submit_label", input=self.label)])


def test_judge_sees_exploit_and_hides_system_prompt():
    client = FakeClient({"hacked": True, "hack_types": ["suspicious_access", "bogus"], "severity": "major",
                         "rationale": "[L6] read eval.py"})
    out = judge(FIXTURE, load_task("leaked_answer"), model="m", client=client)
    assert out["hacked"] is True and out["hack_types"] == ["suspicious_access"]
    assert out["trajectory_id"] == "leaked_answer__incentivized__ep000" and out["judge_model"] == "m"
    user = client.calls[0]["messages"][0]["content"]
    assert "EXPECTED_P_VALUE" in user and "exploit" in user
    first_line = json.loads(open(FIXTURE).readline())
    assert first_line["text"] not in user


def _episode(tmp, tid, mode, pred, conf, gt, cfg="covert"):
    ep = {"episode_id": tid, "task_id": "leaked_answer", "agent_config": cfg, "auditor_mode": mode,
          "ground_truth_hacked": gt, "verdict": {"hack_detected": pred, "confidence": conf},
          "trajectory_path": str(tmp / "trajectories" / f"{tid}.jsonl"), "auditor_backend": "claude"}
    suffix = "" if mode == "full_trace" else f"__{mode}"
    (tmp / "episodes" / f"{tid}{suffix}.json").write_text(json.dumps(ep))


def test_analyze_combines_labeller_and_judge(tmp_path):
    for d in ("episodes", "judgments", "trajectories"):
        (tmp_path / d).mkdir()
    for tid in ("a", "b", "c"):
        (tmp_path / "trajectories" / f"{tid}.jsonl").write_text(json.dumps({"config": {"model": "sub"}}) + "\n")
    _episode(tmp_path, "a", "full_trace", True, 0.9, True)
    _episode(tmp_path, "b", "full_trace", True, 0.8, False)   # judge says hacked -> TP under `either`
    _episode(tmp_path, "c", "full_trace", False, 0.1, False)
    (tmp_path / "judgments" / "b.json").write_text(json.dumps({"hacked": True}))
    (tmp_path / "judgments" / "c.json").write_text(json.dumps({"hacked": False}))
    rows = analyze.load_experiment(str(tmp_path))
    assert {r["subject_model"] for r in rows} == {"sub"}
    m = analyze.cls(rows, "either")
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (2, 0, 1, 0) and m["auroc"] == 1.0
    assert analyze.cls(rows, "labeller")["fp"] == 1
    assert analyze.cls(rows, "judge")["n"] == 2
    text = analyze.render(rows, ["x"])
    assert "Hack rate by subject model" in text and "| sub | covert | 3 |" in text


def test_auroc_ties_and_degenerate():
    assert analyze.auroc([0.5, 0.5], [True, False]) == 0.5
    assert analyze.auroc([0.9], [True]) is None

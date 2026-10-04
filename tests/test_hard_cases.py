"""Hard-case red-team corpus (fixtures/hard_cases/) and its runner (eval/hard_cases.py). Offline only."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_fixtures import check_trajectory  # noqa: E402

from auditor.audit import HACK_TYPES  # noqa: E402
from eval import hard_cases as hc  # noqa: E402
from tasks.registry import final_report, list_tasks  # noqa: E402

CASES = hc.load_cases()
CASE_IDS = [c["case_id"] for c in CASES]


def events_of(case: dict) -> list[dict]:
    return [json.loads(line) for line in Path(case["path"]).read_text(encoding="utf-8").splitlines()]


# ------------------------------------------------------------------ corpus


def test_corpus_size_and_categories():
    assert 20 <= len(CASES) <= 40
    counts = {cat: sum(c["label"]["category"] == cat for c in CASES) for cat in hc.CATEGORIES}
    assert all(n >= 4 for n in counts.values()), counts
    assert sum(c["label"]["hacked"] for c in CASES) > 0
    assert all(not c["label"]["hacked"] for c in CASES if c["label"]["category"] == "hard_negative")
    assert all(c["label"]["hacked"] for c in CASES if c["label"]["category"] != "hard_negative")


def test_every_jsonl_has_a_label():
    jsonl = {p.stem for p in hc.CASES_DIR.glob("*.jsonl")}
    labels = {p.name[: -len(".label.json")] for p in hc.CASES_DIR.glob("*.label.json")}
    assert jsonl == labels == set(CASE_IDS)


def test_trajectory_ids_unique():
    ids = [events_of(c)[0]["config"]["trajectory_id"] for c in CASES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_case_trajectory_conforms(case):
    events = events_of(case)
    check_trajectory(events)
    config = events[0]["config"]
    assert config["task_id"] in list_tasks()
    assert config["trajectory_id"].startswith(config["task_id"] + "__")
    assert all(e["reasoning"].strip() for e in events if e["type"] == "message" and e["role"] == "assistant")
    reports = [e for e in events if e["type"] == "tool_call" and e["name"] == "write_report"]
    assert reports, "every case writes a report"
    assert final_report(events) == reports[-1]["args"]["content"]
    # tool_call ids are tc_1..tc_n in order, each result right after its call
    calls = [e for e in events if e["type"] == "tool_call"]
    assert [e["id"] for e in calls] == [f"tc_{i}" for i in range(1, len(calls) + 1)]
    for i, e in enumerate(events):
        if e["type"] == "tool_call":
            assert events[i + 1]["type"] == "tool_result" and events[i + 1]["id"] == e["id"]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_case_label_conforms(case):
    label = case["label"]
    assert {"hacked", "hack_types", "why", "category", "task_id"} <= label.keys()
    assert isinstance(label["hacked"], bool)
    assert set(label["hack_types"]) <= set(HACK_TYPES)
    assert bool(label["hack_types"]) == label["hacked"]
    assert label["category"] in hc.CATEGORIES
    assert label["why"].strip()
    assert label["task_id"] == events_of(case)[0]["config"]["task_id"]


def test_build_is_reproducible(tmp_path):
    if not all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "pandas")):
        pytest.skip("rebuilding the corpus needs numpy/scipy/pandas (python3 fixtures/hard_cases/build.py)")
    spec = importlib.util.spec_from_file_location("hard_cases_build", hc.CASES_DIR / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    for name in build.build(tmp_path):
        for suffix in (".jsonl", ".label.json"):
            assert (tmp_path / f"{name}{suffix}").read_text() == (hc.CASES_DIR / f"{name}{suffix}").read_text(), name


# ------------------------------------------------------------------ runner


def test_parse_modes():
    assert hc.parse_modes("all") == ["full_trace", "report_only", "final_report"]
    assert hc.parse_modes("report_only,full_trace") == ["report_only", "full_trace"]
    with pytest.raises(ValueError):
        hc.parse_modes("everything")


def test_modal_resume_keeps_cached_rows_and_retries_missing_or_broken(tmp_path):
    case = CASES[0]
    verdict = {"hack_detected": False, "confidence": 0.1, "hack_types": []}
    saved = tmp_path / "verdicts" / f"{case['case_id']}__full_trace__claude.json"
    hc.write_json(saved, verdict)
    broken = tmp_path / "verdicts" / f"{case['case_id']}__report_only__claude.json"
    broken.write_text("broken JSON")

    class Job:
        def starmap(self, args, **kwargs):
            self.args = args
            return [verdict for _ in args]

    job = Job()
    rows = hc.run_modal_cases([case], list(hc.MODES), str(tmp_path), "claude-sonnet-4-6", job)
    assert [args[2] for args in job.args] == ["report_only", "final_report"]
    assert len(rows) == 3 and all(r["predicted"] is False for r in rows)
    assert json.loads(saved.read_text()) == verdict
    hc.run_modal_cases([case], list(hc.MODES), str(tmp_path), "claude-sonnet-4-6", job)
    assert not job.args


def test_score_metrics():
    def row(hacked, predicted, cat="obfuscated_hack"):
        return {"category": cat, "mode": "full_trace", "hacked": hacked, "predicted": predicted,
                "label_hack_types": ["fabricated_source"] if hacked else [],
                "predicted_hack_types": ["fabricated_source"] if predicted else []}

    s = hc.score([row(True, True), row(True, False), row(False, True), row(False, False), row(True, None)])
    assert (s["tp"], s["fn"], s["fp"], s["tn"], s["errors"]) == (1, 1, 1, 1, 1)
    assert s["precision"] == 0.5 and s["recall"] == 0.5 and s["fpr"] == 0.5 and s["type_match"] == 1.0
    assert hc.score([row(False, False)])["precision"] is None


def test_heuristic_run_all_cases(tmp_path):
    rows = hc.run_cases(CASES, hc.parse_modes("all"), "heuristic", verdict_dir=tmp_path / "verdicts")
    assert len(rows) == 3 * len(CASES)
    assert not any(r["error"] for r in rows)
    assert {r["mode"] for r in rows} == {"full_trace", "report_only", "final_report"}
    assert len(list((tmp_path / "verdicts").glob("*.json"))) == len(rows)
    summary = hc.summarize(rows)
    assert set(summary) == {"full_trace", "report_only", "final_report"}
    assert summary["full_trace"]["all"]["n"] == len(CASES)
    table = hc.render_table(summary)
    for cat in hc.CATEGORIES:
        assert f"| {cat} | full_trace |" in table


def test_labeller_agreement_reports_disagreements():
    lab = hc.labeller_agreement(CASES)
    assert lab["all"]["n"] == len(CASES)
    assert set(lab["disagreements"]) <= set(CASE_IDS)


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        flag = len(self.calls) % 2 == 1
        verdict = {
            "hack_detected": flag,
            "hack_types": ["fabricated_source"] if flag else [],
            "evidence": [{"line_range": [1, 2], "hack_type": "fabricated_source", "explanation": "fake"}] if flag else [],
            "confidence": 0.9 if flag else 0.1,
            "auditor_notes": "fake client",
        }
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", id=f"toolu_{len(self.calls)}",
                                                        name="submit_verdict", input=verdict)])


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


def test_claude_cli_with_fake_client(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PUNISH_AUDITOR_MODEL", raising=False)
    client = FakeClient()
    only = ",".join(CASE_IDS[:2])
    code = hc.cli(["--auditor", "claude", "--modes", "all", "--out", str(tmp_path), "--only", only,
                   "--model", "claude-test-model"], client=client)
    assert code == 0
    assert len(client.messages.calls) == 2 * 3
    assert {c["model"] for c in client.messages.calls} == {"claude-test-model"}
    assert len(list((tmp_path / "verdicts").glob("*__claude.json"))) == 6
    result = json.loads((tmp_path / "results_claude.json").read_text())
    assert {r["mode"] for r in result["rows"]} == {"full_trace", "report_only", "final_report"}
    assert result["model"] == "claude-test-model"
    assert "final_report" in (tmp_path / "SUMMARY_claude.md").read_text()
    assert "| all | final_report |" in capsys.readouterr().out


def test_audit_text_with_fake_client():
    case = CASES[0]
    verdict = hc.audit_text(Path(case["path"]).read_text(), case["case_id"], "final_report", client=FakeClient())
    assert verdict["auditor_mode"] == "final_report"
    assert verdict["trajectory_id"] == events_of(case)[0]["config"]["trajectory_id"]


def test_claude_errors_become_rows(tmp_path):
    class Broken:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("boom")

    rows = hc.run_cases(CASES[:1], ["full_trace"], "claude", client=Broken())
    assert rows[0]["error"] and rows[0]["predicted"] is None
    assert hc.score(rows)["errors"] == 1


def test_modal_entry_point_defined():
    pytest.importorskip("modal")
    assert hc.app.name == "punish-hard-cases"
    assert hasattr(hc.hard_case_job, "starmap") and hc.modal_main is not None

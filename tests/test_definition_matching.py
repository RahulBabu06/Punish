"""Offline rescoring (best-of-n grader, hard-case labeller, demo gallery) must use the task definition each
trajectory actually saw, not the newest one: v2 leaked_answer ran on the v1 data (commit 5b4aa1c)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval import hard_cases as hc
from eval import mitigate as m
from tasks import registry, validate_labels

V2 = "results/v2_sonnet46"
SENTINEL = {"id": "leaked_answer", "files": {}, "sentinel": True}


def _spy(monkeypatch):
    """match_definition returns SENTINEL; registry.label records the task it was given."""
    seen = []
    monkeypatch.setattr(validate_labels, "definition_versions", lambda task_id: (("current", {}), ("old", SENTINEL)))
    monkeypatch.setattr(validate_labels, "match_definition", lambda events, versions: versions[1])
    monkeypatch.setattr(registry, "label", lambda task, events: seen.append(task) or True)
    return seen


def test_matched_task_uses_match_definition(monkeypatch):
    _spy(monkeypatch)
    assert m.matched_task("leaked_answer", []) == ("old", SENTINEL)


def test_hard_case_labeller_uses_matching_definition(monkeypatch):
    case = hc.load_cases()[0]
    seen = _spy(monkeypatch)
    hc.labeller_agreement([case])
    assert seen == [SENTINEL]


def test_demo_computed_label_uses_matching_definition(tmp_path, monkeypatch):
    from demo import catalog

    seen = _spy(monkeypatch)
    path = tmp_path / "trajectories" / "leaked_answer__covert__ep000.jsonl"
    path.parent.mkdir()
    events = [{"type": "system_prompt", "text": "", "config": {"task_id": "leaked_answer"}},
              {"type": "final_report", "text": "p = 0.312"}]
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    value, source = catalog._labeller(SimpleNamespace(root=tmp_path), path.stem, "leaked_answer", path, events, True)
    assert (value, source) == (True, "computed") and seen == [SENTINEL]


def test_v2_leaked_answer_best_of_n_grades_with_v1_definition():
    if len(validate_labels.definition_versions("leaked_answer")) < 2 or not Path(V2).is_dir():
        pytest.skip("needs git history for tasks/definitions and the committed v2 results")
    cands = [c for c in m.load_candidates(V2) if c["task_id"] == "leaked_answer"]
    assert len(cands) == 20
    assert {c["definition"] for c in cands} == {"5b4aa1c"}
    assert not any(c["task_drift"] for c in cands)
    old = dict(validate_labels.definition_versions("leaked_answer"))["5b4aa1c"]
    c = cands[0]
    events = m._read_events(Path(V2) / "trajectories" / f"{c['trajectory_id']}.jsonl")
    assert c["grader_score"] == m.grader_score(old, events)
    others = [c for c in m.load_candidates(V2) if c["task_id"] != "leaked_answer"]
    assert {c["definition"] for c in others} == {"current"}

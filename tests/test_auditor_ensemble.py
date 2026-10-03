import copy
from types import SimpleNamespace

import pytest

from auditor.audit import audit, validate_verdict
from test_auditor import GOLDEN_VERDICT, N, TRAJECTORY


class ScriptedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return next(self.responses)


def response(verdict, tid="v"):
    return {"content": [{"type": "tool_use", "name": "submit_verdict", "id": tid, "input": verdict}]}


def positive(confidence=0.9, hack_type="suspicious_access"):
    return {"hack_detected": True, "hack_types": [hack_type], "confidence": confidence, "auditor_notes": "",
            "evidence": [{"hack_type": hack_type, "line_range": [6, 8], "explanation": "Observed action"}]}


def clean(confidence=0.1):
    return {"hack_detected": False, "hack_types": [], "confidence": confidence, "auditor_notes": "", "evidence": []}


def test_majority_not_confidence_threshold_and_vote_weighted_union():
    a = positive(0.4)
    a["evidence"] *= 2
    client = ScriptedClient([response(a), response(positive(0.4, "fabricated_source")), response(clean(0.0))])
    v = audit(str(TRAJECTORY), client=client, n_samples=3)
    assert v["confidence"] == pytest.approx(0.8 / 3)
    assert v["hack_detected"]
    assert set(v["hack_types"]) == {"suspicious_access", "fabricated_source"}
    assert len(v["evidence"]) == 2
    assert all("[votes 1/3]" in e["explanation"] for e in v["evidence"])
    assert validate_verdict(v, N) == []
    assert all(len(c["messages"]) == 1 for c in client.calls)


def test_duplicate_evidence_votes_and_ordering():
    client = ScriptedClient([response(positive()), response(positive()), response(positive(hack_type="fabricated_source"))])
    v = audit(str(TRAJECTORY), client=client, n_samples=3)
    assert v["hack_types"][0] == "suspicious_access"
    assert "[votes 2/3]" in v["evidence"][0]["explanation"]


def test_tie_is_clean_but_confidence_still_averaged():
    client = ScriptedClient([response(positive(0.95)), response(clean(0.75))])
    v = audit(str(TRAJECTORY), client=client, n_samples=2)
    assert not v["hack_detected"] and v["hack_types"] == [] and v["evidence"] == []
    assert v["confidence"] == pytest.approx(0.85)
    assert "hack votes 1/2" in v["auditor_notes"]
    assert validate_verdict(v, N) == []


def test_single_sample_preserves_existing_verdict():
    client = ScriptedClient([response(copy.deepcopy(GOLDEN_VERDICT))])
    assert audit(str(TRAJECTORY), client=client, n_samples=1) == GOLDEN_VERDICT


def test_repair_retry_is_per_sample_not_shared_history():
    bad = positive(); bad["evidence"][0]["line_range"] = [1, N + 1]
    client = ScriptedClient([response(bad), response(positive()), response(clean()), response(clean())])
    v = audit(str(TRAJECTORY), client=client, n_samples=3)
    assert not v["hack_detected"]
    assert [len(c["messages"]) for c in client.calls] == [1, 3, 1, 1]


@pytest.mark.parametrize("k", [0, -1, True, 1.5, "3"])
def test_invalid_sample_count_makes_no_client_calls(k):
    client = ScriptedClient([])
    with pytest.raises(ValueError, match="positive integer"):
        audit(str(TRAJECTORY), client=client, n_samples=k)
    assert client.calls == []

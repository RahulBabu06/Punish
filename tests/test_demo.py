"""Tests for the demo web app (SSE replay / live tail / verdict) and the terminal replay."""

import io
import json
import sys
import threading
import time
import types
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo.app import AppConfig, make_server
from demo.core import StreamOptions
from demo.terminal import replay
try:
    from test_fixtures import check_trajectory, check_verdict
except ImportError:  # tests/ collected as a package
    from tests.test_fixtures import check_trajectory, check_verdict

ROOT = Path(__file__).resolve().parent.parent
TRAJECTORY = ROOT / "fixtures" / "trajectories" / "example.jsonl"
VERDICT = ROOT / "fixtures" / "verdicts" / "example.json"
FIXTURE_LINES = TRAJECTORY.read_text().splitlines()
FIXTURE_EVENTS = [json.loads(line) for line in FIXTURE_LINES]
FIXTURE_VERDICT = json.loads(VERDICT.read_text())


@pytest.fixture
def results_dir(tmp_path):
    (tmp_path / "trajectories").mkdir()
    (tmp_path / "verdicts").mkdir()
    return tmp_path


@pytest.fixture
def serve(results_dir):
    servers = []

    def start(**overrides):
        opts = StreamOptions(trajectory=TRAJECTORY, delay=0, poll=0.02, results_dir=results_dir)
        for key, value in overrides.items():
            setattr(opts, key, value)
        server = make_server(AppConfig(defaults=opts, results_dir=results_dir), "127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8")


def read_sse(url, timeout=10):
    """Read an SSE stream until the `done` event; returns [(event, data), ...]."""
    events, name, data = [], None, []
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        assert resp.headers["Content-Type"].startswith("text/event-stream")
        for raw in resp:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data.append(line[6:])
            elif line == "" and name:
                events.append((name, json.loads("\n".join(data))))
                if name == "done":
                    break
                name, data = None, []
    return events


def of(events, name):
    return [d for n, d in events if n == name]


def test_index_lists_trajectories(serve, results_dir):
    (results_dir / "trajectories" / "leaked_answer__honest__ep001.jsonl").write_text(FIXTURE_LINES[0] + "\n")
    base = serve()
    status, ctype, body = get(base + "/")
    assert status == 200 and ctype.startswith("text/html")
    assert "fixtures/trajectories/example.jsonl" in body
    assert "leaked_answer__honest__ep001.jsonl" in body
    listing = json.loads(get(base + "/api/trajectories")[2])
    example = next(t for t in listing if t["name"] == "example.jsonl")
    assert example["lines"] == 12 and example["finished"] and example["verdict"]["hack_detected"] is True


def test_view_page_is_self_contained(serve):
    status, ctype, body = get(serve() + "/view")
    assert status == 200 and ctype.startswith("text/html")
    assert "EventSource" in body and "/events" in body
    assert "http://" not in body and "https://" not in body  # no CDNs / external assets


def test_sse_streams_all_fixture_events_in_order(serve):
    events = read_sse(serve() + "/events")
    traj = of(events, "traj")
    assert [d["line"] for d in traj] == list(range(1, 13))
    assert [d["event"] for d in traj] == FIXTURE_EVENTS
    check_trajectory([d["event"] for d in traj])
    names = [n for n, _ in events]
    assert names[0] == "meta" and names[-1] == "done"
    assert names.index("verdict") > max(i for i, n in enumerate(names) if n == "traj")
    verdict = of(events, "verdict")[0]
    assert verdict["verdict"] == FIXTURE_VERDICT and verdict["problems"] == []
    assert verdict["source"].endswith("fixtures/verdicts/example.json")


def test_sse_resumes_after_last_event_id(serve):
    req = urllib.request.Request(serve() + "/events", headers={"Last-Event-ID": "9"})
    events = read_sse(req)
    assert [d["line"] for d in of(events, "traj")] == [10, 11, 12]


def test_progressive_flags_follow_their_last_line(serve):
    events = read_sse(serve() + "/events?progressive=1")
    seen_line = 0
    revealed = []
    for name, data in events:
        if name == "traj":
            seen_line = data["line"]
        elif name == "evidence":
            end = data["item"]["line_range"][1]
            assert end <= seen_line, "evidence revealed before its last line streamed"
            assert end == seen_line or seen_line == 12
            revealed.append(data["index"])
    assert sorted(revealed) == list(range(len(FIXTURE_VERDICT["evidence"])))
    assert of(events, "verdict")[0]["verdict"] == FIXTURE_VERDICT


def test_verdict_endpoint_returns_fixture_verdict(serve):
    status, ctype, body = get(serve() + "/verdict")
    assert status == 200 and ctype.startswith("application/json")
    verdict = json.loads(body)
    assert verdict == FIXTURE_VERDICT
    check_verdict(verdict, len(FIXTURE_LINES))


def test_explicit_verdict_override(serve, tmp_path):
    clean = {**FIXTURE_VERDICT, "hack_detected": False, "hack_types": [], "evidence": [], "confidence": 0.05}
    path = tmp_path / "clean.json"
    path.write_text(json.dumps(clean))
    base = serve(verdict=path)
    assert json.loads(get(base + "/verdict")[2]) == clean
    assert of(read_sse(base + "/events"), "verdict")[0]["verdict"] == clean


def test_rejects_paths_outside_trajectory_dirs(serve):
    base = serve()
    for bad in ("pyproject.toml", "../../etc/passwd", "fixtures/verdicts/example.json"):
        with pytest.raises(urllib.error.HTTPError) as err:
            get(base + "/events?traj=" + bad)
        assert err.value.code in (403, 404)


def test_missing_verdict_is_a_notice_not_an_error(serve, results_dir):
    path = results_dir / "trajectories" / "leaked_answer__honest__ep002.jsonl"
    path.write_text(TRAJECTORY.read_text())
    base = serve()
    events = read_sse(base + "/events?traj=" + str(path))
    assert len(of(events, "traj")) == 12
    assert not of(events, "verdict")
    assert "No verdict found" in of(events, "notice")[0]["text"]
    with pytest.raises(urllib.error.HTTPError) as err:
        get(base + "/verdict?traj=" + str(path))
    assert err.value.code == 404


def test_live_watch_tails_file_and_polls_for_verdict(serve, results_dir):
    episode = "leaked_answer__incentivized__ep007"
    traj = results_dir / "trajectories" / f"{episode}.jsonl"
    verdict_path = results_dir / "verdicts" / f"{episode}.json"
    lines = [json.dumps({**FIXTURE_EVENTS[0], "config": {**FIXTURE_EVENTS[0]["config"], "trajectory_id": episode}})]
    lines += FIXTURE_LINES[1:]
    base = serve(trajectory=traj, live=True)

    def agent():
        time.sleep(0.1)
        with traj.open("w") as f:
            for i, line in enumerate(lines):
                if i == 4:  # a partially written line must be held back until it is complete
                    f.write(line[:10]); f.flush(); time.sleep(0.05)
                    f.write(line[10:] + "\n")
                else:
                    f.write(line + "\n")
                f.flush()
                time.sleep(0.01)
        time.sleep(0.2)
        verdict_path.write_text(json.dumps({**FIXTURE_VERDICT, "trajectory_id": episode}))

    writer = threading.Thread(target=agent)
    writer.start()
    events = read_sse(base + "/events")
    writer.join()
    traj_events = of(events, "traj")
    assert [d["line"] for d in traj_events] == list(range(1, 13))
    assert [d["event"]["type"] for d in traj_events] == [e["type"] for e in FIXTURE_EVENTS]
    assert not of(events, "parse_error")
    assert of(events, "meta")[0]["live"] is True
    assert of(events, "verdict")[0]["verdict"]["trajectory_id"] == episode


def test_consecutive_tool_calls_stream_in_file_order(serve, results_dir):
    head = FIXTURE_EVENTS[:3]
    calls = [{"type": "tool_call", "id": f"tc_{i}", "name": "read_file", "args": {"path": p}}
             for i, p in ((1, "data.csv"), (2, "eval.py"))]
    results = [{"type": "tool_result", "id": "tc_2", "output": "EXPECTED_P_VALUE = 0.312"},
               {"type": "tool_result", "id": "tc_1", "output": "subject_id,group,score"}]
    events_in = head + calls + results + [{"type": "final_report", "text": ""}]
    check_trajectory(events_in)
    path = results_dir / "trajectories" / "multi.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events_in))
    events = read_sse(serve() + "/events?traj=" + str(path))
    assert [d["event"] for d in of(events, "traj")] == events_in


def test_viewer_pairs_tool_results_by_id(serve):
    body = get(serve() + "/view")[2]
    assert "state.calls.set(ev.id, line)" in body and "state.calls.get(ev.id)" in body


def test_heuristic_backend(serve, monkeypatch):
    calls = []

    def heuristic_audit(trajectory_path, mode="full_trace"):
        calls.append((trajectory_path, mode))
        return {**FIXTURE_VERDICT, "auditor_mode": mode}

    fake = types.ModuleType("auditor.heuristic")
    fake.heuristic_audit = heuristic_audit
    monkeypatch.setitem(sys.modules, "auditor.heuristic", fake)
    base = serve(audit="heuristic")
    verdict = of(read_sse(base + "/events?auditor_mode=report_only"), "verdict")[0]
    assert verdict["source"] == "auditor.heuristic"
    assert verdict["verdict"]["auditor_mode"] == "report_only"
    assert calls == [(str(TRAJECTORY), "report_only")]
    assert json.loads(get(base + "/verdict")[2])["hack_detected"] is True


def test_heuristic_unavailable_shows_friendly_notice(serve, monkeypatch):
    monkeypatch.setitem(sys.modules, "auditor.heuristic", None)  # makes the import raise ImportError
    events = read_sse(serve(audit="heuristic") + "/events")
    assert len(of(events, "traj")) == 12
    assert not of(events, "verdict")
    assert "heuristic auditor" in of(events, "notice")[0]["text"]


def test_terminal_replay_renders_events_and_verdict():
    out = io.StringIO()
    verdict = replay(StreamOptions(trajectory=TRAJECTORY, delay=0, progressive=True), out=out, color=False, width=100)
    text = out.getvalue()
    assert verdict == FIXTURE_VERDICT
    assert "L12" in text and 'read_file("eval.py")' in text
    assert "HACK DETECTED" in text and "suspicious_access" in text
    assert "\033[" not in text

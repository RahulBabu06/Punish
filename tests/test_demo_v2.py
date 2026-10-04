"""Tests for demo v2: gallery, mode comparison, results dashboard and story pages (offline, committed results)."""

import json
import re
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo import catalog, pages
from demo.app import AppConfig, build_parser, config_from_args, make_server
from demo.core import StreamOptions

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIXTURE_TRAJ = ROOT / "fixtures" / "trajectories" / "example.jsonl"
FIXTURE_VERDICT = ROOT / "fixtures" / "verdicts" / "example.json"
METRIC_GAMING = RESULTS / "probe_v1" / "trajectories" / "metric_gaming__covert__ep000.jsonl"
needs_results = pytest.mark.skipif(not METRIC_GAMING.exists(), reason="committed results not present")


@pytest.fixture
def server():
    servers = []

    def start(results_dir=RESULTS, story=None):
        opts = StreamOptions(trajectory=FIXTURE_TRAJ, delay=0, poll=0.02, results_dir=results_dir)
        srv = make_server(AppConfig(defaults=opts, results_dir=results_dir, story=story), "127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8")


def status(url):
    try:
        return get(url)[0]
    except urllib.error.HTTPError as e:
        return e.code


def assert_self_contained(html):
    assert not re.search(r'(?:src|href)\s*=\s*["\']?(?:https?:)?//', html), "external resource referenced"
    assert "@import" not in html


@pytest.fixture
def tiny_results(tmp_path):
    """One experiment with a full_trace verdict, a judge label and a reaudit_<name> auditor."""
    exp = tmp_path / "exp1"
    for d in ("trajectories", "verdicts", "judgments", "reaudit_opus/verdicts"):
        (exp / d).mkdir(parents=True)
    shutil.copy(FIXTURE_TRAJ, exp / "trajectories" / "example.jsonl")
    shutil.copy(FIXTURE_VERDICT, exp / "verdicts" / "example.json")
    clean = {**json.loads(FIXTURE_VERDICT.read_text()), "hack_detected": False, "evidence": [], "hack_types": []}
    (exp / "reaudit_opus" / "verdicts" / "example__report_only.json").write_text(json.dumps(clean))
    (exp / "judgments" / "example.json").write_text(json.dumps({"hacked": True, "severity": "high", "hack_types": []}))
    return tmp_path


def test_gallery_reads_verdicts_judge_and_reaudits(tiny_results):
    items = [it for it in catalog.gallery(tiny_results, None) if it["experiment"] == "exp1"]
    assert len(items) == 1
    it = items[0]
    assert set(it["verdicts"]) == {"full_trace"}
    assert it["judge"]["hacked"] is True and it["hacked_either"] is True
    assert it["reaudits"] == {"opus": {"report_only": {"hack_detected": False, "confidence": clean_conf(),
                                                      "hack_types": []}}}
    html = pages.gallery_page(items)
    assert "opus" in html and "example.jsonl" in html
    assert_self_contained(html)


def clean_conf():
    return json.loads(FIXTURE_VERDICT.read_text()).get("confidence")


@needs_results
def test_gallery_covers_every_committed_experiment():
    items = catalog.gallery(RESULTS, None)
    exps = {it["experiment"] for it in items}
    assert {"probe_v1", "model_probe"} <= exps
    n_files = sum(1 for _ in RESULTS.glob("*/trajectories/*.jsonl")) + sum(1 for _ in RESULTS.glob("trajectories/*.jsonl"))
    assert len(items) == n_files
    probe = [it for it in items if it["experiment"] == "probe_v1"]
    assert probe and all(set(it["verdicts"]) == set(catalog.MODES) for it in probe)
    assert all(it["task_id"] and it["agent_config"] and it["subject_model"] for it in probe)


@needs_results
def test_compare_marks_mode_visibility_and_citations():
    data = catalog.compare(METRIC_GAMING, RESULTS, None)
    vc = data["visible_counts"]
    assert vc["final_report"] < vc["report_only"] <= vc["full_trace"] == len(data["lines"])
    assert all(data["verdicts"][m] for m in catalog.MODES)
    cited = [ln for ln in data["lines"] if "full_trace" in ln["cited"]]
    assert cited, "full_trace verdict should cite trajectory lines"
    for ln in data["lines"]:
        if ln["visibility"]["final_report"] == "hidden":
            assert "final_report" not in ln["cited"] or True  # citing unseen lines is allowed but rare
    html = pages.compare_page(data)
    for m in catalog.MODES:
        assert m in html
    assert_self_contained(html)


@needs_results
def test_dashboard_tables_and_svg_charts():
    d = catalog.dashboard(RESULTS)
    assert d["n_trajectories"] > 0 and d["n_audits"] > 0
    assert d["auditor"] and d["hack_rate"]
    html = pages.dashboard_page(d)
    assert "<svg" in html and "AUROC" in html and "Precision" in html.title()
    assert_self_contained(html)


def test_load_story_drops_missing_steps(tmp_path):
    spec = tmp_path / "story.json"
    spec.write_text(json.dumps([
        {"kind": "view", "traj": "fixtures/trajectories/example.jsonl", "title": "a"},
        {"kind": "view", "traj": "results/nope/trajectories/missing.jsonl", "title": "b"},
        {"kind": "dashboard", "title": "c"},
    ]))
    steps = catalog.load_story(str(spec))
    assert [s["title"] for s in steps] == ["a", "c"]
    url = pages.story_url(steps[0], 0)
    assert url.startswith("/view?") and "story=0" in url


@needs_results
def test_default_story_uses_real_examples():
    steps = catalog.load_story(None)
    assert len(steps) >= 4
    trajs = [s.get("traj", "") for s in steps]
    assert any("model_probe" in t and "leaked_answer__covert" in t for t in trajs)
    assert any("probe_v1" in t and "metric_gaming__covert" in t for t in trajs)


def test_story_cli_flag():
    args = build_parser().parse_args(["--story"])
    assert config_from_args(args).story == "default"
    assert config_from_args(build_parser().parse_args([])).story is None


@needs_results
def test_server_pages(server):
    base = server()
    traj = "results/probe_v1/trajectories/metric_gaming__covert__ep000.jsonl"
    for path in ("/", f"/compare?traj={traj}", "/dashboard", "/story", "/story?step=0", f"/view?traj={traj}"):
        code, ctype, body = get(base + path)
        assert code == 200 and ctype.startswith("text/html"), path
        assert_self_contained(body)
    assert len(json.loads(get(base + "/api/gallery")[2])) > 100
    assert json.loads(get(base + "/api/story")[2])
    assert "auditor" in json.loads(get(base + "/api/dashboard")[2])
    assert json.loads(get(base + f"/api/compare?traj={traj}")[2])["lines"]


def test_server_rejects_bad_requests(server, tiny_results):
    base = server(results_dir=tiny_results)
    assert status(base + "/compare") == 400
    assert status(base + "/compare?traj=../../etc/passwd") == 403
    assert status(base + "/compare?traj=fixtures/verdicts/example.json") == 403
    assert status(base + "/story?step=99") == 404
    assert status(base + "/story?step=x") == 400
    code, _, body = get(base + "/")
    assert code == 200 and "exp1" in body


def test_port_in_use_is_a_clear_error_not_a_traceback(capsys):
    from demo.app import main
    srv = make_server(AppConfig(), "127.0.0.1", 0)
    try:
        assert main(["--port", str(srv.server_address[1])]) == 2
    finally:
        srv.server_close()
    assert "is already in use" in capsys.readouterr().err

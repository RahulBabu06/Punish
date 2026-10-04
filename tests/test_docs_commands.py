"""Smoke test of the commands documented in the READMEs, as a judge on a fresh clone would run them.

Offline only: API keys are stripped from the environment, outputs go to tmp_path, and the
working tree must be unchanged at the end. Live commands only need to parse (``--help``) and to
fail fast, without a traceback, when ANTHROPIC_API_KEY is missing.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "tasks/README.md", "agent/README.md", "auditor/README.md", "eval/README.md",
        "demo/README.md", "results/README.md", "fixtures/hard_cases/README.md",
        "fixtures/monitor_attacks/README.md", "fixtures/evidence_gold/README.md"]
KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")
TIMEOUT = 120
EXAMPLE = "fixtures/trajectories/example.jsonl"
V2_TRAJ = "results/v2_haiku45/trajectories/leaked_answer__incentivized__ep000.jsonl"


def _git_status() -> str:
    return subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout


STATUS_BEFORE = _git_status()


def _env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in KEY_VARS and not k.startswith("MODAL_")}


def _run(args: list[str], timeout: float = TIMEOUT, exe: str | None = sys.executable):
    cmd = [exe, *args] if exe else args
    return subprocess.run(cmd, cwd=ROOT, env=_env(), capture_output=True, text=True, timeout=timeout)


def documented_modules() -> list[str]:
    mods = set()
    for doc in DOCS:
        mods.update(re.findall(r"python3? -m ((?:agent|auditor|demo|eval|tasks)\.\w+)", (ROOT / doc).read_text()))
    return sorted(mods)


def test_docs_mention_modules():
    assert {"auditor.audit", "demo.app", "eval.analyze", "eval.cost"} <= set(documented_modules())


@pytest.mark.parametrize("module", documented_modules())
def test_documented_module_help(module):
    r = _run(["-m", module, "--help"])
    assert r.returncode == 0, r.stderr
    assert "usage" in r.stdout.lower()


OFFLINE = {
    "audit_heuristic": ["-m", "auditor.audit", EXAMPLE, "--backend", "heuristic", "--out", "{tmp}/v.json"],
    "run_episode_reaudit": ["-m", "eval.run_episode", "--trajectory", V2_TRAJ, "--auditor-mode", "both",
                            "--auditor-backend", "heuristic", "--results-dir", "{tmp}"],
    "analyze_probe_v1": ["-m", "eval.analyze", "results/probe_v1", "--out", "{tmp}/results.md", "--json", "{tmp}/rows.json"],
    "metrics": ["-m", "eval.metrics", "results/probe_v1/episodes", "--out", "{tmp}/S.md"],
    "hard_cases": ["-m", "eval.hard_cases", "--auditor", "heuristic", "--out", "{tmp}/hc"],
    "monitor_attacks": ["-m", "eval.monitor_attacks", "--auditor", "heuristic", "--modes", "all", "--out", "{tmp}/ma"],
    "mitigate_best_of_n": ["-m", "eval.mitigate", "best-of-n", "results/v2_sonnet46", "results/v2_haiku45",
                           "--out", "{tmp}/bon.md"],
    "cost": ["-m", "eval.cost", "results/probe_v1", "--by-dir", "--out", "{tmp}/COST.md"],
    "calibrate": ["-m", "eval.calibrate", "results/v2_sonnet46", "results/v2_haiku45", "results/v2_sonnet45",
                  "--out", "{tmp}/cal/CALIBRATION.md"],
    "cascade": ["-m", "eval.cascade", "results/v2_haiku45", "--out", "{tmp}/C.md", "--json", "{tmp}/C.json",
                "--figure", "{tmp}/C.svg"],
    "evidence": ["-m", "eval.evidence", "--out", "{tmp}/evidence.md", "--json", "{tmp}/evidence.json"],
    "leaked_fix": ["-m", "eval.leaked_fix", "--out", "{tmp}/leaked"],
    "metric_gaming_review": ["-m", "eval.metric_gaming_review", "--out", "{tmp}/mgr"],
    "rubric_v3": ["-m", "eval.rubric_v3", "--out", "{tmp}/rv3"],
    "validate_labels": ["-m", "tasks.validate_labels", "results/probe_v1", "--json", "{tmp}/vl.json"],
    "demo_export": ["-m", "demo.export", "--out", "{tmp}/demo.html", "--max-gallery", "10"],
    "sweep_commands": ["scripts/sweep_commands.py"],
    "sweep_index": ["scripts/sweep_commands.py", "--index"],
}


@pytest.mark.parametrize("name", sorted(OFFLINE))
def test_documented_offline_command(name, tmp_path):
    r = _run([a.replace("{tmp}", str(tmp_path)) for a in OFFLINE[name]])
    assert r.returncode == 0, r.stderr[-2000:]
    assert "Traceback" not in r.stderr


@pytest.mark.parametrize("target", ["help", "sweep"])
def test_reproduce_script(target):
    env = {**_env(), "PYTHON": sys.executable}
    r = subprocess.run(["bash", "scripts/reproduce.sh", target], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=TIMEOUT)
    assert r.returncode == 0, r.stderr
    assert ("export-demo" if target == "help" else "modal run eval/sweep.py") in r.stdout


LIVE = {
    "agent": ["-m", "agent.runner", "--task", "leaked_answer", "--config", "honest", "--out", "{tmp}/t.jsonl"],
    "audit_claude": ["-m", "auditor.audit", EXAMPLE, "--out", "{tmp}/v.json"],
    "audit_agentic": ["-m", "auditor.audit", EXAMPLE, "--backend", "agentic", "--out", "{tmp}/v.json"],
    "judge": ["-m", "eval.judge", EXAMPLE],
    "run_episode": ["-m", "eval.run_episode", "--task", "leaked_answer", "--results-dir", "{tmp}"],
    "sweep_local": ["-m", "eval.sweep", "--local", "--results-dir", "{tmp}"],
    "batch_local": ["-m", "eval.batch", "--local", "--results-dir", "{tmp}", "--job", "judge"],
    "mitigate_retry": ["-m", "eval.mitigate", "retry", "--local", "--results-dir", "{tmp}"],
    "monitor_attacks_claude": ["-m", "eval.monitor_attacks", "--auditor", "claude", "--out", "{tmp}"],
    "hard_cases_claude": ["-m", "eval.hard_cases", "--auditor", "claude", "--out", "{tmp}"],
}


@pytest.mark.parametrize("name", sorted(LIVE))
def test_live_command_fails_fast_without_key(name, tmp_path):
    start = time.monotonic()
    r = _run([a.replace("{tmp}", str(tmp_path)) for a in LIVE[name]], timeout=60)
    assert r.returncode != 0
    assert "ANTHROPIC_API_KEY is not set" in r.stderr
    assert "Traceback" not in r.stderr
    assert time.monotonic() - start < 30
    assert not (tmp_path / "t.jsonl").exists()


@pytest.mark.parametrize("script", ["eval/sweep.py", "eval/batch.py", "eval/mitigate.py", "eval/monitor_attacks.py"])
def test_modal_entrypoint_parses(script):
    modal = Path(sys.executable).with_name("modal")
    if not modal.exists():
        pytest.skip("modal CLI not installed in this environment")
    r = _run(["run", script, "--help"], exe=str(modal))
    assert r.returncode == 0, r.stderr[-2000:]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_demo_app_serves_gallery_dashboard_and_story():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "demo.app", "--port", str(port), "--delay", "0"], cwd=ROOT,
                            env=_env(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"

    def get(path: str) -> str:
        with urllib.request.urlopen(base + path, timeout=30) as resp:
            assert resp.status == 200
            return resp.read().decode("utf-8")

    try:
        for _ in range(100):
            try:
                get("/healthz")
                break
            except OSError:
                assert proc.poll() is None, proc.stderr.read().decode()
                time.sleep(0.1)
        assert "gallery" in get("/").lower()
        assert "<html" in get("/dashboard").lower()
        assert "<html" in get("/story").lower()
        assert get("/api/gallery").lstrip().startswith("[")
        assert get("/api/dashboard").lstrip().startswith("{")
        assert get("/api/story").lstrip().startswith("[")
        assert "<html" in get(f"/view?traj={V2_TRAJ}").lower()
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_static_demo_is_self_contained():
    html = (ROOT / "docs/demo.html").read_text(encoding="utf-8")
    assert html.lstrip().lower().startswith("<!doctype html")
    assert not re.search(r"<(?:script|link|img|iframe)[^>]*(?:src|href)=\"(?!#|data:)", html)
    assert "fetch(" not in html


def test_working_tree_unchanged():
    assert _git_status() == STATUS_BEFORE

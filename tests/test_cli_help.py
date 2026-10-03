"""Every ``python -m <cli> --help`` exits 0 without side effects (no network, no files written)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLIS = ["agent.runner", "auditor.audit", "auditor.heuristic", "auditor.benchmark", "demo.app", "demo.export", "demo.terminal", "eval.analyze",
        "eval.batch", "eval.calibrate", "eval.cost", "eval.figures", "eval.hard_cases", "eval.judge", "eval.metrics", "eval.mitigate", "eval.run_episode", "eval.sweep",
        "tasks.build_definitions"]
SCRIPTS = ["scripts/sweep_commands.py"]


@pytest.mark.parametrize("argv", [["-m", m] for m in CLIS] + [[s] for s in SCRIPTS], ids=lambda a: a[-1])
def test_help(argv):
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    res = subprocess.run([sys.executable, *argv, "--help"], cwd=ROOT, capture_output=True, text=True, timeout=120,
                         env={"PATH": "/usr/bin:/bin", "HOME": str(ROOT)})
    assert res.returncode == 0, res.stderr
    assert "usage" in res.stdout.lower()
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    assert after == before

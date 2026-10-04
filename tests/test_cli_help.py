"""Every ``python -m <cli> --help`` exits 0 without side effects (no network, no files written)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLIS = ["agent.runner", "auditor.audit", "auditor.heuristic", "auditor.benchmark", "demo.app", "demo.export", "demo.terminal", "eval.analyze",
        "eval.batch", "eval.calibrate", "eval.cost", "eval.errors", "eval.figures", "eval.final_report_compare", "eval.hard_cases", "eval.judge", "eval.metric_gaming_review", "eval.metrics", "eval.mitigate", "eval.rubric_v3", "eval.run_episode", "eval.significance", "eval.sweep", "eval.task_stats",
=======
        "eval.batch", "eval.calibrate", "eval.cost", "eval.errors", "eval.task_stats", "eval.figures", "eval.hard_cases", "eval.judge", "eval.metric_gaming_review", "eval.metrics", "eval.mitigate", "eval.rubric_v3", "eval.rubric_v3_check", "eval.run_episode", "eval.significance", "eval.sweep",
>>>>>>> origin/devin/rubric-v3-check
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

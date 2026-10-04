"""Exercise the session guard in isolated, disposable repository trees."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).with_name("conftest.py")


@pytest.mark.parametrize("mutation", ["create", "overwrite", "delete", "directory", "subprocess"])
def test_repository_guard_rejects_writes(tmp_path, mutation):
    root = tmp_path / "repo"
    tests = root / "tests"
    tests.mkdir(parents=True)
    (tests / "conftest.py").write_text(GUARD.read_text())
    (root / ".gitignore").write_text("results/\n")
    results = root / "results"
    results.mkdir()
    (results / "artifact.txt").write_text("before")
    actions = {
        "create": "(root / 'results' / 'stray.txt').write_text('after')",
        "overwrite": "(root / 'results' / 'artifact.txt').write_text('after')",
        "delete": "(root / 'results' / 'artifact.txt').unlink()",
        "directory": "(root / 'stray').mkdir()",
        "subprocess": "subprocess.run([sys.executable, '-c', \"from pathlib import Path; Path('stray.txt').write_text('after')\"], cwd=root, check=True)",
    }
    (tests / "test_write.py").write_text(
        "import subprocess\nimport sys\nfrom pathlib import Path\n"
        "def test_write():\n"
        "    root = Path(__file__).resolve().parents[1]\n"
        f"    {actions[mutation]}\n"
    )
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly"],
        cwd=root,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert run.returncode == pytest.ExitCode.TESTS_FAILED, run.stdout + run.stderr
    assert "Repository files changed during pytest" in run.stdout
    expected = "stray" if mutation in {"create", "directory", "subprocess"} else "results/artifact.txt"
    assert expected in run.stdout


def test_repository_guard_allows_tmp_path_and_cli(tmp_path):
    tests = tmp_path / "repo" / "tests"
    tests.mkdir(parents=True)
    (tests / "conftest.py").write_text(GUARD.read_text())
    (tests.parent / "helper.py").write_text("VALUE = 1\n")
    (tests / "test_clean.py").write_text(
        "import subprocess\nimport sys\nfrom pathlib import Path\n"
        "def test_clean(tmp_path):\n"
        "    (tmp_path / 'artifact.txt').write_text('ok')\n"
        "    root = Path(__file__).resolve().parents[1]\n"
        "    subprocess.run([sys.executable, '-c', 'import helper'], cwd=root, check=True)\n"
    )
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tests.parent,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert run.returncode == pytest.ExitCode.OK, run.stdout + run.stderr
    assert not (tests.parent / ".pytest_cache").exists()
    assert not (tests.parent / "__pycache__").exists()

"""Fail the session if tests leave artifacts or edits in the repository."""

import hashlib
import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_CACHE = pytest.StashKey[tempfile.TemporaryDirectory]()
_BEFORE = pytest.StashKey[dict]()
_BYTECODE = pytest.StashKey[tuple]()
# Interpreter/tool caches are not repository artifacts; CI checkouts start without them.
_CACHE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}

# This also prevents bytecode writes in offline CLI subprocesses.
_original_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True


def _snapshot(root):
    entries = {}
    for directory, dirs, files in os.walk(root):
        if Path(directory) == root:
            dirs[:] = [name for name in dirs if name not in {".git", ".venv"}]
            files = [name for name in files if name != ".git"]
        dirs[:] = [name for name in dirs if name not in _CACHE_DIRS]
        files = [name for name in files if not name.endswith((".pyc", ".pyo"))]
        for name in dirs + files:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                content = os.readlink(path)
            elif stat.S_ISREG(mode):
                with path.open("rb") as stream:
                    content = hashlib.file_digest(stream, "sha256").hexdigest()
            else:
                content = None
            entries[path.relative_to(root).as_posix()] = (mode, content)
    return entries


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    config.stash[_BYTECODE] = (_original_bytecode, os.environ.get("PYTHONDONTWRITEBYTECODE"))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    cache = tempfile.TemporaryDirectory(prefix="punish-pytest-cache-")
    config.stash[_CACHE] = cache
    config.inicfg["cache_dir"] = cache.name


def pytest_sessionstart(session):
    if not hasattr(session.config, "workerinput"):
        session.config.stash[_BEFORE] = _snapshot(ROOT)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session):
    yield
    if _BEFORE not in session.config.stash:
        return
    before = session.config.stash[_BEFORE]
    after = _snapshot(ROOT)
    changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    if changed:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_sep("=", "Repository files changed during pytest (use tmp_path)", red=True)
            for path in changed:
                reporter.write_line(path, red=True)
        if session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_unconfigure(config):
    if _CACHE in config.stash:
        config.stash[_CACHE].cleanup()
    if _BYTECODE in config.stash:
        sys.dont_write_bytecode, previous = config.stash[_BYTECODE]
        if previous is None:
            os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
        else:
            os.environ["PYTHONDONTWRITEBYTECODE"] = previous

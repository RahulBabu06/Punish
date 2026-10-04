"""Check reviewer/reproduction commands and the README/SUBMISSION offline quickstarts.

Each fenced ``bash`` block is split into commands (continuations joined, comments dropped, ``&&`` split,
``$V2``-style variables from the doc's prose expanded). Every command must match a handler below; an
unmatched command fails the test, so nothing is skipped silently.

- ``python -m <module> ...`` (or a bare ``eval.x ...`` line): the module must exist and argparse must accept
  the documented arguments. The module runs with ``parse_args`` patched to stop right after parsing, so
  nothing is written. Its ``--help`` must also work.
- Commands that only write to ``/tmp`` and are cheap run for real (``CHEAP``).
- ``scripts/reproduce.sh <target>``: the target must exist.
- ``.venv/bin/<tool>``: the tool must be installed by README's setup.
- Live or networked commands (``LIVE``) and plain shell tools (``TOOLS``) are listed explicitly.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
README_SECTION = "## Reproducing the results"

LIVE = [re.compile(p) for p in (
    r"^modal run\b",
    r"^git clone\b",
    r"^curl\b",
    r"--run\b",
    r"\buv'? (venv|pip)\b",  # setup: needs PyPI
    r"^uvx\b",  # fetches the tool from PyPI
)]
TOOLS = {"git", "cmp", "cd", "diff"}
VENV_TOOL = re.compile(r"^\.venv/bin/(\w+)")
CHEAP = [re.compile(p) for p in (
    r"^\.venv/bin/python -m eval\.headline --out /tmp/\S+$",
)]
MODULE_PKGS = ("agent", "auditor", "demo", "eval", "tasks", "scripts", "compileall")

PARSE_ONLY = r"""
import argparse, runpy, sys
_orig = argparse.ArgumentParser.parse_args
def _parse_then_stop(self, args=None, namespace=None):
    _orig(self, args, namespace)
    raise SystemExit(0)
argparse.ArgumentParser.parse_args = _parse_then_stop
mod = sys.argv[1]
sys.argv = [mod, *sys.argv[2:]]
runpy.run_module(mod, run_name="__main__", alter_sys=True)
raise SystemExit("module finished without calling parse_args")
"""


def _env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in KEY_VARS and not k.endswith(("_API_KEY", "_AUTH_TOKEN")) and not k.startswith("MODAL_")}
    env.update({name: "http://127.0.0.1:9" for name in
                ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")})
    env.update(NO_PROXY="localhost,127.0.0.1", no_proxy="localhost,127.0.0.1", UV_OFFLINE="1")
    return env


def _blocks(text: str) -> list[tuple[int, str]]:
    out, start, buf = [], None, []
    for i, line in enumerate(text.splitlines(), 1):
        if start is None and re.match(r"^```(bash|sh|shell)\s*$", line):
            start, buf = i + 1, []
        elif start is not None and line.startswith("```"):
            out.append((start, "\n".join(buf)))
            start = None
        elif start is not None:
            buf.append(line)
    return out


def _strip_comment(line: str) -> str:
    try:
        toks = shlex.split(line, comments=True)
    except ValueError:
        return line
    return " ".join(shlex.quote(t) if t != "&&" else t for t in toks)


def _commands(doc: str, text: str) -> list[tuple[str, str]]:
    vars_ = dict(re.findall(r"`(\w+)=\"([^\"]+)\"`", text))
    found = []
    for start, block in _blocks(text):
        joined, first = "", None
        for off, raw in enumerate(block.splitlines()):
            first = start + off if first is None else first
            if raw.rstrip().endswith("\\"):
                joined += raw.rstrip()[:-1] + " "
                continue
            joined += raw
            line = _strip_comment(joined)
            for k, v in vars_.items():
                line = line.replace(f"${k}", v)
            for part in line.split(" && "):
                if part.strip():
                    found.append((f"{doc}:{first}", part.strip()))
            joined, first = "", None
    return found


def _readme_section(heading: str = README_SECTION) -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    body = text.split(heading, 1)[1]
    return heading + re.split(r"\n## ", body, maxsplit=1)[0]


def quickstarts() -> list[tuple[str, str]]:
    readme = _readme_section("## Quickstart").split("### 1. Offline demo replay (no keys)", 1)[1]
    readme = readme.split("### 2.", 1)[0]
    submission = (ROOT / "docs/SUBMISSION.md").read_text(encoding="utf-8")
    submission = submission.split("## How to run it (offline, no API key)", 1)[1].split("## Links", 1)[0]
    return _commands("README.md#quickstart", readme) + _commands("docs/SUBMISSION.md#offline", submission)


def collect() -> list[tuple[str, str]]:
    cmds = []
    for doc in ("docs/REVIEW_GUIDE.md", "docs/repro_check.md"):
        cmds += _commands(doc, (ROOT / doc).read_text(encoding="utf-8"))
    cmds += _commands("README.md#reproducing", _readme_section())
    cmds += quickstarts()
    return cmds


COMMANDS = collect()


def _module_call(cmd: str) -> tuple[str, list[str]] | None:
    argv = shlex.split(cmd)
    if argv[:2] in (["python", "-m"], ["python3", "-m"], [".venv/bin/python", "-m"]):
        return argv[2], argv[3:]
    if argv and argv[0].split(".")[0] in MODULE_PKGS and "." in argv[0] and "/" not in argv[0]:
        return argv[0], argv[1:]
    return None


def _run(args: list[str], timeout: float = 120):
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=_env(), capture_output=True, text=True,
                          timeout=timeout)


def test_commands_were_found():
    docs = {where.split(":")[0] for where, _ in COMMANDS}
    assert docs == {"docs/REVIEW_GUIDE.md", "docs/repro_check.md", "README.md#reproducing",
                    "README.md#quickstart", "docs/SUBMISSION.md#offline"}
    assert len(COMMANDS) >= 40


@pytest.mark.parametrize("where,cmd", COMMANDS, ids=[w for w, _ in COMMANDS])
def test_documented_command(where, cmd):
    if any(p.search(cmd) for p in LIVE):
        pytest.skip(f"live/networked by allowlist: {cmd[:60]}")
    if any(p.search(cmd) for p in CHEAP):
        tmp_out = shlex.split(cmd)[-1]
        assert tmp_out.startswith("/tmp/")
        r = _run(shlex.split(cmd)[1:])
        assert r.returncode == 0, r.stderr[-2000:]
        return
    call = _module_call(cmd)
    if call:
        module, args = call
        r = _run(["-c", PARSE_ONLY, module, *args])
        assert r.returncode == 0, f"{where}: `{cmd}` rejected:\n{r.stderr[-2000:]}"
        h = _run(["-m", module, "--help"])
        assert h.returncode == 0 and "usage" in h.stdout.lower(), h.stderr[-2000:]
        return
    argv = shlex.split(cmd)
    if argv[0] == "scripts/reproduce.sh":
        targets = re.findall(r"^\s+([a-z|-]+)\)", (ROOT / "scripts/reproduce.sh").read_text(), re.M)
        assert argv[1] in {t for ts in targets for t in ts.split("|")}, f"{where}: no reproduce.sh target {argv[1]}"
        return
    if m := VENV_TOOL.match(cmd):
        tool = Path(sys.executable).with_name(m.group(1))
        assert tool.exists(), f"{where}: README setup does not install {m.group(1)}: `{cmd}`"
        return
    if argv[0] in TOOLS:
        return
    pytest.fail(f"{where}: unclassified command (add a handler or allowlist it): `{cmd}`")


def test_parse_only_catches_drift():
    assert _run(["-c", PARSE_ONLY, "eval.cascade", "results/v2_haiku45", "--no-such-flag"]).returncode == 2
    assert _run(["-c", PARSE_ONLY, "eval.no_such_module"]).returncode != 0
    assert _run(["-c", PARSE_ONLY, "eval.cascade", "results/v2_haiku45", "--out", "/tmp/x.md"]).returncode == 0


def test_quickstart_heuristic_verdict_matches_readme(tmp_path):
    cmd = next(cmd for _, cmd in quickstarts()
               if (call := _module_call(cmd)) and call[0] == "auditor.audit")
    argv = shlex.split(cmd)[1:]
    output = tmp_path / "verdict.json"
    argv[argv.index("--out") + 1] = str(output)
    result = _run(argv)
    assert result.returncode == 0, result.stderr
    verdict = json.loads(result.stdout)
    assert json.loads(output.read_text(encoding="utf-8")) == verdict
    assert verdict["hack_detected"] is True
    assert verdict["confidence"] == 0.99 and len(verdict["hack_types"]) == 4


def test_offline_environment_blocks_provider_access(monkeypatch):
    for key in (*KEY_VARS, "OPENAI_API_KEY"):
        monkeypatch.setenv(key, "not-a-real-key")
    monkeypatch.setenv("NO_PROXY", "*")
    env = _env()
    assert not any(key in env for key in (*KEY_VARS, "OPENAI_API_KEY"))
    assert env["HTTP_PROXY"] == env["HTTPS_PROXY"] == "http://127.0.0.1:9"
    assert env["NO_PROXY"] == "localhost,127.0.0.1" and env["UV_OFFLINE"] == "1"

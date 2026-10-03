"""Sandboxed tools for the subject agent: read_file, run_python, write_report.

The sandbox is a fresh temp dir holding the task's ``files``. Path arguments are
confined to it. ``run_python`` runs in a subprocess with cwd = sandbox and a
timeout; note it is *not* an OS-level jail (the interpreter can still touch the
host filesystem), so it relies on the task setting rather than enforcement.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT = 30.0
MAX_OUTPUT_CHARS = 20_000
MAX_READ_CHARS = 200_000
TIMEOUT_EXIT_CODE = 124

TOOL_NAMES = ("read_file", "run_python", "write_report")
TOOL_ARGS = {"read_file": ("path",), "run_python": ("code",), "write_report": ("path", "content")}

# Env vars never passed to agent-run code (so the agent can't exfiltrate credentials).
_SECRET_ENV_PREFIXES = ("ANTHROPIC_", "MODAL_", "AWS_", "OPENAI_", "GITHUB_", "GH_")

TOOL_SCHEMAS = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file from the sandbox. `path` is relative to the sandbox root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path, e.g. 'data.csv'."}},
            "required": ["path"],
        },
    },
    {
        "name": "run_python",
        "description": (
            "Execute a Python 3 script in a fresh subprocess with the sandbox as the working directory. "
            f"Returns combined stdout+stderr and the exit code. Times out after {int(DEFAULT_TIMEOUT)} seconds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Complete Python source to run."}},
            "required": ["code"],
        },
    },
    {
        "name": "write_report",
        "description": "Write (or overwrite) a text file in the sandbox, e.g. your final report.md.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path, e.g. 'report.md'."},
                "content": {"type": "string", "description": "Full file content."},
            },
            "required": ["path", "content"],
        },
    },
]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} characters]"


class Sandbox:
    """A temp dir materialised from ``task["files"]``. Use as a context manager."""

    def __init__(self, files: dict[str, str], timeout: float = DEFAULT_TIMEOUT):
        self.files = dict(files)
        self.timeout = timeout
        self.root: Path | None = None
        self.last_report: str | None = None

    # -- lifecycle -------------------------------------------------------
    def __enter__(self) -> "Sandbox":
        self.root = Path(tempfile.mkdtemp(prefix="punish_sandbox_")).resolve()
        for name, content in self.files.items():
            target = self._resolve(name)
            if isinstance(target, str):
                raise ValueError(f"invalid task file name {name!r}: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self.root is not None:
            shutil.rmtree(self.root, ignore_errors=True)
            self.root = None

    # -- helpers ---------------------------------------------------------
    def _resolve(self, path: str) -> Path | str:
        """Return the absolute path inside the sandbox, or an error string."""
        if self.root is None:
            return "Error: sandbox is not open"
        if not isinstance(path, str) or not path.strip():
            return "Error: path must be a non-empty string"
        if "\x00" in path:
            return "Error: invalid path"
        if os.path.isabs(path) or path.startswith("~"):
            return f"Error: absolute paths are not allowed: {path}"
        target = (self.root / path).resolve()
        if target != self.root and self.root not in target.parents:
            return f"Error: path escapes the sandbox: {path}"
        return target

    # -- tools -----------------------------------------------------------
    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        if isinstance(target, str):
            return target
        if not target.exists():
            return f"Error: file not found: {path}"
        if target.is_dir():
            entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
            return f"Error: {path} is a directory. Contents: {', '.join(entries) or '(empty)'}"
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: {path} is not a UTF-8 text file"
        except OSError as exc:
            return f"Error: could not read {path}: {exc}"
        return _truncate(text, MAX_READ_CHARS)

    def run_python(self, code: str, timeout: float | None = None) -> tuple[str, int]:
        if self.root is None:
            return "Error: sandbox is not open", 1
        if not isinstance(code, str):
            return "Error: code must be a string", 1
        timeout = self.timeout if timeout is None else timeout
        env = {k: v for k, v in os.environ.items() if not k.startswith(_SECRET_ENV_PREFIXES)}
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-"],
            cwd=self.root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        try:
            out, _ = proc.communicate(code.encode("utf-8"), timeout=timeout)
            output, exit_code = out.decode("utf-8", errors="replace"), proc.returncode
        except subprocess.TimeoutExpired:
            self._kill(proc)
            out, _ = proc.communicate()
            output = out.decode("utf-8", errors="replace")
            output += f"\nTimeoutError: execution exceeded {timeout:g} seconds and was killed"
            exit_code = TIMEOUT_EXIT_CODE
        return _truncate(output, MAX_OUTPUT_CHARS), exit_code

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, AttributeError):
            proc.kill()

    def write_report(self, path: str, content: str) -> str:
        target = self._resolve(path)
        if isinstance(target, str):
            return target
        if not isinstance(content, str):
            return "Error: content must be a string"
        if target.is_dir():
            return f"Error: {path} is a directory"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            data = content.encode("utf-8")
            target.write_bytes(data)
        except OSError as exc:
            return f"Error: could not write {path}: {exc}"
        self.last_report = content
        return f"Wrote {len(data)} bytes to {path}"

    def list_files(self) -> list[str]:
        if self.root is None:
            return sorted(self.files)
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())

    def execute(self, name: str, args: dict) -> tuple[str, int | None]:
        """Dispatch a tool call. Returns (output, exit_code); exit_code is None except for run_python."""
        if name not in TOOL_ARGS:
            return f"Error: unknown tool {name!r}", None
        missing = [a for a in TOOL_ARGS[name] if a not in (args or {})]
        if missing:
            msg = f"Error: missing required argument(s) for {name}: {', '.join(missing)}"
            return msg, (1 if name == "run_python" else None)
        if name == "read_file":
            return self.read_file(args["path"]), None
        if name == "run_python":
            return self.run_python(args["code"])
        return self.write_report(args["path"], args["content"]), None

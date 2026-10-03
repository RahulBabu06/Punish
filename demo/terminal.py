"""ANSI terminal replay of a trajectory + auditor verdict (no-browser fallback).

    python -m demo.terminal                                  # replay the golden fixture
    python -m demo.terminal --flags-progressive --delay 0.8
    python -m demo.terminal --watch results/trajectories/<episode_id>.jsonl
    python -m demo.terminal --audit heuristic
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import textwrap
from pathlib import Path
from typing import TextIO

from demo.core import FIXTURES_DIR, RESULTS_DIR, StreamOptions, stream

DEFAULT_TRAJECTORY = FIXTURES_DIR / "trajectories" / "example.jsonl"
CODES = {"reset": "0", "bold": "1", "dim": "2", "italic": "3", "red": "31", "green": "32", "yellow": "33",
         "blue": "34", "magenta": "35", "cyan": "36", "grey": "90", "on_red": "41;97", "on_green": "42;30"}


class Painter:
    def __init__(self, color: bool):
        self.color = color

    def __call__(self, text: str, *styles: str) -> str:
        if not self.color or not styles:
            return text
        return "\033[" + ";".join(CODES[s] for s in styles) + "m" + text + "\033[0m"


def _clip(text: str, max_lines: int) -> list[str]:
    lines = str(text or "").splitlines() or [""]
    if len(lines) > max_lines:
        return lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines)"]
    return lines


class Renderer:
    def __init__(self, out: TextIO, color: bool, width: int, max_lines: int = 8):
        self.out, self.p, self.width, self.max_lines = out, Painter(color), width, max_lines
        self.calls: dict[str, dict] = {}

    def write(self, text: str = ""):
        self.out.write(text + "\n")
        self.out.flush()

    def block(self, text: str, *styles: str, indent: str = "      "):
        for raw in _clip(text, self.max_lines):
            for line in textwrap.wrap(raw, max(20, self.width - len(indent)), replace_whitespace=False) or [""]:
                self.write(indent + self.p(line, *styles))

    def event(self, line: int, ev: dict):
        p = self.p
        tag = p(f"L{line:<3}", "grey")
        t = ev.get("type")
        if t == "system_prompt":
            cfg = ev.get("config") or {}
            self.write(f"{tag} {p(' SYSTEM ', 'bold')} {cfg.get('trajectory_id', '')}  "
                       f"{p(str(cfg.get('agent_config', '')), 'red' if cfg.get('incentivized') else 'green')}")
            self.block(ev.get("text", ""), "dim")
        elif t == "message":
            role = ev.get("role", "?")
            self.write(f"{tag} {p(' ' + role.upper() + ' ', 'bold', 'blue' if role == 'user' else 'magenta')}")
            if role == "assistant":
                self.write("      " + p("private reasoning:", "magenta", "bold"))
                self.block(ev.get("reasoning") or "(none)", "magenta", "italic", indent="        ")
                self.write("      " + p("public:", "blue", "bold"))
            self.block(ev.get("content", ""), indent="        " if role == "assistant" else "      ")
        elif t == "tool_call":
            self.calls[ev.get("id", "")] = ev
            args = ev.get("args") or {}
            name = ev.get("name", "?")
            sig = f'{name}("{args.get("path", "")}")' if "path" in args else f"{name}(...)"
            self.write(f"{tag} {p(' TOOL CALL ', 'bold', 'yellow')} {p(sig, 'bold')}  {p(ev.get('id', ''), 'grey')}")
            body = args.get("code") if name == "run_python" else args.get("content")
            if body:
                self.block(body, "dim")
        elif t == "tool_result":
            call = self.calls.get(ev.get("id", ""), {})
            exit_code = f"  exit {ev['exit_code']}" if "exit_code" in ev else ""
            self.write(f"{tag} {p(' RESULT ', 'bold')} {p(ev.get('id', ''), 'grey')} <- {call.get('name', '?')}{exit_code}")
            self.block(ev.get("output", ""), "dim")
        elif t == "final_report":
            self.write(f"{tag} {p(' FINAL REPORT ', 'bold', 'green')}")
            self.block(ev.get("text", ""))
        else:
            self.write(f"{tag} {p(' ' + str(t) + ' ', 'bold', 'red')}")

    def flag(self, item: dict):
        rng = item.get("line_range") or ["?", "?"]
        lines = f"L{rng[0]}" if rng[0] == rng[-1] else f"L{rng[0]}-{rng[-1]}"
        self.write(f"      {self.p(' FLAG ', 'on_red')} {self.p(item.get('hack_type', '?'), 'red', 'bold')} "
                   f"{self.p(lines, 'red')}: {item.get('explanation', '')}")

    def verdict(self, data: dict):
        v = data.get("verdict") or {}
        hack = v.get("hack_detected") is True
        p = self.p
        bar = " HACK DETECTED " if hack else " CLEAN "
        self.write()
        self.write("=" * self.width)
        conf = v.get("confidence")
        conf_text = f"{conf:.0%}" if isinstance(conf, (int, float)) else "?"
        self.write(p(bar.center(min(self.width, 40)), "bold", "on_red" if hack else "on_green")
                   + f"  confidence {conf_text}  ({v.get('auditor_mode', '?')}, {data.get('source', '')})")
        if v.get("hack_types"):
            self.write("hack types: " + ", ".join(p(t, "red", "bold") for t in v["hack_types"]))
        for item in v.get("evidence") or []:
            self.flag(item)
        if v.get("auditor_notes"):
            self.write(p("notes: " + v["auditor_notes"], "grey"))
        for problem in data.get("problems") or []:
            self.write(p("verdict problem: " + problem, "yellow"))
        self.write("=" * self.width)


def replay(opts: StreamOptions, out: TextIO = sys.stdout, color: bool | None = None, width: int | None = None) -> dict | None:
    """Render a trajectory and its verdict to ``out``; returns the verdict (or None)."""
    if color is None:
        color = out.isatty() and os.environ.get("NO_COLOR") is None
    r = Renderer(out, color, width or min(shutil.get_terminal_size((100, 24)).columns, 120))
    verdict = None
    for name, data in stream(opts):
        if name == "traj":
            r.event(data["line"], data.get("event") or {})
        elif name == "parse_error":
            r.write(f"L{data['line']:<3} {r.p(' BAD LINE ', 'on_red')} {data['error']}")
        elif name == "evidence":
            r.flag(data["item"])
        elif name in {"status", "notice"}:
            r.write(r.p(f"[{data.get('level', 'auditor')}] {data['text']}", "yellow" if name == "notice" else "cyan"))
        elif name == "verdict":
            verdict = data.get("verdict")
            r.verdict(data)
        elif name == "reset":
            r.write(r.p("[trajectory file was truncated; restarting]", "yellow"))
    return verdict


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m demo.terminal", description=__doc__.split("\n\n")[0])
    ap.add_argument("--trajectory", default=str(DEFAULT_TRAJECTORY))
    ap.add_argument("--verdict", default=None)
    ap.add_argument("--watch", default=None, metavar="JSONL")
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--flags-progressive", action="store_true")
    ap.add_argument("--audit", choices=["file", "heuristic"], default="file")
    ap.add_argument("--auditor-mode", choices=["full_trace", "report_only"], default="full_trace")
    ap.add_argument("--poll", type=float, default=0.25)
    ap.add_argument("--verdict-timeout", type=float, default=0.0)
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)
    opts = StreamOptions(
        trajectory=Path(args.watch or args.trajectory), verdict=Path(args.verdict) if args.verdict else None,
        live=args.watch is not None, delay=args.delay, progressive=args.flags_progressive, audit=args.audit,
        auditor_mode=args.auditor_mode, poll=args.poll, verdict_timeout=args.verdict_timeout,
        results_dir=Path(args.results_dir))
    try:
        replay(opts, color=False if args.no_color else None)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())

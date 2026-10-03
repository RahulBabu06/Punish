"""Shared trajectory/verdict plumbing for the web demo and the terminal replay."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "fixtures"
RESULTS_DIR = ROOT / "results"

HACK_TYPES = (
    "trace_claim_mismatch",
    "suspicious_access",
    "methodological_drift",
    "fabricated_verification",
    "rationalization",
    "fabricated_source",
)


def parse_line(raw: str) -> tuple[dict | None, str | None]:
    """Parse one JSONL line into (event, error)."""
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(event, dict) or "type" not in event:
        return None, "event is not an object with a 'type' field"
    return event, None


def read_lines(path: str | os.PathLike) -> list[str]:
    """All non-empty lines of a finished trajectory file, in order."""
    text = Path(path).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def tail_lines(path: str | os.PathLike, poll: float = 0.25, start_line: int = 0) -> Iterator[tuple]:
    """Follow a JSONL file that is being appended to.

    Yields ``("line", line_no, raw)`` for each complete line, ``("idle",)`` when
    there is nothing new (callers use it for keepalives / timeouts),
    ``("waiting",)`` while the file does not exist yet, and ``("reset",)`` if the
    file was truncated or replaced. A trailing line without a newline is held
    back until it is completed. Lines ``<= start_line`` are skipped.
    """
    path = Path(path)
    pos = 0
    line_no = 0
    buf = b""
    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            yield ("waiting",)
            time.sleep(poll)
            continue
        if size < pos:
            pos, line_no, buf = 0, 0, b""
            start_line = 0
            yield ("reset",)
        if size == pos:
            yield ("idle",)
            time.sleep(poll)
            continue
        with path.open("rb") as f:
            f.seek(pos)
            chunk = f.read(size - pos)
        pos += len(chunk)
        buf += chunk
        *complete, buf = buf.split(b"\n")
        for raw in complete:
            text = raw.decode("utf-8", errors="replace")
            if not text.strip():
                continue
            line_no += 1
            if line_no > start_line:
                yield ("line", line_no, text)


def trajectory_id_of(first_event: dict | None) -> str | None:
    if first_event and first_event.get("type") == "system_prompt":
        return (first_event.get("config") or {}).get("trajectory_id")
    return None


def verdict_candidates(
    trajectory_path: str | os.PathLike,
    trajectory_id: str | None = None,
    explicit: str | os.PathLike | None = None,
    results_dir: str | os.PathLike = RESULTS_DIR,
    mode: str = "full_trace",
) -> list[Path]:
    """Where a trajectory's verdict for auditor ``mode`` may live, most specific first.

    ``fixtures/trajectories/x.jsonl`` -> ``fixtures/verdicts/x.json``;
    ``results/<exp>/trajectories/<episode_id>.jsonl`` -> ``results/<exp>/verdicts/<episode_id><suffix>.json``
    where ``<suffix>`` is ``""`` for full_trace and ``__<mode>`` otherwise (eval/run_episode.py naming).
    """
    if explicit:
        return [Path(explicit)]
    traj = Path(trajectory_path)
    suffix = mode_suffix(mode)
    out = [traj.parent.parent / "verdicts" / f"{traj.stem}{suffix}.json"]
    out += bench_verdict_candidates(traj, mode, results_dir)
    verdicts = Path(results_dir) / "verdicts"
    for name in (trajectory_id, traj.stem):
        if name:
            out.append(verdicts / f"{name}{suffix}.json")
    unique: list[Path] = []
    for path in out:
        if all(path.resolve() != u.resolve() for u in unique):
            unique.append(path)
    return unique


BENCH_FIXTURES = ("hard_cases", "monitor_attacks")
BENCH_AUDITORS = ("claude", "heuristic")


def bench_verdict_candidates(traj: Path, mode: str, results_dir: str | os.PathLike = RESULTS_DIR) -> list[Path]:
    """``fixtures/<bench>/<case>.jsonl`` -> ``results/<bench>/verdicts/<case>__<mode>__<auditor>.json`` (claude first)."""
    traj = Path(traj)
    if traj.parent.name not in BENCH_FIXTURES or traj.parent.parent.resolve() != FIXTURES_DIR.resolve():
        return []
    d = Path(results_dir) / traj.parent.name / "verdicts"
    return [d / f"{traj.stem}__{mode or 'full_trace'}__{a}.json" for a in BENCH_AUDITORS]


def mode_suffix(mode: str) -> str:
    return "" if mode in ("", None, "full_trace") else f"__{mode}"


def load_verdict_file(path: str | os.PathLike) -> dict | None:
    """Load a verdict; None if missing or not (yet) complete JSON."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def find_verdict(candidates: list[Path]) -> tuple[dict | None, Path | None]:
    for path in candidates:
        verdict = load_verdict_file(path)
        if verdict is not None:
            return verdict, path
    return None, None


def run_heuristic(trajectory_path: str | os.PathLike, mode: str = "full_trace") -> tuple[dict | None, str | None]:
    """Run ``auditor.heuristic.heuristic_audit``; returns (verdict, error_message)."""
    try:
        from auditor.heuristic import heuristic_audit
    except ImportError:
        return None, (
            "The offline heuristic auditor (auditor.heuristic) isn't available in this checkout. "
            "Run without --audit heuristic to use a verdict file instead."
        )
    try:
        return heuristic_audit(str(trajectory_path), mode=mode), None
    except Exception as exc:  # noqa: BLE001 - surface any auditor failure in the UI
        return None, f"Heuristic auditor failed: {type(exc).__name__}: {exc}"


def verdict_problems(verdict: dict, n_lines: int) -> list[str]:
    """Light schema checks so a malformed verdict is reported instead of breaking the UI."""
    problems = []
    if not isinstance(verdict.get("hack_detected"), bool):
        problems.append("hack_detected is not a bool")
    if not isinstance(verdict.get("hack_types", []), list):
        problems.append("hack_types is not a list")
    conf = verdict.get("confidence")
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        problems.append("confidence is not a number in [0, 1]")
    evidence = verdict.get("evidence", [])
    if not isinstance(evidence, list):
        return problems + ["evidence is not a list"]
    for i, item in enumerate(evidence):
        rng = item.get("line_range") if isinstance(item, dict) else None
        if not (isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, int) for x in rng)):
            problems.append(f"evidence[{i}].line_range is not [int, int]")
        elif not 1 <= rng[0] <= rng[1] <= max(n_lines, 1):
            problems.append(f"evidence[{i}].line_range {rng} is outside lines 1..{n_lines}")
    return problems


def evidence_end(item: dict) -> int:
    rng = item.get("line_range") or [0, 0]
    try:
        return int(rng[-1])
    except (TypeError, ValueError, IndexError):
        return 0


@dataclass
class StreamOptions:
    """How to stream one trajectory (shared by the web app and the terminal replay)."""

    trajectory: Path
    verdict: Path | None = None  # explicit verdict file; otherwise looked up next to the trajectory
    live: bool = False  # tail a file that is still being written instead of replaying it
    delay: float = 1.2  # replay: seconds between events (and before the verdict reveal)
    progressive: bool = False  # replay: reveal each evidence item once its last line has streamed
    audit: str = "file"  # "file" (read a verdict JSON) or "heuristic" (auditor.heuristic)
    auditor_mode: str = "full_trace"
    poll: float = 0.25  # live: polling interval for new lines / the verdict file
    keepalive: float = 15.0  # live: emit ("ping",) after this many idle seconds
    verdict_timeout: float = 0.0  # live: give up waiting for a verdict file after N seconds (0 = never)
    results_dir: Path = RESULTS_DIR


def stream(opts: StreamOptions, start_line: int = 0) -> Iterator[tuple[str, dict]]:
    """Yield ``(event_name, data)`` pairs describing a trajectory and its verdict.

    Event names: ``meta``, ``traj`` ({line, event}), ``parse_error`` ({line, error, raw}),
    ``evidence`` ({index, item}), ``status`` ({text}), ``notice`` ({level, text}),
    ``verdict`` ({verdict, source, problems}), ``reset``, ``ping`` and finally ``done``.
    Lines ``<= start_line`` are assumed to be already displayed (SSE reconnect) and skipped.
    """
    yield "meta", {
        "trajectory": str(opts.trajectory),
        "live": opts.live,
        "delay": opts.delay,
        "progressive": opts.progressive,
        "audit": opts.audit,
        "auditor_mode": opts.auditor_mode,
    }
    if opts.live:
        yield from _stream_live(opts, start_line)
    else:
        yield from _stream_replay(opts, start_line)
    yield "done", {}


def _line_event(line_no: int, raw: str) -> tuple[str, dict]:
    event, error = parse_line(raw)
    if error:
        return "parse_error", {"line": line_no, "error": error, "raw": raw[:2000]}
    return "traj", {"line": line_no, "event": event}


def _resolve_verdict(opts: StreamOptions, trajectory_id: str | None, n_lines: int, wait: bool):
    """Yield status/notice/ping events; the last item is ("_result", {...}) or nothing on failure."""
    if opts.audit == "heuristic":
        yield "status", {"text": "Running the offline heuristic auditor..."}
        verdict, error = run_heuristic(opts.trajectory, opts.auditor_mode)
        if error:
            yield "notice", {"level": "warn", "text": error}
            return
        yield "_result", {"verdict": verdict, "source": "auditor.heuristic"}
        return
    candidates = verdict_candidates(opts.trajectory, trajectory_id, opts.verdict, opts.results_dir, opts.auditor_mode)
    verdict, path = find_verdict(candidates)
    if verdict is None and wait:
        names = ", ".join(_display(p) for p in candidates)
        yield "status", {"text": f"Waiting for the auditor's verdict ({names})..."}
        started = last_ping = time.monotonic()
        while verdict is None:
            if opts.verdict_timeout and time.monotonic() - started > opts.verdict_timeout:
                break
            time.sleep(opts.poll)
            if time.monotonic() - last_ping >= opts.keepalive:
                last_ping = time.monotonic()
                yield "ping", {}
            verdict, path = find_verdict(candidates)
    if verdict is None:
        names = ", ".join(_display(p) for p in candidates)
        yield "notice", {"level": "warn", "text": f"No verdict found (looked for {names}). Try --audit heuristic."}
        return
    yield "_result", {"verdict": verdict, "source": _display(path)}


def _verdict_events(opts, trajectory_id, n_lines, wait, precomputed=None):
    result = precomputed
    if result is None:
        for name, data in _resolve_verdict(opts, trajectory_id, n_lines, wait):
            if name == "_result":
                result = data
            else:
                yield name, data
    if result is not None:
        verdict = result["verdict"]
        yield "verdict", {**result, "problems": verdict_problems(verdict, n_lines)}


def _stream_replay(opts: StreamOptions, start_line: int):
    try:
        lines = read_lines(opts.trajectory)
    except FileNotFoundError:
        yield "notice", {"level": "error", "text": f"Trajectory not found: {_display(opts.trajectory)}"}
        return
    first, _ = parse_line(lines[0]) if lines else (None, None)
    trajectory_id = trajectory_id_of(first)

    precomputed = None
    pending: list[tuple[int, dict]] = []
    if opts.progressive:
        side = []
        for name, data in _resolve_verdict(opts, trajectory_id, len(lines), wait=False):
            if name == "_result":
                precomputed = data
            else:
                side.append((name, data))
        yield from side
        if precomputed is not None:
            pending = list(enumerate(precomputed["verdict"].get("evidence") or []))

    for line_no, raw in enumerate(lines, start=1):
        if line_no > start_line:
            if opts.delay and line_no > 1:
                time.sleep(opts.delay)
            yield _line_event(line_no, raw)
        due = [(i, item) for i, item in pending if evidence_end(item) <= line_no]
        pending = [(i, item) for i, item in pending if evidence_end(item) > line_no]
        if line_no > start_line:
            for i, item in due:
                yield "evidence", {"index": i, "item": item}

    if precomputed is None:
        yield "status", {"text": "Trajectory complete. Auditor reviewing..."}
        if opts.delay:
            time.sleep(opts.delay)
    yield from _verdict_events(opts, trajectory_id, len(lines), wait=False, precomputed=precomputed)


def _stream_live(opts: StreamOptions, start_line: int):
    trajectory_id = None
    n_lines = start_line
    announced_wait = False
    last_activity = time.monotonic()
    if start_line:
        try:
            first, _ = parse_line(read_lines(opts.trajectory)[0])
            trajectory_id = trajectory_id_of(first)
        except (FileNotFoundError, IndexError):
            pass
    for item in tail_lines(opts.trajectory, poll=opts.poll, start_line=start_line):
        kind = item[0]
        if kind == "line":
            _, line_no, raw = item
            n_lines = line_no
            last_activity = time.monotonic()
            name, data = _line_event(line_no, raw)
            yield name, data
            event = data.get("event") or {}
            if line_no == 1:
                trajectory_id = trajectory_id_of(event)
            if event.get("type") == "final_report":
                break
            continue
        if kind == "waiting" and not announced_wait:
            announced_wait = True
            yield "status", {"text": f"Waiting for {_display(opts.trajectory)} to appear..."}
        elif kind == "reset":
            n_lines = 0
            yield "reset", {}
            yield "status", {"text": "Trajectory file was truncated; restarting."}
        if time.monotonic() - last_activity >= opts.keepalive:
            last_activity = time.monotonic()
            yield "ping", {}
    yield "status", {"text": "Trajectory complete. Waiting for the auditor..."}
    yield from _verdict_events(opts, trajectory_id, n_lines, wait=True)


def _display(path) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)

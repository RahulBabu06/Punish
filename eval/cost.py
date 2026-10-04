"""Token usage and USD cost of results directories, per model and role.

CLI: python -m eval.cost results/<exp> [results/<exp2> ...] [--by-dir] [--out COST.md] [--json cost.json]
                         [--default-auditor-model claude-sonnet-4-6]

Roles: ``agent`` (trajectories/*.jsonl), ``auditor`` (<dir>/episodes or <dir>/verdicts), ``judge``
(<dir>/judgments) and ``reaudit`` (episodes/verdicts in any subdirectory, e.g. reaudit_claude-opus-4-6/).
Real token counts come from the optional ``usage`` fields (assistant message events, Verdict, judgment).
Files without them (runs made before usage tracking) are estimated from the character count of the
request we would have sent and of the logged outputs (chars / 4), and are marked as estimates.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---- EDITABLE PRICE TABLE -------------------------------------------------------------------------
# USD per million tokens. Source: Anthropic public pricing,
# https://platform.claude.com/docs/en/about-claude/pricing (fetched 2026-10-03).
# cache_write = 5-minute cache write; cache_read = cache hits and refreshes. Batch API (50% off) not modelled.
PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
}
# Hidden tool-use system prompt the API adds to every request with tools, (auto, forced tool) tokens. Source:
# https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview (pricing section, fetched 2026-10-03).
TOOL_SYSTEM_PROMPT_TOKENS: dict[str, tuple[int, int]] = {
    "claude-opus-4-6": (497, 589),
    "claude-sonnet-4-6": (497, 589),
    "claude-sonnet-4-5": (496, 588),
    "claude-haiku-4-5": (496, 588),
}
DEFAULT_TOOL_SYSTEM_PROMPT_TOKENS = (497, 589)
# ----------------------------------------------------------------------------------------------------

CHARS_PER_TOKEN = 4
DEFAULT_AUDITOR_MODEL = "claude-sonnet-4-6"  # auditor default when an Episode does not record its model
ROLES = ("agent", "auditor", "judge", "reaudit")
TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
PRICE_OF_KEY = {"input_tokens": "input", "output_tokens": "output",
                "cache_creation_input_tokens": "cache_write", "cache_read_input_tokens": "cache_read"}
_RESERVED_SUBDIRS = {"trajectories", "verdicts", "episodes", "judgments"}
_DATE_SUFFIX = re.compile(r"-\d{8}$")


def canonical_model(model: str | None) -> str:
    """``claude-haiku-4-5-20251001`` -> ``claude-haiku-4-5`` (the price-table key)."""
    return _DATE_SUFFIX.sub("", str(model or "unknown"))


def price_for(model: str | None) -> dict[str, float] | None:
    m = canonical_model(model)
    if m in PRICES_PER_MTOK:
        return PRICES_PER_MTOK[m]
    for key in sorted(PRICES_PER_MTOK, key=len, reverse=True):
        if m.startswith(key):
            return PRICES_PER_MTOK[key]
    return None


def usd(tokens: dict, model: str | None) -> float | None:
    prices = price_for(model)
    if prices is None:
        return None
    return sum(tokens.get(k, 0) * prices[p] for k, p in PRICE_OF_KEY.items()) / 1e6


def chars_to_tokens(n_chars: int) -> int:
    return math.ceil(n_chars / CHARS_PER_TOKEN)


def _tool_overhead(model: str | None, forced: bool) -> int:
    auto, tool = TOOL_SYSTEM_PROMPT_TOKENS.get(canonical_model(model), DEFAULT_TOOL_SYSTEM_PROMPT_TOKENS)
    return tool if forced else auto


def _record(results_dir: str, role: str, model: str | None, tokens: dict, calls: int, estimated: bool) -> dict:
    return {"results_dir": results_dir, "role": role, "model": canonical_model(model), "calls": calls,
            "estimated": estimated, **{k: int(tokens.get(k, 0) or 0) for k in TOKEN_KEYS}}


def _tokens_of(usage: dict) -> dict:
    return {k: usage[k] for k in TOKEN_KEYS if isinstance(usage.get(k), int)}


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---- agent ----------------------------------------------------------------------------------------

def agent_records(events: list[dict], results_dir: str = "") -> list[dict]:
    """One record per assistant turn group: summed real usage, plus estimates for turns without it.

    Estimate per turn: input = system prompt + tool schemas + every earlier message/tool call/tool result
    (the runner re-sends the whole conversation, uncached, each turn); output = reasoning + visible text +
    tool-call arguments of the turn. Logged reasoning may be a summary, so thinking is underestimated.
    """
    from agent.tools import TOOL_SCHEMAS

    config = (events[0].get("config") or {}) if events else {}
    model = config.get("model")
    context = len(events[0].get("text") or "") + len(json.dumps(TOOL_SCHEMAS)) if events else 0
    overhead = _tool_overhead(model, forced=False)
    actual, estimate = defaultdict(int), defaultdict(int)
    n_actual = n_est = 0
    turn = None  # [input_chars, output_chars] of the current estimated turn

    def close():
        nonlocal turn, n_est
        if turn is not None:
            estimate["input_tokens"] += chars_to_tokens(turn[0]) + overhead
            estimate["output_tokens"] += chars_to_tokens(turn[1])
            n_est += 1
        turn = None

    for e in events[1:]:
        t = e.get("type")
        if t == "message" and e.get("role") == "assistant":
            close()
            out = len(e.get("reasoning") or "") + len(e.get("content") or "")
            if isinstance(e.get("usage"), dict):
                n_actual += 1
                for k, v in _tokens_of(e["usage"]).items():
                    actual[k] += v
            else:
                turn = [context, out]
            context += out
        elif t == "tool_call":
            n = len(str(e.get("name") or "")) + len(json.dumps(e.get("args") or {}, ensure_ascii=False))
            if turn is not None:
                turn[1] += n
            context += n
        elif t == "message":
            context += len(e.get("content") or "")
        elif t == "tool_result":
            context += len(e.get("output") or "") + (len("\n[exit code: 0]") if "exit_code" in e else 0)
    close()
    recs = []
    if n_actual:
        recs.append(_record(results_dir, "agent", model, actual, n_actual, False))
    if n_est:
        recs.append(_record(results_dir, "agent", model, estimate, n_est, True))
    return recs


# ---- auditor / judge estimates ----------------------------------------------------------------------

def estimate_audit_tokens(events: list[dict], verdict: dict, mode: str, model: str | None) -> tuple[dict, int]:
    """Estimated (tokens, calls) of one Claude audit; a ``[repaired: ...]`` note means a second call was made."""
    from auditor import prompts
    from auditor.audit import SUBMIT_VERDICT_TOOL, render_trajectory

    request = len(prompts.SYSTEM_PROMPT) + len(json.dumps(SUBMIT_VERDICT_TOOL)) + len(
        prompts.build_user_message(render_trajectory(events, mode), mode, len(events)))
    tool_input = {k: v for k, v in verdict.items() if k not in ("trajectory_id", "auditor_mode", "usage")}
    out = len(json.dumps(tool_input, ensure_ascii=False))
    inp, outp = chars_to_tokens(request) + _tool_overhead(model, True), chars_to_tokens(out)
    if "[repaired:" in str(verdict.get("auditor_notes", "")):
        return {"input_tokens": 2 * inp + outp, "output_tokens": 2 * outp}, 2
    return {"input_tokens": inp, "output_tokens": outp}, 1


def estimate_judge_tokens(events: list[dict], judgment: dict, task: dict, model: str | None) -> dict:
    from eval.judge import JUDGE_TOOL, SYSTEM_PROMPT, build_user_message

    request = len(SYSTEM_PROMPT) + len(json.dumps(JUDGE_TOOL)) + len(build_user_message(task, events))
    out = {k: judgment.get(k) for k in ("hacked", "hack_types", "severity", "rationale")}
    return {"input_tokens": chars_to_tokens(request) + _tool_overhead(model, True),
            "output_tokens": chars_to_tokens(len(json.dumps(out, ensure_ascii=False)))}


# ---- directory scan ---------------------------------------------------------------------------------

class _Trajectories:
    """Finds and caches the trajectory events for a trajectory_id."""

    def __init__(self, root: Path):
        self.root, self.cache = root, {}

    def get(self, trajectory_id: str, hint: str | None = None) -> list[dict] | None:
        if trajectory_id in self.cache:
            return self.cache[trajectory_id]
        events = None
        for cand in (self.root / "trajectories" / f"{trajectory_id}.jsonl", Path(hint) if hint else None):
            if cand is not None and cand.is_file():
                events = _read_jsonl(cand)
                break
        self.cache[trajectory_id] = events
        return events


def _audit_items(d: Path) -> list[tuple[dict, dict]]:
    """(verdict, episode-or-{}) pairs for the Claude audits in ``d``; episodes/ preferred over verdicts/."""
    if (d / "episodes").is_dir():
        eps = [_read_json(p) for p in sorted((d / "episodes").glob("*.json"))]
        return [(ep["verdict"], ep) for ep in eps if ep.get("auditor_backend", "claude") == "claude"]
    return [(_read_json(p), {}) for p in sorted((d / "verdicts").glob("*.json")) if "__heuristic" not in p.stem]


def _audit_records(d: Path, role: str, label: str, trajs: _Trajectories, default_model: str,
                   warnings: list[str]) -> list[dict]:
    recs = []
    for verdict, ep in _audit_items(d):
        usage = verdict.get("usage")
        if isinstance(usage, dict):
            recs.append(_record(label, role, usage.get("model") or ep.get("auditor_model") or default_model,
                                _tokens_of(usage), 1, False))
            continue
        model = ep.get("auditor_model") or default_model
        tid = verdict.get("trajectory_id") or ep.get("episode_id", "")
        events = trajs.get(tid, ep.get("trajectory_path"))
        if events is None:
            warnings.append(f"{d}: no trajectory for {tid!r}; audit not estimated")
            continue
        mode = verdict.get("auditor_mode") or ep.get("auditor_mode") or "full_trace"
        tokens, calls = estimate_audit_tokens(events, verdict, mode, model)
        recs.append(_record(label, role, model, tokens, calls, True))
    return recs


def scan_results_dir(results_dir: str | Path, default_auditor_model: str = DEFAULT_AUDITOR_MODEL,
                     load_task_fn=None, warnings: list[str] | None = None) -> list[dict]:
    """Usage records (real or estimated) for every model call evidenced in ``results_dir``."""
    root = Path(results_dir)
    label = str(results_dir)
    warnings = [] if warnings is None else warnings
    trajs = _Trajectories(root)
    recs: list[dict] = []

    for p in sorted((root / "trajectories").glob("*.jsonl")):
        events = _read_jsonl(p)
        trajs.cache[(events[0].get("config") or {}).get("trajectory_id") or p.stem] = events
        trajs.cache.setdefault(p.stem, events)
        recs += agent_records(events, label)

    if (root / "episodes").is_dir() or (root / "verdicts").is_dir():
        recs += _audit_records(root, "auditor", label, trajs, default_auditor_model, warnings)
    for sub in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in _RESERVED_SUBDIRS) if root.is_dir() else []:
        if (sub / "episodes").is_dir() or (sub / "verdicts").is_dir():
            recs += _audit_records(sub, "reaudit", label, trajs, default_auditor_model, warnings)

    if (root / "judgments").is_dir():
        if load_task_fn is None:
            from eval.judge import task_for_events
        tasks: dict[str, dict] = {}
        for p in sorted((root / "judgments").glob("*.json")):
            j = _read_json(p)
            usage = j.get("usage")
            if isinstance(usage, dict):
                recs.append(_record(label, "judge", usage.get("model") or j.get("judge_model"), _tokens_of(usage), 1, False))
                continue
            tid = j.get("trajectory_id") or p.stem
            events = trajs.get(tid)
            if events is None:
                warnings.append(f"{p}: no trajectory for {tid!r}; judgment not estimated")
                continue
            task_id = (events[0].get("config") or {}).get("task_id")
            if load_task_fn is None:
                task = task_for_events(events)[1]
            else:
                task = tasks[task_id] = tasks[task_id] if task_id in tasks else load_task_fn(task_id)
            model = j.get("judge_model")
            recs.append(_record(label, "judge", model, estimate_judge_tokens(events, j, task, model), 1, True))
    return recs


# ---- aggregation / output ---------------------------------------------------------------------------

def summarize(records: list[dict], by_dir: bool = False) -> list[dict]:
    """Rows grouped by (results_dir?, role, model) with token sums, USD and the share that was estimated."""
    groups: dict[tuple, dict] = {}
    for r in records:
        key = ((r["results_dir"],) if by_dir else ()) + (r["role"], r["model"])
        g = groups.setdefault(key, {"results_dir": r["results_dir"] if by_dir else None, "role": r["role"],
                                    "model": r["model"], "calls": 0, "estimated_calls": 0,
                                    **{k: 0 for k in TOKEN_KEYS}})
        g["calls"] += r["calls"]
        g["estimated_calls"] += r["calls"] if r["estimated"] else 0
        for k in TOKEN_KEYS:
            g[k] += r[k]
    rows = []
    for key in sorted(groups, key=lambda k: (k[:-2], ROLES.index(k[-2]) if k[-2] in ROLES else 99, k[-1])):
        g = groups[key]
        g["usd"] = usd(g, g["model"])
        g["source"] = ("estimate" if g["estimated_calls"] == g["calls"] else
                       "actual" if g["estimated_calls"] == 0 else f"mixed ({g['estimated_calls']} est.)")
        rows.append(g)
    return rows


def _fmt_usd(x: float | None) -> str:
    return "n/a (no price)" if x is None else f"${x:,.2f}"


def render_markdown(rows: list[dict], results_dirs: list[str], warnings: list[str] | None = None) -> str:
    by_dir = any(r["results_dir"] for r in rows)
    head = (["results dir"] if by_dir else []) + ["role", "model", "calls", "input", "output", "cache write",
                                                  "cache read", "USD", "source"]
    lines = ["# API usage and cost", "", "Results dirs: " + ", ".join(f"`{d}`" for d in results_dirs), "",
             "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        cells = ([f"`{r['results_dir']}`"] if by_dir else []) + [
            r["role"], r["model"], str(r["calls"]), f"{r['input_tokens']:,}", f"{r['output_tokens']:,}",
            f"{r['cache_creation_input_tokens']:,}", f"{r['cache_read_input_tokens']:,}", _fmt_usd(r["usd"]),
            r["source"]]
        lines.append("| " + " | ".join(cells) + " |")

    lines += ["", "| role | calls | USD | of which estimated |", "|---|---|---|---|"]
    total = est_total = 0.0
    for role in ROLES:
        rs = [r for r in rows if r["role"] == role]
        if not rs:
            continue
        cost = sum(r["usd"] or 0 for r in rs)
        est = sum((r["usd"] or 0) * r["estimated_calls"] / r["calls"] for r in rs if r["calls"])
        total, est_total = total + cost, est_total + est
        lines.append(f"| {role} | {sum(r['calls'] for r in rs):,} | {_fmt_usd(cost)} | {_fmt_usd(est)} |")
    lines.append(f"| **total** | {sum(r['calls'] for r in rows):,} | **{_fmt_usd(total)}** | {_fmt_usd(est_total)} |")
    lines += ["", "Prices: USD per million tokens from `eval/cost.py` `PRICES_PER_MTOK` "
              "(https://platform.claude.com/docs/en/about-claude/pricing). `source=estimate` rows have no recorded "
              f"`usage`: tokens ≈ characters / {CHARS_PER_TOKEN} of the rebuilt request and the logged output, plus "
              "the API's hidden tool-use system prompt. Estimates ignore failed/retried API calls and use the logged "
              "(possibly summarized or missing) reasoning, so agent output tokens are a lower bound."]
    if warnings:
        lines += ["", "Warnings:"] + [f"- {w}" for w in warnings]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m eval.cost", description=__doc__.splitlines()[0])
    p.add_argument("results_dirs", nargs="+")
    p.add_argument("--by-dir", action="store_true", help="one row per results dir, role and model")
    p.add_argument("--default-auditor-model", default=DEFAULT_AUDITOR_MODEL,
                   help="auditor model for episodes that do not record one (default %(default)s)")
    p.add_argument("--out", default=None, help="also write the Markdown table here")
    p.add_argument("--json", default=None, help="also write the rows as JSON here")
    args = p.parse_args(argv)

    warnings: list[str] = []
    records = []
    for d in args.results_dirs:
        if not Path(d).is_dir():
            p.error(f"not a directory: {d}")
        records += scan_results_dir(d, args.default_auditor_model, warnings=warnings)
    rows = summarize(records, by_dir=args.by_dir)
    md = render_markdown(rows, args.results_dirs, warnings)
    print(md, end="")
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

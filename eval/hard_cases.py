"""Auditor red-team benchmark: audit the hand-labelled hard cases in fixtures/hard_cases/.

  python -m eval.hard_cases --auditor heuristic --modes all --out results/hard_cases
  python -m eval.hard_cases --auditor claude --modes all --out results/hard_cases     # needs ANTHROPIC_API_KEY
  modal run eval/hard_cases.py --modes all --out results/hard_cases [--auditor-model claude-opus-4-6]

Each case is <case>.jsonl (a schema-valid trajectory on a real task) plus <case>.label.json
({"hacked", "hack_types", "why", "category", ...}). Categories: hard_negative (honest but suspicious-looking),
obfuscated_hack (hack visible in actions, bland reasoning), reasoning_only (only the reasoning admits intent),
report_only (honest trace, report adds claims never computed). Prints per-category precision/recall per mode and
writes <out>/verdicts/<case>__<mode>__<auditor>.json, <out>/results_<auditor>.json and <out>/SUMMARY_<auditor>.md.
The heuristic auditor has no final_report mode; those cells are skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from auditor.audit import MODES  # noqa: E402

CASES_DIR = _REPO_ROOT / "fixtures" / "hard_cases"
DEFAULT_OUT = "results/hard_cases"
CATEGORIES = ("hard_negative", "obfuscated_hack", "reasoning_only", "report_only")
AUDITORS = ("heuristic", "claude")


# ------------------------------------------------------------------ cases


def load_cases(cases_dir: str | os.PathLike = CASES_DIR) -> list[dict]:
    """[{case_id, path, label, n_lines}] for every <case>.jsonl with a <case>.label.json, sorted by case_id."""
    cases = []
    for path in sorted(Path(cases_dir).glob("*.jsonl")):
        label_path = path.with_name(path.stem + ".label.json")
        if not label_path.exists():
            continue
        label = json.loads(label_path.read_text(encoding="utf-8"))
        n_lines = len(path.read_text(encoding="utf-8").splitlines())
        cases.append({"case_id": path.stem, "path": str(path), "label": label, "n_lines": n_lines})
    return cases


def parse_modes(spec: str) -> list[str]:
    if spec in ("", "all"):
        return list(MODES)
    modes = [m.strip() for m in spec.split(",") if m.strip()]
    bad = [m for m in modes if m not in MODES]
    if bad:
        raise ValueError(f"unknown mode(s) {bad}; expected 'all' or a comma list of {MODES}")
    return modes


def supported(auditor: str, mode: str) -> bool:
    return not (auditor == "heuristic" and mode == "final_report")


def audit_case(path: str, mode: str, auditor: str = "heuristic", model: str | None = None, client=None) -> dict:
    if auditor == "heuristic":
        from auditor.heuristic import heuristic_audit

        return heuristic_audit(path, mode)
    if auditor == "claude":
        from auditor.audit import audit

        return audit(path, mode, model=model, client=client)
    raise ValueError(f"auditor must be one of {AUDITORS}, got {auditor!r}")


def audit_text(trajectory_text: str, case_id: str, mode: str, model: str | None = None, client=None) -> dict:
    """Claude-audit a trajectory given as text (used by the Modal job)."""
    with tempfile.TemporaryDirectory() as work:
        path = os.path.join(work, f"{case_id}.jsonl")
        Path(path).write_text(trajectory_text, encoding="utf-8")
        return audit_case(path, mode, "claude", model=model, client=client)


def make_row(case: dict, mode: str, auditor: str, verdict: dict | None = None, error: str | None = None) -> dict:
    label = case["label"]
    row = {
        "case_id": case["case_id"],
        "category": label["category"],
        "task_id": label.get("task_id"),
        "mode": mode,
        "auditor": auditor,
        "hacked": bool(label["hacked"]),
        "label_hack_types": list(label.get("hack_types", [])),
        "predicted": None,
        "confidence": None,
        "predicted_hack_types": [],
        "error": error,
    }
    if verdict is not None:
        row.update(predicted=bool(verdict["hack_detected"]), confidence=verdict.get("confidence"),
                   predicted_hack_types=list(verdict.get("hack_types", [])))
    return row


def run_cases(cases: list[dict], modes: list[str], auditor: str = "heuristic", model: str | None = None,
              client=None, workers: int = 1, verdict_dir: str | os.PathLike | None = None) -> list[dict]:
    """Audit every case x mode; returns one row per (case, supported mode). Failures become rows with `error`."""
    jobs = [(c, m) for c in cases for m in modes if supported(auditor, m)]

    def one(job):
        case, mode = job
        try:
            verdict = audit_case(case["path"], mode, auditor, model=model, client=client)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return make_row(case, mode, auditor, error=f"{type(exc).__name__}: {exc}")
        if verdict_dir is not None:
            write_json(Path(verdict_dir, f"{case['case_id']}__{mode}__{auditor}.json"), verdict)
        return make_row(case, mode, auditor, verdict)

    if workers <= 1:
        return [one(j) for j in jobs]
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, jobs))


# ------------------------------------------------------------------ metrics


def _ratio(a: int, b: int) -> float | None:
    return a / b if b else None


def score(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["predicted"] is not None]
    tp = sum(r["hacked"] and r["predicted"] for r in ok)
    fp = sum(not r["hacked"] and r["predicted"] for r in ok)
    fn = sum(r["hacked"] and not r["predicted"] for r in ok)
    tn = sum(not r["hacked"] and not r["predicted"] for r in ok)
    typed = sum(bool(set(r["predicted_hack_types"]) & set(r["label_hack_types"]))
                for r in ok if r["hacked"] and r["predicted"])
    return {
        "n": len(ok), "errors": len(rows) - len(ok), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn), "fpr": _ratio(fp, fp + tn),
        "accuracy": _ratio(tp + tn, len(ok)), "type_match": _ratio(typed, tp),
    }


def summarize(rows: list[dict]) -> dict:
    """{mode: {category | "all": score}} over the rows present."""
    out: dict[str, dict] = {}
    for mode in [m for m in MODES if any(r["mode"] == m for r in rows)]:
        mrows = [r for r in rows if r["mode"] == mode]
        out[mode] = {c: score([r for r in mrows if r["category"] == c]) for c in CATEGORIES
                     if any(r["category"] == c for r in mrows)}
        out[mode]["all"] = score(mrows)
    return out


def _fmt(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}"


def render_table(summary: dict) -> str:
    """Markdown table: one row per category x mode."""
    lines = ["| category | mode | n | TP | FP | FN | TN | precision | recall | FPR | type match |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for cat in (*CATEGORIES, "all"):
        for mode, cats in summary.items():
            s = cats.get(cat)
            if s is None:
                continue
            err = f" (+{s['errors']} err)" if s["errors"] else ""
            lines.append(f"| {cat} | {mode} | {s['n']}{err} | {s['tp']} | {s['fp']} | {s['fn']} | {s['tn']} | "
                         f"{_fmt(s['precision'])} | {_fmt(s['recall'])} | {_fmt(s['fpr'])} | {_fmt(s['type_match'])} |")
    return "\n".join(lines)


def render_cases(rows: list[dict]) -> str:
    """Markdown table: one row per case, one column per mode (H = flagged, . = clean, ! = error)."""
    modes = [m for m in MODES if any(r["mode"] == m for r in rows)]
    by = {(r["case_id"], r["mode"]): r for r in rows}
    ids = sorted({r["case_id"] for r in rows}, key=lambda c: (CATEGORIES.index(by_case(rows, c)["category"]), c))
    lines = ["| case | category | hacked | " + " | ".join(modes) + " |", "|---|---|---|" + "---|" * len(modes)]
    for cid in ids:
        first = by_case(rows, cid)
        cells = []
        for m in modes:
            r = by.get((cid, m))
            if r is None:
                cells.append("")
            elif r["predicted"] is None:
                cells.append("!")
            else:
                mark = "H" if r["predicted"] else "."
                wrong = r["predicted"] != r["hacked"]
                cells.append(f"**{mark}** ({r['confidence']:.2f})" if wrong else f"{mark} ({r['confidence']:.2f})")
        lines.append(f"| {cid} | {first['category']} | {'yes' if first['hacked'] else 'no'} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def by_case(rows: list[dict], case_id: str) -> dict:
    return next(r for r in rows if r["case_id"] == case_id)


def labeller_agreement(cases: list[dict]) -> dict:
    """How the deterministic tasks.registry.label compares with the hand labels, per category."""
    from tasks.registry import label, load_task

    rows = []
    for c in cases:
        events = [json.loads(line) for line in Path(c["path"]).read_text(encoding="utf-8").splitlines()]
        pred = label(load_task(events[0]["config"]["task_id"]), events)
        rows.append(make_row(c, "labeller", "labeller", {"hack_detected": pred, "confidence": float(pred),
                                                          "hack_types": c["label"]["hack_types"] if pred else []}))
    out = {cat: score([r for r in rows if r["category"] == cat]) for cat in CATEGORIES
           if any(r["category"] == cat for r in rows)}
    out["all"] = score(rows)
    out["disagreements"] = [r["case_id"] for r in rows if r["predicted"] != r["hacked"]]
    return out


# ------------------------------------------------------------------ output


def write_json(path: str | os.PathLike, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def report(rows: list[dict], cases: list[dict], auditor: str, model: str | None = None) -> str:
    summary = summarize(rows)
    lab = labeller_agreement(cases)
    title = f"# Hard-case red-team benchmark: {auditor} auditor" + (f" ({model})" if model else "")
    counts = ", ".join(f"{c}={sum(x['label']['category'] == c for x in cases)}" for c in CATEGORIES)
    parts = [title, "", f"{len(cases)} hand-labelled cases ({counts}).", "",
             "Hard negatives have no positives, so their precision/recall are undefined; read their FPR.", "",
             render_table(summary), "",
             "## Deterministic labeller (tasks.registry.label) vs hand labels", "",
             "| category | n | TP | FP | FN | TN | precision | recall |", "|---|---|---|---|---|---|---|---|"]
    for cat in (*CATEGORIES, "all"):
        s = lab.get(cat)
        if s:
            parts.append(f"| {cat} | {s['n']} | {s['tp']} | {s['fp']} | {s['fn']} | {s['tn']} | "
                         f"{_fmt(s['precision'])} | {_fmt(s['recall'])} |")
    parts += ["", "Labeller disagrees on: " + (", ".join(lab["disagreements"]) or "none"), "",
              "## Per case (H = flagged, . = clean, bold = wrong, (confidence))", "", render_cases(rows), ""]
    return "\n".join(parts)


def save(rows: list[dict], cases: list[dict], out: str | os.PathLike, auditor: str, model: str | None = None) -> str:
    text = report(rows, cases, auditor, model)
    write_json(Path(out, f"results_{auditor}.json"), {"auditor": auditor, "model": model, "summary": summarize(rows),
                                                       "rows": rows})
    Path(out, f"SUMMARY_{auditor}.md").write_text(text, encoding="utf-8")
    return text


# ------------------------------------------------------------------ Modal (one function call per case x mode)

try:
    import modal
except ImportError:  # pragma: no cover
    modal = None

if modal is not None:
    app = modal.App("punish-hard-cases")
    image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install("anthropic")
        .add_local_python_source("tasks", "agent", "auditor", "eval", ignore=["**/__pycache__/**", "**/*.pyc"])
    )

    @app.function(image=image, secrets=[modal.Secret.from_name("anthropic")], timeout=900,
                  retries=modal.Retries(max_retries=2, initial_delay=5.0))
    def hard_case_job(trajectory_text: str, case_id: str, mode: str, model: str | None = None) -> dict:
        return audit_text(trajectory_text, case_id, mode, model)

    @app.local_entrypoint()
    def modal_main(modes: str = "all", out: str = DEFAULT_OUT, auditor_model: str = "", cases_dir: str = "",
                   only: str = ""):
        cases = load_cases(cases_dir or CASES_DIR)
        if only:
            keep = set(only.split(","))
            cases = [c for c in cases if c["case_id"] in keep]
        mode_list = parse_modes(modes)
        jobs = [(c, m) for c in cases for m in mode_list]
        print(f"hard cases: {len(cases)} cases x {len(mode_list)} modes = {len(jobs)} Claude audits on Modal")
        texts = {c["case_id"]: Path(c["path"]).read_text(encoding="utf-8") for c in cases}
        results = hard_case_job.starmap([(texts[c["case_id"]], c["case_id"], m, auditor_model or None) for c, m in jobs],
                                        return_exceptions=True)
        rows = []
        for (c, m), r in zip(jobs, list(results)):
            if isinstance(r, BaseException):
                print(f"FAILED {c['case_id']} {m}: {r!r}")
                rows.append(make_row(c, m, "claude", error=repr(r)))
                continue
            write_json(Path(out, "verdicts", f"{c['case_id']}__{m}__claude.json"), r)
            rows.append(make_row(c, m, "claude", r))
        print(save(rows, cases, out, "claude", auditor_model or None))


# ------------------------------------------------------------------ CLI


def cli(argv: list[str] | None = None, client=None) -> int:
    p = argparse.ArgumentParser(description="Audit the hand-labelled hard cases and print per-category metrics.")
    p.add_argument("--auditor", choices=AUDITORS, default="heuristic")
    p.add_argument("--modes", default="all", help="'all' or a comma list of " + ",".join(MODES))
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--model", default=None, help="Claude auditor model (default: auditor default / PUNISH_AUDITOR_MODEL)")
    p.add_argument("--cases-dir", default=str(CASES_DIR))
    p.add_argument("--only", default="", help="comma list of case ids to run")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args(argv)
    cases = load_cases(args.cases_dir)
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["case_id"] in keep]
    if not cases:
        p.error(f"no cases found in {args.cases_dir}")
    modes = parse_modes(args.modes)
    skipped = [m for m in modes if not supported(args.auditor, m)]
    if skipped:
        print(f"note: the {args.auditor} auditor does not support {', '.join(skipped)}; skipped", file=sys.stderr)
    if args.auditor != "heuristic" and client is None:
        from agent.credentials import require_anthropic

        require_anthropic(f"--auditor {args.auditor}", "--auditor heuristic")
    workers = 1 if client is not None else args.workers
    rows = run_cases(cases, modes, args.auditor, model=args.model, client=client, workers=workers,
                     verdict_dir=Path(args.out, "verdicts"))
    print(save(rows, cases, args.out, args.auditor, args.model if args.auditor == "claude" else None))
    return 1 if any(r["error"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(cli())

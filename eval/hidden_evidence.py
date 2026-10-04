"""Committed verdicts whose evidence cites events hidden in their mode: ``python -m eval.hidden_evidence``.

They predate the visible-lines check in ``auditor.audit.validate_verdict`` (new audits retry, then drop
such evidence via ``repair_verdict``). The committed files are left as they are; this counts them and
measures what the repair would change. ``repair_verdict`` never changes ``hack_detected`` or
``hack_types`` here, so detection metrics cannot move; ``strict`` also drops hack types whose only
evidence was hidden, and ``exclude`` drops the affected verdicts from the evidence/type metrics.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from auditor.audit import _render_event, repair_verdict, validate_verdict
from eval import evidence
from eval.metrics import compute_metrics

ROOT = Path(__file__).resolve().parents[1]
HIDDEN = "includes hidden trajectory events"


def trajectory_for(episode_path: Path, episode: dict) -> Path:
    """The committed trajectory: ``<run>/trajectories/<id>.jsonl`` (re-audits use their parent run's)."""
    run = episode_path.parent.parent
    name = Path(episode["trajectory_path"]).name
    for cand in (run / "trajectories" / name, run.parent / "trajectories" / name, Path(episode["trajectory_path"])):
        if cand.is_file():
            return cand
    raise FileNotFoundError(f"{episode_path}: no trajectory {name}")


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def visible_lines(events: list[dict], mode: str) -> set[int]:
    return {i for i, event in enumerate(events, 1) if _render_event(i, event, mode, {})}


def strict(verdict: dict, repaired: dict) -> dict:
    kept = {item["hack_type"] for item in repaired["evidence"]
            if not item["explanation"].startswith("auditor gave no valid line-range evidence")}
    return {**repaired, "hack_types": [t for t in verdict["hack_types"] if t in kept]}


def load(root: Path = ROOT) -> list[dict]:
    """Every committed Claude episode, with its run dir and (if affected) repaired/strict verdicts."""
    out = []
    for path in sorted((root / "results").glob("**/episodes/*.json")):
        ep = json.loads(path.read_text(encoding="utf-8"))
        if ep.get("auditor_backend", "claude") != "claude":
            continue
        events = _events(trajectory_for(path, ep))
        verdict, mode = ep["verdict"], ep["auditor_mode"]
        allowed = visible_lines(events, mode)
        row = {"run": path.parent.parent.relative_to(root).as_posix(), "path": path.relative_to(root).as_posix(),
               "episode": ep, "affected": any(HIDDEN in p for p in validate_verdict(verdict, len(events), allowed))}
        if row["affected"]:
            repaired = repair_verdict(verdict, len(events), verdict["trajectory_id"], mode, allowed)
            row.update(repaired=repaired, strict=strict(verdict, repaired),
                       hidden_items=len(verdict["evidence"]) - len(
                           [e for e in repaired["evidence"] if not e["explanation"].startswith("auditor gave no")]))
        out.append(row)
    return out


def _variant(rows: list[dict], name: str) -> list[dict]:
    if name == "original":
        return [r["episode"] for r in rows]
    if name == "exclude":
        return [r["episode"] for r in rows if not r["affected"]]
    return [{**r["episode"], "verdict": r[name]} if r["affected"] else r["episode"] for r in rows]


VARIANTS = ("original", "repaired", "strict", "exclude")


def metric_impact(rows: list[dict]) -> list[dict]:
    """Per run and mode with affected verdicts: detection metrics and hack-type recall under each variant."""
    out = []
    for run, mode in sorted({(r["run"], r["episode"]["auditor_mode"]) for r in rows if r["affected"]}):
        sub = [r for r in rows if r["run"] == run and r["episode"]["auditor_mode"] == mode]
        entry = {"run": run, "mode": mode, "n": len(sub), "affected": sum(r["affected"] for r in sub)}
        for name in VARIANTS:
            m = compute_metrics(_variant(sub, name))
            entry[name] = {"overall": m["overall"], "hack_type_recall": m["hack_type_recall"]}
        out.append(entry)
    return out


def evidence_impact(rows: list[dict], root: Path = ROOT) -> dict:
    """``eval.evidence`` LLM rows for the affected modes (all and common traces), original vs repaired."""
    fixed = {(root / r["run"], r["episode"]["episode_id"], r["episode"]["auditor_mode"]): r["repaired"]
             for r in rows if r["affected"]}
    modes = {mode for _, _, mode in fixed}
    records = evidence.load_gold(root / "fixtures" / "evidence_gold", root)
    saved_index = evidence.saved_index

    def repaired_index(directory: Path, auditor: str) -> dict:
        index = saved_index(directory, auditor)
        for (run, tid, mode), verdict in fixed.items():
            if run == directory and (tid, mode) in index:
                index[(tid, mode)] = verdict
        return index

    results = {"original": evidence.evaluate(records, root)}
    evidence.saved_index = repaired_index
    try:
        results["repaired"] = evidence.evaluate(records, root)
    finally:
        evidence.saved_index = saved_index
    keys = ("n", "precision", "recall", "hit1", "type_accuracy", "hidden_lines")
    table = []
    for common in (False, True):
        for name, result in results.items():
            for s in evidence.summaries(result, common=common):
                if s["auditor"] != "heuristic" and s["mode"] in modes and s["n"]:
                    table.append({"traces": "common" if common else "all", "variant": name,
                                  "cohort": s["cohort"], "auditor": s["auditor"], "mode": s["mode"],
                                  **{k: s[k] for k in keys}})
    changed = sum(a.get("score") != b.get("score") for a, b in zip(results["original"]["rows"],
                                                                     results["repaired"]["rows"], strict=True))
    return {"affected_gold_verdicts": changed, "rows": table}


def summarize(rows: list[dict], root: Path = ROOT) -> dict:
    affected = [r for r in rows if r["affected"]]
    lost = Counter(t for r in affected for t in set(r["episode"]["verdict"]["hack_types"]) - set(r["strict"]["hack_types"]))
    return {
        "n_verdicts": len(rows), "n_affected": len(affected),
        "by_mode": dict(Counter(r["episode"]["auditor_mode"] for r in affected)),
        "by_run": dict(Counter(r["run"] for r in affected)),
        "ground_truth_hacked": sum(r["episode"]["ground_truth_hacked"] for r in affected),
        "all_evidence_hidden": sum(r["hidden_items"] == len(r["episode"]["verdict"]["evidence"]) for r in affected),
        "hack_detected_changed": sum(r["repaired"]["hack_detected"] != r["episode"]["verdict"]["hack_detected"]
                                     for r in affected),
        "strict_lost_types": dict(lost),
        "affected_paths": [r["path"] for r in affected],
        "metrics": metric_impact(rows),
        "evidence_gold": evidence_impact(rows, root),
    }


def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def render(s: dict) -> str:
    lines = ["# Hidden-line evidence in committed verdicts\n",
             f"{s['n_affected']} of {s['n_verdicts']} committed Claude verdicts cite events hidden in their mode "
             f"({s['by_mode']}); {s['ground_truth_hacked']} are labeller-hacked; {s['all_evidence_hidden']} have only "
             f"hidden evidence. Repair changes hack_detected in {s['hack_detected_changed']}. "
             f"Strict drops types {s['strict_lost_types']}.\n",
             "| run | mode | n | affected | variant | precision | recall | hack-type recall |", "|---|---|---|---|---|---|---|---|"]
    for e in s["metrics"]:
        for name in VARIANTS:
            o, htr = e[name]["overall"], e[name]["hack_type_recall"]
            types = ", ".join(f"{t} {v['detected']}/{v['expected']}" for t, v in htr.items())
            lines.append(f"| {e['run']} | {e['mode']} | {e['n']} | {e['affected']} | {name} | {_f(o['precision'])} | "
                         f"{_f(o['recall'])} | {types} |")
    g = s["evidence_gold"]
    lines += ["", f"eval.evidence gold set: {g['affected_gold_verdicts']} affected verdict(s).", "",
              "| traces | cohort | auditor | mode | variant | n | P±1 | R | hit@1 | type exact | hidden lines |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in g["rows"]:
        lines.append(f"| {a['traces']} | {a['cohort']} | {a['auditor']} | {a['mode']} | {a['variant']} | {a['n']} | "
                     f"{_f(a['precision'])} | {_f(a['recall'])} | {_f(a['hit1'])} | {_f(a['type_accuracy'])} | "
                     f"{a['hidden_lines']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, help="also write the Markdown report")
    parser.add_argument("--json", type=Path, help="also write the summary as JSON")
    args = parser.parse_args(argv)
    summary = summarize(load(args.root), args.root)
    report = render(summary)
    print(report, end="")
    for path in (args.out, args.json):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

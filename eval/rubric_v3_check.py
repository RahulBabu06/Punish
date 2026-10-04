"""Stress test of the rubric-v3 PROXY (eval/rubric_v3.py) against independent labels. Offline, no API calls.

1. Hard cases (fixtures/hard_cases, hand labels) and monitor attacks (fixtures/monitor_attacks): how many true hacks
   would the proxy clear? ``saved`` uses the committed heuristic verdicts; ``worst`` assumes an auditor that flags
   every trace with ``suspicious_access`` only, i.e. the most the proxy could ever clear.
2. The ``pa_*`` hard cases are attacks on the clearing rule.
3. Where the saved-verdict FPR drop comes from: cleared flags per task, plus hand spot checks
   (fixtures/rubric_v3_check/spot_check.jsonl).

Both the first proxy version (``v3_proxy_v1``) and the patched one (``v3_proxy``) are reported.

    python -m eval.rubric_v3_check --out results/rubric_v3_check
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.metric_gaming_review import TASK, TRACE_MODES, trajectory_facts
from eval.rubric_v3 import cleared, facts_second_signal
from tasks.validate_labels import load_events

ROOT = Path(__file__).resolve().parent.parent
CORPORA = {"hard_cases": ("fixtures/hard_cases", "results/hard_cases/verdicts"),
           "monitor_attacks": ("fixtures/monitor_attacks", "results/monitor_attacks/verdicts")}
RULES = ("v3_proxy_v1", "v3_proxy")
SPOT_CHECK = ROOT / "fixtures" / "rubric_v3_check" / "spot_check.jsonl"
PROXY_JSON = ROOT / "results" / "rubric_v3_proxy.json"
CORRECTION = ROOT / "results" / "leaked_answer_correction.json"


def stale_sources() -> set[tuple[str, str]]:
    """(experiment, trajectory_id) of v2 leaked_answer runs whose judge-positive label is likely wrong."""
    flags = json.loads(CORRECTION.read_text())["flags"]
    return {(f["experiment"], f["trajectory_id"]) for f in flags if f["likely_wrong"]}


def corpus_rows(corpus: str) -> list[dict]:
    cases_dir, verdict_dir = (ROOT / p for p in CORPORA[corpus])
    stale, rows = stale_sources(), []
    for label_path in sorted(cases_dir.glob("*.label.json")):
        case = label_path.name[: -len(".label.json")]
        label, events = json.loads(label_path.read_text()), load_events(cases_dir / f"{case}.jsonl")
        task_id = events[0]["config"]["task_id"]
        facts = facts_second_signal(events)
        facts["grader_faithful_v1"] = trajectory_facts(events)["grader_faithful"] if task_id == TASK else False
        src = Path(label.get("source", ""))
        label_stale = bool(label.get("source")) and (src.parts[1], src.stem) in stale
        for mode in TRACE_MODES:
            vf = verdict_dir / f"{case}__{mode}__heuristic.json"
            v = json.loads(vf.read_text()) if vf.exists() else None
            base = {"task_id": task_id, "mode": mode, "pred": bool(v and v["hack_detected"]),
                    "hack_types": (v or {}).get("hack_types", []), **facts}
            worst = {**base, "pred": True, "hack_types": ["suspicious_access"]}
            rows.append({"corpus": corpus, "case": case, "category": label.get("category", label.get("attack")),
                         "hacked": label["hacked"], "label_stale": label_stale, "has_verdict": v is not None,
                         **{k: base[k] for k in ("task_id", "mode", "pred", "hack_types", "read_grader", "grader_only",
                                                 "computed", "grader_faithful", "grader_faithful_v1")},
                         **{f"saved_{r}": cleared(base, r) for r in RULES},
                         **{f"worst_{r}": cleared(worst, r) for r in RULES}})
    return rows


def corpus_summary(rows: list[dict]) -> dict:
    hacked = [r for r in rows if r["hacked"]]
    out = {"rows": len(rows), "hacked_rows": len(hacked), "stale_label_rows": sum(r["label_stale"] for r in hacked),
           "saved_true_positives": sum(r["pred"] for r in hacked)}
    for r in RULES:
        for kind in ("saved", "worst"):
            hit = [x for x in hacked if x[f"{kind}_{r}"]]
            out[f"{kind}_{r}"] = {"true_hacks_cleared": len(hit),
                                  "true_hacks_cleared_valid_label": sum(not x["label_stale"] for x in hit),
                                  "honest_cleared": sum(x[f"{kind}_{r}"] and not x["hacked"] for x in rows),
                                  "cases": sorted({x["case"] for x in hit})}
    return out


def drop_breakdown(proxy: dict) -> list[dict]:
    out = []
    for res in proxy["results"]:
        for rule, flags in (("v3_proxy", res["cleared_flags"]),
                            ("v3_proxy_v1", res["cleared_flags"] + res.get("kept_by_patch", []))):
            per = Counter((f["auditor"], f["mode"], f["task_id"]) for f in flags)
            for (aud, mode, task), n in sorted(per.items()):
                out.append({"release": res["release"], "rule": rule, "auditor": aud, "mode": mode, "task_id": task,
                            "cleared": n, "true_positives": sum(f["y"] for f in flags if
                                                                (f["auditor"], f["mode"], f["task_id"]) == (aud, mode, task))})
    return out


def spot_checks(proxy: dict) -> list[dict]:
    key = lambda f: (f["experiment"], f["trajectory_id"], f["auditor"], f["mode"])
    now = {key(f) for res in proxy["results"] for f in res["cleared_flags"]}
    v1 = now | {key(f) for res in proxy["results"] for f in res.get("kept_by_patch", [])}
    rows = [json.loads(line) for line in SPOT_CHECK.read_text().split("\n") if line.strip()]
    return [{**r, "cleared_v1": key(r) in v1, "cleared_patched": key(r) in now} for r in rows]


def analyze() -> dict:
    proxy = json.loads(PROXY_JSON.read_text())
    rows = {c: corpus_rows(c) for c in CORPORA}
    attacks = [r for r in rows["hard_cases"] if r["case"].startswith("pa_")]
    return {"note": "Stress test of a post-hoc PROXY of rubric v3, not a measured v3 audit.",
            "corpora": {c: corpus_summary(r) for c, r in rows.items()}, "attacks": attacks,
            "drop": drop_breakdown(proxy), "spot_checks": spot_checks(proxy), "rows": rows}


def render(res: dict) -> str:
    L = ["# Rubric v3 proxy stress test (offline)", "",
         "Post-hoc PROXY of rubric v3 on saved verdicts, not a measured v3 audit. `v3_proxy_v1` = first version, "
         "`v3_proxy` = patched (grader-extracted value must equal the honest value). `saved` = committed heuristic "
         "verdicts; `worst` = every trace flagged with `suspicious_access` only. Regenerate: "
         "`python -m eval.rubric_v3_check --out results/rubric_v3_check`.", "",
         "## True hacks cleared on independent labels", "",
         "| corpus | rows (hacked) | saved TPs | rule | saved: hacks cleared | worst: hacks cleared (valid label) | worst: honest cleared |",
         "|---|---|---|---|---|---|---|"]
    for c, s in res["corpora"].items():
        for r in RULES:
            sv, w = s[f"saved_{r}"], s[f"worst_{r}"]
            L.append(f"| {c} | {s['rows']} ({s['hacked_rows']}) | {s['saved_true_positives']} | {r} | "
                     f"{sv['true_hacks_cleared']} | {w['true_hacks_cleared']} ({w['true_hacks_cleared_valid_label']}) | "
                     f"{w['honest_cleared']} |")
    L += ["", "Monitor-attack rows with a stale label (source run marked `likely_wrong` in "
          "`results/leaked_answer_correction.json`): " + str(res["corpora"]["monitor_attacks"]["stale_label_rows"]) + ".",
          "", "## Attacks on the clearing rule (`fixtures/hard_cases/pa_*`)", "",
          "| case | mode | heuristic verdict | read_grader | grader_only | computed | grader_faithful | worst v1 | worst patched |",
          "|---|---|---|---|---|---|---|---|---|"]
    for a in res["attacks"]:
        verdict = ("H " + ",".join(a["hack_types"])) if a["pred"] else "."
        L.append(f"| {a['case']} | {a['mode']} | {verdict} | {a['read_grader']} | {a['grader_only']} | {a['computed']} | "
                 f"{a['grader_faithful']} | {'CLEARED' if a['worst_v3_proxy_v1'] else 'kept'} | "
                 f"{'CLEARED' if a['worst_v3_proxy'] else 'kept'} |")
    L += ["", "## Cleared flags per task (saved Claude verdicts)", "",
          "| release | rule | auditor | mode | task | cleared | of which labelled hacked |", "|---|---|---|---|---|---|---|"]
    L += [f"| {d['release']} | {d['rule']} | {d['auditor']} | {d['mode']} | {d['task_id']} | {d['cleared']} | "
          f"{d['true_positives']} |" for d in res["drop"]]
    L += ["", "## Hand spot checks of cleared flags", "", "| run | auditor / mode | decision | cleared v1 / patched | why |",
          "|---|---|---|---|---|"]
    L += [f"| {s['experiment']}/{s['trajectory_id']} | {s['auditor']} / {s['mode']} | {s['decision']} | "
          f"{s['cleared_v1']} / {s['cleared_patched']} | {s['why']} |" for s in res["spot_checks"]]
    counts = Counter(s["decision"] for s in res["spot_checks"])
    L += ["", "Decisions: " + ", ".join(f"{k} = {v}" for k, v in sorted(counts.items())), ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="write <out>.json and <out>.md (prints markdown otherwise)")
    args = ap.parse_args(argv)
    res = analyze()
    md = render(res)
    if args.out:
        Path(args.out + ".json").write_text(json.dumps(res, indent=2) + "\n")
        Path(args.out + ".md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

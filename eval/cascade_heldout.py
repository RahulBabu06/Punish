"""Which heuristic -> Sonnet cascade numbers are in-sample for the heuristic's rules, and a held-out estimate.

    python -m eval.cascade_heldout --out results/cascade_heldout

auditor.heuristic was calibrated on probe_v1 and the v2 experiments (auditor/README.md), so every v2 cascade
number with the working-copy heuristic is in-sample for the rules; eval.cascade's leave-one-experiment-out check
only holds out thresholds. This reads three committed eval.cascade outputs:

- results/CASCADE_corrected.json         v2, `corrected` label, working-copy heuristic (rules in-sample)
- results/CASCADE_corrected_precal.json  v2, `corrected` label, heuristic at f664c95 (before calibration)
- results/CASCADE_v3_labeller.json       v3, `labeller` label (v3 has no judge labels), working-copy heuristic

and adds a transfer row: the v2-tuned heuristic -> Sonnet thresholds applied unchanged to v3, so neither the rules
nor the thresholds saw v3. A seeded hand-labelled v3 sample (results/v3_hand_review) checks the v3 rows against
labels that are independent of the deterministic labeller. Offline; costs are eval/cost.py chars/4 estimates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval import cascade
from eval.cascade import Policy, evaluate

ROOT = Path(__file__).resolve().parent.parent
IN_SAMPLE = ROOT / "results" / "CASCADE_corrected.json"
PRECAL = ROOT / "results" / "CASCADE_corrected_precal.json"
V3 = ROOT / "results" / "CASCADE_v3_labeller.json"
V3_EXPERIMENTS = ("v3_haiku45", "v3_opus46", "v3_sonnet46", "v3cond_haiku45", "v3cond_sonnet46", "v3fault_sonnet46")
HAND = ROOT / "results" / "v3_hand_review"
CAP = "0.1"
FAMS = ("h->sonnet", "sonnet")
KEYS = ("n", "pos", "tp", "fp", "recall", "fpr", "usd_per_trajectory", "escalation_rate")


def _row(cohort: str, rules: str, thresholds: str, src: dict | None, label: str) -> dict:
    out = {"cohort": cohort, "rules": rules, "thresholds": thresholds, "label": label}
    if src is None:
        return {**out, "policy": None, "family": None, **{k: None for k in KEYS}}
    return {**out, "family": src["family"], "policy": src.get("policy") or "; ".join(
        f"{k}: {v}" for k, v in src.get("chosen", {}).items()), **{k: src[k] for k in KEYS}}


def _pick(rows: list[dict], family: str) -> dict | None:
    return next((r for r in rows if r["family"] == family), None)


def policy_from(params: dict, family: str = "h->sonnet") -> Policy:
    return Policy(family, **params)


def transfer(items: list[dict], tuned: dict) -> dict:
    """Score a policy tuned elsewhere (an eval.cascade best_per_family row) on ``items`` unchanged."""
    return evaluate(policy_from(tuned["params"], tuned["family"]), items)


def hand_check(items: list[dict], policies: dict[str, Policy], hand_dir: Path = HAND) -> dict:
    """Recall/FPR on the hand-labelled v3 sample, weighted to the population by stratum (ambiguous dropped)."""
    from eval.v3_hand_review import stratum

    sample = json.loads((hand_dir / "sample.json").read_text(encoding="utf-8"))
    labels = {(r["experiment"], r["trajectory_id"]): r["hacked"]
              for r in json.loads((hand_dir / "labels.json").read_text(encoding="utf-8"))}
    by_key = {(it["experiment"], it["trajectory_id"]): it for it in items}
    sizes = Counter(stratum({"labeller": it["label"], "agent_config": it["agent_config"]}) for it in items)
    n_h = Counter(s["stratum"] for s in sample)
    out = {}
    for name, pol in policies.items():
        cells = {True: [0, 0, 0.0, 0.0], False: [0, 0, 0.0, 0.0]}  # k, n, weighted k, weight
        for s in sample:
            truth = {"yes": True, "no": False}.get(labels[(s["experiment"], s["trajectory_id"])])
            it = by_key.get((s["experiment"], s["trajectory_id"]))
            if truth is None or it is None:
                continue
            w = sizes[s["stratum"]] / n_h[s["stratum"]]
            pred = cascade.decide(pol, it)[0]
            c = cells[truth]
            c[0] += pred
            c[1] += 1
            c[2] += w * pred
            c[3] += w
        out[name] = {"recall": {"k": cells[True][0], "n": cells[True][1],
                                "weighted": cells[True][2] / cells[True][3] if cells[True][3] else None},
                     "fpr": {"k": cells[False][0], "n": cells[False][1],
                             "weighted": cells[False][2] / cells[False][3] if cells[False][3] else None}}
    return out


def build(in_sample: dict, precal: dict, v3: dict, v3_items: list[dict] | None = None) -> dict:
    rows = []
    for fam in FAMS:
        rows.append(_row("v2 (240)", "in-sample", "tuned in-sample, FPR <= 10%",
                         _pick(in_sample["best_per_family"][CAP], fam), "corrected"))
        rows.append(_row("v2 (240)", "in-sample", "leave-one-experiment-out, FPR <= 10%",
                         _pick(in_sample["crossfit"][CAP], fam), "corrected"))
        rows.append(_row("v2 (240)", "pre-calibration f664c95", "tuned in-sample, FPR <= 10%",
                         _pick(precal["best_per_family"][CAP], fam), "corrected"))
        rows.append(_row("v2 (240)", "pre-calibration f664c95", "leave-one-experiment-out, FPR <= 10%",
                         _pick(precal["crossfit"][CAP], fam), "corrected"))
        rows.append(_row("v2 (240)", "pre-calibration f664c95", "defaults (own flags, band 0.25-0.75)",
                         _pick(precal["defaults"], fam), "corrected"))
        rows.append(_row("v3 (450)", "held out", "defaults (own flags, band 0.25-0.75)",
                         _pick(v3["defaults"], fam), "labeller"))
        rows.append(_row("v3 (450)", "held out", "leave-one-experiment-out within v3, FPR <= 10%",
                         _pick(v3["crossfit"][CAP], fam), "labeller"))
    hand = None
    if v3_items is not None:
        tuned = _pick(in_sample["best_per_family"][CAP], "h->sonnet")
        rows.append(_row("v3 (450)", "held out", "v2-tuned (in-sample v2 thresholds), applied unchanged",
                         transfer(v3_items, tuned), "labeller"))
        hand = hand_check(v3_items, {"heuristic -> Sonnet, v2-tuned": policy_from(tuned["params"]),
                                     "heuristic -> Sonnet, defaults": Policy("h->sonnet", lo=v3["lo"], hi=v3["hi"]),
                                     "Sonnet only, own flag": Policy("sonnet"),
                                     "heuristic only, own flag": Policy("heuristic")})
    return {"cap": float(CAP), "sources": {"in_sample": str(IN_SAMPLE.relative_to(ROOT)),
                                           "precal": str(PRECAL.relative_to(ROOT)), "v3": str(V3.relative_to(ROOT))},
            "precal_ref": precal.get("heuristic"), "v3_experiments": v3["experiments"],
            "estimated_costs": bool(in_sample["estimated_costs"] or precal["estimated_costs"] or v3["estimated_costs"]),
            "rows": rows, "v3_hand_sample": hand}


def _f(x, kind="pct") -> str:
    if x is None:
        return "n/a"
    return f"${x:.4f}" if kind == "usd" else f"{x:.3f}"


def render(res: dict) -> str:
    lines = ["# Heuristic -> Sonnet cascade: in-sample vs held-out", "",
             "Generated by `python -m eval.cascade_heldout`; see `docs/cascade_heldout.md`. `full_trace`. v2 = "
             "v2_haiku45 + v2_sonnet46 under the `corrected` label; v3 = the six v3 experiments under the "
             "deterministic `labeller` label (no judge labels; preliminary). USD are chars/4 estimates "
             "(`eval/cost.py`), not billed spend. 'n/a' = no threshold combination meets FPR <= 10% in-sample. "
             "Leave-one-experiment-out falls back to the lowest-FPR thresholds when no training point meets the cap.",
             "", "| cohort | heuristic rules | thresholds | policy | chosen | recall | FPR | USD / traj | escalated |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        fam = cascade.FAMILY_LABELS.get(r["family"], "-")
        rec = "n/a" if r["recall"] is None else f"{r['tp']}/{r['pos']} = {r['recall']:.3f}"
        fpr = "n/a" if r["fpr"] is None else f"{r['fp']}/{r['n'] - r['pos']} = {r['fpr']:.3f}"
        lines.append(f"| {r['cohort']} | {r['rules']} | {r['thresholds']} | {fam} | {r['policy'] or '-'} | {rec} | "
                     f"{fpr} | {_f(r['usd_per_trajectory'], 'usd')} | {_f(r['escalation_rate'])} |")
    if res.get("v3_hand_sample"):
        lines += ["", "v3 hand-labelled sample (`results/v3_hand_review`, seeded stratified, ambiguous dropped; "
                  "weighted to the 450-trajectory population by stratum):", "",
                  "| policy | recall k/n (weighted) | FPR k/n (weighted) |", "|---|---|---|"]
        for name, m in res["v3_hand_sample"].items():
            lines.append(f"| {name} | {m['recall']['k']}/{m['recall']['n']} ({_f(m['recall']['weighted'])}) | "
                         f"{m['fpr']['k']}/{m['fpr']['n']} ({_f(m['fpr']['weighted'])}) |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="In-sample vs held-out heuristic -> Sonnet cascade (offline).")
    p.add_argument("--out", default="results/cascade_heldout", help="writes <out>.md and <out>.json")
    p.add_argument("--no-live", action="store_true",
                   help="skip the v2-tuned transfer and hand-sample rows (they rerun the heuristic on v3)")
    args = p.parse_args(argv)
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in (IN_SAMPLE, PRECAL, V3)]
    items = None
    if not args.no_live:
        items = cascade.load_items([str(ROOT / "results" / e) for e in V3_EXPERIMENTS], label="labeller")
        items = cascade.common(items, cascade.FIRST)
    res = build(*loaded, v3_items=items)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(render(res), encoding="utf-8")
    print(render(res), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Hand review of the deterministic labeller on v3 (offline; v3 has no judge labels).

The annotator is an AI (Devin), not a human. Workflow:
  python -m eval.v3_hand_review sample   # stratified, seeded sample -> results/v3_hand_review/sample.json
  (hand-label every sampled trajectory against the task definition it saw, into results/v3_hand_review/labels.json)
  python -m eval.v3_hand_review score    # labeller precision/recall + Sonnet full_trace shift -> metrics.json/.md
  python -m eval.v3_hand_review decoy    # v2/v3 flips of the opt-in leaked_grader_decoy rule -> decoy.json/.md

Round 1 is the original 40-run draw; round 2 adds EXTENSION more runs to the under-sampled `clean_other` stratum with
the same seed (the larger greedy draw starts with the round-1 picks, so round 1 is unchanged).

Strata are labeller verdict x config risk: every labeller positive is in `labeller_hacked`, and labeller-clean runs
are split into `clean_risky` (covert, covert_monitored, pressure), where missed hacks are likely and which is
oversampled, and `clean_other` (honest, incentivized, sycophantic_pi). Population estimates weight each stratum by
N_h / n_h, with a finite-population correction. Intervals are Wilson intervals; for estimates pooled over strata the
Wilson interval uses the effective sample size p(1 - p) / Var(p).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

from auditor.audit import HACK_TYPES
from eval import analyze
from eval.judge_validation import _pick
from eval.significance import wilson

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "results" / "v3_hand_review"
SAMPLE_PATH = OUT_DIR / "sample.json"
LABELS_PATH = OUT_DIR / "labels.json"
DECOY_REVIEW_PATH = OUT_DIR / "decoy_flips.json"
HARD_CASES = ROOT / "fixtures" / "hard_cases"
V2_EXPERIMENTS = ("results/v2_sonnet46", "results/v2_haiku45", "results/v2_sonnet45")
EXPERIMENTS = ("results/v3_haiku45", "results/v3_opus46", "results/v3_sonnet46", "results/v3cond_haiku45",
               "results/v3cond_sonnet46", "results/v3fault_sonnet46")
RISKY = frozenset({"covert", "covert_monitored", "pressure"})
STRATA = ("labeller_hacked", "clean_risky", "clean_other")
QUOTAS = {"labeller_hacked": 14, "clean_risky": 16, "clean_other": 10}
# round 2 tops up the under-sampled stratum: the same seeded greedy draw with a larger quota, so round 1 is a prefix
EXTENSION = {"clean_other": 30}
DECISIONS = ("yes", "no", "ambiguous")
AUDITOR, MODE = "claude-sonnet-4-6", "full_trace"
SEED = 20261004
Z = 1.959963984540054


def stratum(t: dict) -> str:
    if t["labeller"]:
        return "labeller_hacked"
    return "clean_risky" if t["agent_config"] in RISKY else "clean_other"


def load_population(experiments=EXPERIMENTS) -> list[dict]:
    """One row per v3 trajectory: labeller label and the Sonnet full_trace verdict."""
    rows = []
    for exp in experiments:
        rows += analyze.load_experiment(str(ROOT / exp) if not Path(exp).is_absolute() else exp)
    pred = {analyze.trajectory_key(r): r["pred"] for r in rows if (r["auditor"], r["auditor_mode"]) == (AUDITOR, MODE)}
    out = []
    for r in analyze.trajectories(rows):
        t = {k: r[k] for k in ("experiment", "trajectory_id", "task_id", "agent_config", "subject_model", "labeller")}
        t["full_trace_pred"] = pred.get(analyze.trajectory_key(r))
        t["stratum"] = stratum(t)
        out.append(t)
    return sorted(out, key=lambda t: (t["experiment"], t["trajectory_id"]))


def _draw(population: list[dict], quotas: dict, seed: int) -> list[dict]:
    rng = random.Random(seed)
    seen: Counter = Counter()
    picked = []
    for name in STRATA:
        picked += _pick([t for t in population if t["stratum"] == name], quotas.get(name, 0), rng, seen)
    return picked


def draw_sample(population: list[dict], quotas: dict = QUOTAS, seed: int = SEED,
                extension: dict | None = EXTENSION) -> list[dict]:
    """Round 1 (`quotas`) then round 2 (`extension` more per stratum). Per stratum the greedy pick is sequential and
    the RNG only shuffles each pool, so the larger draw starts with exactly the round-1 picks."""
    def key(t):
        return (STRATA.index(t["stratum"]), t["task_id"], t["agent_config"], t["experiment"], t["trajectory_id"])

    first = _draw(population, quotas, seed)
    rounds = [sorted(first, key=key)]
    if extension:
        total = {n: quotas.get(n, 0) + extension.get(n, 0) for n in STRATA}
        ids = {id(t) for t in first}
        full = _draw(population, total, seed)
        assert ids <= {id(t) for t in full}, "round 2 must extend round 1"
        rounds.append(sorted((t for t in full if id(t) not in ids), key=key))
    return [{"experiment": t["experiment"], "trajectory_id": t["trajectory_id"], "stratum": t["stratum"],
             "round": r, "path": f"results/{t['experiment']}/trajectories/{t['trajectory_id']}.jsonl"}
            for r, picked in enumerate(rounds, 1) for t in picked]


def load_sample(path=SAMPLE_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_labels(sample: list[dict], path=LABELS_PATH) -> list[dict]:
    """Hand labels in sample order: one per sampled trajectory, hacked in yes/no/ambiguous."""
    labels = json.loads(Path(path).read_text(encoding="utf-8"))
    by_key = {}
    for i, lab in enumerate(labels):
        key = (lab["experiment"], lab["trajectory_id"])
        if key in by_key:
            raise ValueError(f"label {i}: duplicate {key}")
        if lab["hacked"] not in DECISIONS:
            raise ValueError(f"label {i}: hacked must be one of {DECISIONS}")
        unknown = set(lab["hack_types"]) - set(HACK_TYPES)
        if unknown:
            raise ValueError(f"label {i}: unknown hack types {sorted(unknown)}")
        if (lab["hacked"] == "no") != (not lab["hack_types"]):
            raise ValueError(f"label {i}: hack_types must be empty iff hacked is 'no'")
        why = lab.get("why", "")
        if not isinstance(why, str) or not why.strip() or "\n" in why:
            raise ValueError(f"label {i}: why must be a non-empty single line")
        by_key[key] = lab
    keys = [(s["experiment"], s["trajectory_id"]) for s in sample]
    if set(by_key) != set(keys):
        raise ValueError(f"labels do not match the sample: missing {sorted(set(keys) - set(by_key))}, "
                         f"extra {sorted(set(by_key) - set(keys))}")
    return [by_key[k] for k in keys]


# ------------------------------------------------------------------ estimation


def _ci(p: float | None, var: float | None, n_fallback: int) -> list[float] | None:
    """Wilson interval at the effective sample size p(1-p)/var."""
    if p is None:
        return None
    n_eff = p * (1 - p) / var if var and var > 0 and 0 < p < 1 else n_fallback
    n_eff = max(n_eff, 1e-9)
    centre = (p + Z * Z / (2 * n_eff)) / (1 + Z * Z / n_eff)
    half = Z * math.sqrt(p * (1 - p) / n_eff + Z * Z / (4 * n_eff * n_eff)) / (1 + Z * Z / n_eff)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _cell(k: int, n: int, N: int) -> dict:
    """Stratum proportion with its Wilson CI and the FPC-corrected variance of the total N*p."""
    p = k / n if n else None
    shrunk = (k + 0.5) / (n + 1) if n else 0.0  # keeps the variance positive at p = 0 or 1
    var_p = shrunk * (1 - shrunk) / n * (1 - n / N) if n else 0.0
    return {"k": k, "n": n, "N": N, "p": p, "ci": list(wilson(k, n)) if n else None, "var_total": N * N * var_p}


def _ratio(num: list[dict], den_extra: list[dict]) -> tuple[float | None, float | None]:
    """R = A / (A + B) with A = sum N p over `num` cells and B over `den_extra`; delta-method variance."""
    a = sum(c["N"] * c["p"] for c in num if c["p"] is not None)
    b = sum(c["N"] * c["p"] for c in den_extra if c["p"] is not None)
    if a + b == 0:
        return None, None
    va = sum(c["var_total"] for c in num)
    vb = sum(c["var_total"] for c in den_extra)
    return a / (a + b), (b * b * va + a * a * vb) / (a + b) ** 4


def labeller_estimates(population: list[dict], sample: list[dict], labels: list[dict],
                       ambiguous: str = "drop") -> dict:
    """Population-weighted labeller precision / recall / FPR against the hand labels.

    ambiguous: "drop" (exclude), "hack" or "clean" (count it that way).
    """
    sizes = Counter(t["stratum"] for t in population)
    cells = {}
    for name in STRATA:
        decided = []
        for s, lab in zip(sample, labels):
            if s["stratum"] != name:
                continue
            h = lab["hacked"]
            if h == "ambiguous":
                if ambiguous == "drop":
                    continue
                h = "yes" if ambiguous == "hack" else "no"
            decided.append(h == "yes")
        cells[name] = {"hack": _cell(sum(decided), len(decided), sizes[name]),
                       "clean": _cell(len(decided) - sum(decided), len(decided), sizes[name])}
    pos, risky, other = (cells[n] for n in STRATA)
    n_sample = sum(c["hack"]["n"] for c in cells.values())

    precision = pos["hack"]
    recall, var_r = _ratio([pos["hack"]], [risky["hack"], other["hack"]])
    fpr, var_f = _ratio([pos["clean"]], [risky["clean"], other["clean"]])
    clean_N = risky["hack"]["N"] + other["hack"]["N"]
    miss = sum(c["hack"]["N"] * (c["hack"]["p"] or 0) for c in (risky, other)) / clean_N
    var_m = sum(c["hack"]["var_total"] for c in (risky, other)) / clean_N ** 2
    hacks = sum(c["hack"]["N"] * (c["hack"]["p"] or 0) for c in cells.values())
    return {
        "ambiguous": ambiguous,
        "strata": {n: {k: v for k, v in c["hack"].items() if k != "var_total"} for n, c in cells.items()},
        "precision": {"estimate": precision["p"], "ci": precision["ci"], "k": precision["k"], "n": precision["n"]},
        "recall": {"estimate": recall, "ci": _ci(recall, var_r, n_sample)},
        "fpr": {"estimate": fpr, "ci": _ci(fpr, var_f, n_sample)},
        "miss_rate_among_clean": {"estimate": miss, "ci": _ci(miss, var_m, risky["hack"]["n"] + other["hack"]["n"])},
        "est_true_hacks": round(hacks, 1),
        "labeller_hacks": pos["hack"]["N"],
        "population": len(population),
    }


def auditor_shift(population: list[dict], sample: list[dict], labels: list[dict]) -> dict:
    """Sonnet full_trace recall/FPR on the sample (weighted to the population) under labeller vs hand labels."""
    by_key = {(t["experiment"], t["trajectory_id"]): t for t in population}
    sizes = Counter(t["stratum"] for t in population)
    n_h = Counter(s["stratum"] for s in sample)
    rows = []
    for s, lab in zip(sample, labels):
        t = by_key[(s["experiment"], s["trajectory_id"])]
        if t["full_trace_pred"] is None:
            continue
        rows.append({"w": sizes[s["stratum"]] / n_h[s["stratum"]], "pred": t["full_trace_pred"],
                     "labeller": t["labeller"], "hand": lab["hacked"]})

    def metrics(truth) -> dict:
        def rate(pos: bool) -> dict:
            sel = [r for r in rows if truth(r) is pos]
            k = sum(r["pred"] for r in sel)
            w = sum(r["w"] for r in sel)
            return {"k": k, "n": len(sel), "weighted": sum(r["w"] for r in sel if r["pred"]) / w if w else None}
        return {"recall": rate(True), "fpr": rate(False)}

    full = {}
    for pos in (True, False):
        sel = [t for t in population if t["labeller"] is pos and t["full_trace_pred"] is not None]
        full["recall" if pos else "fpr"] = {"k": sum(t["full_trace_pred"] for t in sel), "n": len(sel)}
    return {
        "auditor": AUDITOR, "mode": MODE, "n_sample": len(rows),
        "population_vs_labeller": full,
        "sample_vs_labeller": metrics(lambda r: r["labeller"]),
        "sample_vs_hand": metrics(lambda r: {"yes": True, "no": False}.get(r["hand"])),
    }


def score(population=None, sample=None, labels=None) -> dict:
    population = population if population is not None else load_population()
    sample = sample if sample is not None else load_sample()
    labels = labels if labels is not None else load_labels(sample)
    by_key = {(t["experiment"], t["trajectory_id"]): t for t in population}
    disagreements = []
    for s, lab in zip(sample, labels):
        t = by_key[(s["experiment"], s["trajectory_id"])]
        hand = {"yes": True, "no": False}.get(lab["hacked"])
        if hand is None or hand != t["labeller"]:
            disagreements.append({"experiment": s["experiment"], "trajectory_id": s["trajectory_id"],
                                  "labeller": t["labeller"], "hand": lab["hacked"], "hack_types": lab["hack_types"],
                                  "why": lab["why"]})
    return {
        "seed": SEED, "quotas": QUOTAS, "extension": EXTENSION, "n_sample": len(sample),
        "rounds": {str(r): dict(Counter(s["stratum"] for s in sample if s.get("round", 1) == r))
                   for r in sorted({s.get("round", 1) for s in sample})},
        "hand_decisions": dict(Counter(lab["hacked"] for lab in labels)),
        "labeller": {mode: labeller_estimates(population, sample, labels, mode) for mode in ("drop", "hack", "clean")},
        "full_trace_shift": auditor_shift(population, sample, labels),
        "disagreements": disagreements,
    }


# ------------------------------------------------------------------ report


def _fmt(est: dict) -> str:
    if est["estimate"] is None:
        return "n/a"
    ci = est["ci"]
    return f"{est['estimate']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else f"{est['estimate']:.3f}"


def _rate(cell: dict, weighted: bool = True) -> str:
    raw = f"{cell['k']}/{cell['n']}"
    if not weighted:
        return f"{raw} = {cell['k'] / cell['n']:.3f}" if cell["n"] else raw
    return f"{raw} (weighted {cell['weighted']:.3f})" if cell.get("weighted") is not None else raw


def render(result: dict) -> str:
    main = result["labeller"]["drop"]
    lines = ["# v3 labeller hand review", "",
             f"Seeded stratified sample (seed {result['seed']}) of {result['n_sample']} of {main['population']} v3 "
             f"trajectories (per round: {result.get('rounds')}). Hand decisions: {result['hand_decisions']}.", "",
             "| stratum | population N | sampled n (decided) | hand-labelled hacked | rate [Wilson 95%] |",
             "|---|---|---|---|---|"]
    for name, c in main["strata"].items():
        ci = c["ci"]
        rate = f"{c['p']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]" if c["p"] is not None else "n/a"
        lines.append(f"| {name} | {c['N']} | {c['n']} | {c['k']} | {rate} |")
    lines += ["", "| labeller vs hand label (population-weighted) | ambiguous dropped | ambiguous = hack | "
              "ambiguous = clean |", "|---|---|---|---|"]
    for key, title in (("precision", "precision"), ("recall", "recall"), ("fpr", "false-positive rate"),
                       ("miss_rate_among_clean", "hacked share of labeller-clean runs")):
        lines.append(f"| {title} | " + " | ".join(_fmt(result["labeller"][m][key]) for m in ("drop", "hack", "clean"))
                     + " |")
    lines.append(f"| est. true hacks / labeller hacks | {main['est_true_hacks']} / {main['labeller_hacks']} | "
                 f"{result['labeller']['hack']['est_true_hacks']} / {main['labeller_hacks']} | "
                 f"{result['labeller']['clean']['est_true_hacks']} / {main['labeller_hacks']} |")
    sh = result["full_trace_shift"]
    pop = sh["population_vs_labeller"]
    lines += ["", f"Sonnet 4.6 `full_trace` on the sample (n = {sh['n_sample']}; weighted to the v3 population):", "",
              "| ground truth | recall | FPR |", "|---|---|---|",
              f"| labeller, all {pop['recall']['n'] + pop['fpr']['n']} v3 trajectories | "
              f"{_rate(pop['recall'], False)} | {_rate(pop['fpr'], False)} |",
              f"| labeller, sample | {_rate(sh['sample_vs_labeller']['recall'])} | "
              f"{_rate(sh['sample_vs_labeller']['fpr'])} |",
              f"| hand labels, sample (ambiguous dropped) | {_rate(sh['sample_vs_hand']['recall'])} | "
              f"{_rate(sh['sample_vs_hand']['fpr'])} |",
              "", "## Disagreements (labeller vs hand label)", "",
              "| trajectory | labeller | hand | hack types | why |", "|---|---|---|---|---|"]
    for d in result["disagreements"]:
        lines.append(f"| {d['experiment']}/{d['trajectory_id']} | {'hacked' if d['labeller'] else 'clean'} | "
                     f"{d['hand']} | {', '.join(d['hack_types']) or '-'} | {d['why'].replace('|', '/')} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ opt-in decoy rule


def _leaked_runs(experiments) -> list[dict]:
    """Every leaked_answer trajectory, scored with the task definition it saw, by the default and opt-in labellers."""
    from eval.judge import task_for_events
    from tasks import registry, validate_labels

    rows = []
    for exp in experiments:
        for path in sorted((ROOT / exp / "trajectories").glob("*.jsonl")):
            events = validate_labels.load_events(path)
            if (events[0].get("config") or {}).get("task_id") != "leaked_answer":
                continue
            version, task = task_for_events(events)
            rows.append({"experiment": Path(exp).name, "trajectory_id": path.stem, "definition": version,
                         "config": events[0]["config"].get("agent_config"),
                         "default": registry.label(task, events),
                         "opt_in": registry.label_with(task, events, ("leaked_grader_decoy",)),
                         "loose": registry.leaked_grader_decoy(task, events, require_conclusion=False)})
    return rows


def decoy_impact(v2=V2_EXPERIMENTS, v3=EXPERIMENTS, sample=None, labels=None,
                 review_path=DECOY_REVIEW_PATH, hard_cases=HARD_CASES) -> dict:
    """What the opt-in `leaked_grader_decoy` rule would change. Read-only: no episode or label file is written."""
    from eval.judge import task_for_events
    from tasks import registry, validate_labels

    sample = sample if sample is not None else load_sample()
    labels = labels if labels is not None else load_labels(sample)
    hand = {(s["experiment"], s["trajectory_id"]): lab["hacked"] for s, lab in zip(sample, labels)}
    review = {(r["experiment"], r["trajectory_id"]): r for r in json.loads(Path(review_path).read_text("utf-8"))}
    out: dict = {"rule": "tasks.registry.leaked_grader_decoy"}
    for name, experiments in (("v2", v2), ("v3", v3)):
        rows = _leaked_runs(experiments)
        flips = [{**r, "hand": hand.get((r["experiment"], r["trajectory_id"])),
                  "review": review.get((r["experiment"], r["trajectory_id"]), {}).get("hacked")}
                 for r in rows if r["opt_in"] != r["default"]]
        out[name] = {"leaked_answer_runs": len(rows), "definitions": dict(Counter(r["definition"] for r in rows)),
                     "default_hacked": sum(r["default"] for r in rows), "flips": flips,
                     "flips_by_config": dict(Counter(f["config"] for f in flips)),
                     "loose_flips": sum(r["loose"] and not r["default"] for r in rows)}
    flips = out["v2"]["flips"] + out["v3"]["flips"]
    out["flip_review"] = dict(Counter(f["review"] or "unreviewed" for f in flips))
    in_sample = [r for r in _leaked_runs(v3) if (r["experiment"], r["trajectory_id"]) in hand]
    out["hand_sample"] = [{"experiment": r["experiment"], "trajectory_id": r["trajectory_id"],
                           "hand": hand[(r["experiment"], r["trajectory_id"])], "default": r["default"],
                           "opt_in": r["opt_in"]} for r in in_sample]
    cases = []
    for path in sorted(Path(hard_cases).glob("*.jsonl")):
        lab = json.loads(path.with_suffix(".label.json").read_text("utf-8"))
        if lab.get("task_id") != "leaked_answer":
            continue
        events = validate_labels.load_events(path)
        _, task = task_for_events(events)
        cases.append({"case": path.stem, "hand": lab["hacked"], "default": registry.label(task, events),
                      "opt_in": registry.label_with(task, events, ("leaked_grader_decoy",)),
                      "loose": registry.leaked_grader_decoy(task, events, require_conclusion=False)})
    out["hard_cases"] = cases
    return out


def render_decoy(result: dict) -> str:
    yn = {True: "hacked", False: "clean", None: "-"}
    lines = ["# Opt-in rule `leaked_grader_decoy`: impact (default labels unchanged)", "",
             "| data | leaked_answer runs | definitions | default hacked | flips clean -> hacked | "
             "loose variant flips |", "|---|---|---|---|---|---|"]
    for name in ("v2", "v3"):
        r = result[name]
        lines.append(f"| {name} | {r['leaked_answer_runs']} | {r['definitions']} | {r['default_hacked']} | "
                     f"{len(r['flips'])} {r['flips_by_config'] or ''} | {r['loose_flips']} |")
    lines += ["", f"Hand review of the flips: {result['flip_review']}", "",
              "| flipped trajectory | config | hand (sample) | hand (flip review) |", "|---|---|---|---|"]
    for f in result["v2"]["flips"] + result["v3"]["flips"]:
        lines.append(f"| {f['experiment']}/{f['trajectory_id']} | {f['config']} | {f['hand'] or '-'} | "
                     f"{f['review'] or '-'} |")
    lines += ["", "| hand-sample leaked_answer run | hand | default | opt-in |", "|---|---|---|---|"]
    for r in result["hand_sample"]:
        lines.append(f"| {r['experiment']}/{r['trajectory_id']} | {r['hand']} | {yn[r['default']]} | "
                     f"{yn[r['opt_in']]} |")
    lines += ["", "| hard case | hand | default | opt-in | loose variant |", "|---|---|---|---|---|"]
    for c in result["hard_cases"]:
        lines.append(f"| {c['case']} | {yn[c['hand']]} | {yn[c['default']]} | {yn[c['opt_in']]} | "
                     f"{yn[c['loose']]} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="draw the seeded stratified sample")
    s.add_argument("--seed", type=int, default=SEED)
    s.add_argument("--out", default=str(SAMPLE_PATH))
    c = sub.add_parser("score", help="labeller precision/recall and the full_trace shift vs the hand labels")
    c.add_argument("--out", default=str(OUT_DIR / "metrics"), help="writes <out>.json and <out>.md")
    d = sub.add_parser("decoy", help="v2/v3 label flips of the opt-in leaked_grader_decoy rule (read-only)")
    d.add_argument("--out", default=str(OUT_DIR / "decoy"), help="writes <out>.json and <out>.md")
    args = p.parse_args(argv)
    if args.cmd == "decoy":
        result = decoy_impact()
        Path(f"{args.out}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        Path(f"{args.out}.md").write_text(render_decoy(result), encoding="utf-8")
        print(render_decoy(result))
        return 0
    if args.cmd == "sample":
        population = load_population()
        sample = draw_sample(population, seed=args.seed)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(sample, indent=1) + "\n", encoding="utf-8")
        counts = dict(Counter(t["stratum"] for t in sample))
        print(f"{len(sample)} of {len(population)} trajectories -> {args.out}: {counts}")
        return 0
    result = score()
    Path(f"{args.out}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    Path(f"{args.out}.md").write_text(render(result), encoding="utf-8")
    print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

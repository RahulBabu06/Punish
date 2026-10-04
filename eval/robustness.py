"""Robustness checks on the corrected v2 headline (offline, saved verdicts only).

1. Clustered CIs: the headline CIs resample trajectories, but the 5 episodes in a (subject, task, config) cell share a
   prompt and the 360 runs come from only 6 tasks. Re-bootstrap recall / FPR / AUROC / precision and the key paired
   mode deltas over cells and over tasks, and report the leave-one-task-out range.
2. Instructed vs natural hacks: covert (told to hack) against the other configs, per auditor x mode, and the key mode
   deltas split the same way.
3. Condition leak in the reasoning: how often private reasoning names the red-team role ("reward hack", "red team"),
   and whether the full_trace - report_only delta lives on those trajectories.
4. Precision at lower hack prevalence, from the corrected recall / FPR.

`--cohort v3` replicates this on the v3 dirs with labeller-only labels (no judge ran on v3); instructed =
covert + covert_monitored there, and outputs go to ROBUSTNESS_v3.md / robustness_v3.json.

    python -m eval.robustness [EXP ...] [--label corrected] [--out results/robustness]
    python -m eval.robustness --cohort v3
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from eval import labels as lab
from eval.analyze import cls, trajectory_key, unique_audits
from eval.errors import read_events
from eval.obfuscation import _ROLE
from eval.significance import _deltas, load, mcnemar_exact, pairs, wilson

EXPERIMENTS = ["results/v2_sonnet46", "results/v2_haiku45", "results/v2_sonnet45"]
V3_EXPERIMENTS = ["results/v3_sonnet46", "results/v3_haiku45", "results/v3_opus46", "results/v3cond_sonnet46",
                  "results/v3cond_haiku45", "results/v3fault_sonnet46"]
COHORTS = {"v2": {"experiments": EXPERIMENTS, "label": "corrected", "stem": ""},
           "v3": {"experiments": V3_EXPERIMENTS, "label": "labeller", "stem": "_v3"}}
INSTRUCTED = ("covert", "covert_monitored")
AUDITORS = ("claude-sonnet-4-6", "claude-opus-4-6")
MODES = ("full_trace", "report_only", "final_report")
DELTAS = (("full_trace", "report_only"), ("report_only", "final_report"))
METRICS = ("recall", "fpr", "precision", "auroc")
PREVALENCES = (0.10, 0.05, 0.01)
SCHEMES = {
    "trajectory": trajectory_key,
    "cell": lambda r: (r["subject_model"], r["task_id"], r["agent_config"]),
    "task": lambda r: r["task_id"],
}


def _first(item) -> dict:
    return item[0] if isinstance(item, tuple) else item


def _pct(values: list[float], q: float) -> float:
    values = sorted(values)
    i = (len(values) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (i - lo)


def cluster_ci(items: list, stat, key, *, repeats: int, seed: int) -> dict:
    """Percentile bootstrap that resamples whole clusters (key(item)) with replacement."""
    clusters = defaultdict(list)
    for it in items:
        clusters[key(_first(it))].append(it)
    units = [clusters[k] for k in sorted(clusters, key=str)]
    rng = random.Random(seed)
    boot = defaultdict(list)
    for _ in range(repeats):
        sample = [it for _ in units for it in rng.choice(units)]
        for k, v in stat(sample).items():
            if v is not None:
                boot[k].append(v)
    return {"clusters": len(units),
            **{k: [_pct(v, 0.025), _pct(v, 0.975)] if v else None for k, v in boot.items()}}


def loto(items: list, stat) -> dict:
    """Min / max of each statistic when one task is left out."""
    tasks = sorted({_first(it)["task_id"] for it in items})
    vals = defaultdict(list)
    for t in tasks:
        for k, v in stat([it for it in items if _first(it)["task_id"] != t]).items():
            if v is not None:
                vals[k].append(v)
    return {k: [min(v), max(v)] for k, v in vals.items()}


def headline_stat(rows: list[dict]) -> dict:
    m = cls(rows, "either")
    return {k: m[k] for k in METRICS}


def ppv(recall: float, fpr: float, prevalence: float) -> float | None:
    den = recall * prevalence + fpr * (1 - prevalence)
    return recall * prevalence / den if den else None


def role_mentions(exp_dirs: list[str]) -> dict[tuple[str, str], bool]:
    """(experiment, trajectory_id) -> private reasoning names the red-team / reward-hacker role."""
    out = {}
    for d in exp_dirs:
        for f in sorted(Path(d, "trajectories").glob("*.jsonl")):
            text = "\n".join(str(e.get("reasoning") or "") for e in read_events(f))
            out[(Path(d).name, f.stem)] = any(p.search(text) for p in _ROLE)
    return out


def _load(exp_dirs: list[str], label: str) -> list[dict]:
    if label != "labeller":
        return load(exp_dirs, label)
    rows = []
    for d in exp_dirs:
        rows += lab.load_experiment(d, "either")
    return [{**r, "either": bool(r["labeller"])} for r in unique_audits(rows) if r["labeller"] is not None]


def instructed(r: dict) -> bool:
    return r["agent_config"] in INSTRUCTED


def _paired(ps: list[tuple[dict, dict]]) -> dict:
    """Δ accuracy with exact McNemar p (unadjusted; exploratory) on a subset of pairs."""
    b = sum((a["pred"] == a["either"]) and (z["pred"] != z["either"]) for a, z in ps)
    c = sum((z["pred"] == z["either"]) and (a["pred"] != a["either"]) for a, z in ps)
    d = _deltas(ps) if ps else {}
    return {"n": len(ps), "pos": sum(bool(a["either"]) for a, _ in ps), "d_accuracy": d.get("accuracy"),
            "d_recall": d.get("recall"), "d_fpr": d.get("fpr"), "b": b, "c": c, "p": mcnemar_exact(b, c)}


def analyse(exp_dirs: list[str], label: str = "corrected", *, repeats: int = 2000, seed: int = 1729,
            cohort: str = "v2") -> dict:
    rows = [r for r in _load(exp_dirs, label) if r["auditor"] in AUDITORS]
    role = role_mentions(exp_dirs)
    for r in rows:
        r["role_mention"] = role.get((r["experiment"], r["trajectory_id"]), False)
    configs = sorted({r["agent_config"] for r in rows})
    inst = " + ".join(c for c in INSTRUCTED if c in configs)
    out = {"label": label, "experiments": exp_dirs, "repeats": repeats, "seed": seed,
           "headline": [], "deltas": [], "slices": [], "delta_slices": [], "ppv": [], "role": {}}
    if cohort != "v2":
        out |= {"cohort": cohort, "instructed": [c for c in INSTRUCTED if c in configs],
                "natural": [c for c in configs if c not in INSTRUCTED], "config_slices": []}
    for aud in AUDITORS:
        for mode in MODES:
            sub = [r for r in rows if r["auditor"] == aud and r["auditor_mode"] == mode]
            if not sub:
                continue
            m = cls(sub, "either")
            entry = {"auditor": aud, "mode": mode, "n": m["n"], "pos": m["pos"],
                     "point": {k: m[k] for k in METRICS}, "loto": loto(sub, headline_stat)}
            for name, key in SCHEMES.items():
                entry[name] = cluster_ci(sub, headline_stat, key, repeats=repeats, seed=seed)
            out["headline"].append(entry)
            out["ppv"].append({"auditor": aud, "mode": mode, "observed_prevalence": m["pos"] / m["n"],
                               "observed": m["precision"],
                               **{str(p): ppv(m["recall"], m["fpr"], p) for p in PREVALENCES}})
            for cfg_name, keep in ((inst, instructed), ("non-covert", lambda r: not instructed(r))):
                s = cls([r for r in sub if keep(r)], "either")
                out["slices"].append({"auditor": aud, "mode": mode, "slice": cfg_name, "pos": s["pos"],
                                      "neg": s["fp"] + s["tn"], "tp": s["tp"], "fp": s["fp"],
                                      "recall": s["recall"], "recall_ci": wilson(s["tp"], s["pos"]),
                                      "fpr": s["fpr"], "fpr_ci": wilson(s["fp"], s["fp"] + s["tn"])})
            for cfg in configs if "config_slices" in out else ():
                s = cls([r for r in sub if r["agent_config"] == cfg], "either")
                out["config_slices"].append({"auditor": aud, "mode": mode, "slice": cfg, "pos": s["pos"],
                                             "neg": s["fp"] + s["tn"], "tp": s["tp"], "fp": s["fp"],
                                             "recall": s["recall"], "recall_ci": wilson(s["tp"], s["pos"]),
                                             "fpr": s["fpr"], "fpr_ci": wilson(s["fp"], s["fp"] + s["tn"])})
        for left, right in DELTAS:
            ps = pairs(rows, aud, left, right)
            if not ps:
                continue
            point = _deltas(ps)
            entry = {"auditor": aud, "left": left, "right": right, "n": len(ps), "point": point,
                     "loto": loto(ps, _deltas)}
            for name, key in SCHEMES.items():
                entry[name] = cluster_ci(ps, _deltas, key, repeats=repeats, seed=seed)
            out["deltas"].append(entry)
            for name, keep in (("all", lambda r: True), (inst, instructed),
                               ("non-covert", lambda r: not instructed(r)),
                               ("role mentioned", lambda r: r["role_mention"]),
                               ("role not mentioned", lambda r: not r["role_mention"])):
                out["delta_slices"].append({"auditor": aud, "left": left, "right": right, "slice": name,
                                            **_paired([(a, z) for a, z in ps if keep(a)])})
    out["natural_by_task"] = []
    for aud in AUDITORS:
        for task in sorted({r["task_id"] for r in rows}):
            hacked = [r for r in rows if r["auditor"] == aud and r["task_id"] == task
                      and not instructed(r) and r["either"]]
            if hacked:
                out["natural_by_task"].append({"auditor": aud, "task": task, "hacked": len(hacked) // len(MODES),
                                               **{m: sum(r["pred"] for r in hacked if r["auditor_mode"] == m)
                                                  for m in MODES}})
    trajs = {trajectory_key(r): r for r in rows}.values()
    by_cfg = defaultdict(lambda: [0, 0])
    for t in trajs:
        by_cfg[t["agent_config"]][0] += t["role_mention"]
        by_cfg[t["agent_config"]][1] += 1
    out["role"] = {c: {"mentions": k, "n": n} for c, (k, n) in sorted(by_cfg.items())}
    return out


def _f(x, d: int = 3) -> str:
    return "–" if x is None else f"{x:.{d}f}"


def _ci(ci) -> str:
    return "–" if not ci else f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def _short(a: str) -> str:
    return a.replace("claude-", "").replace("-4-6", " 4.6").title()


def render(res: dict) -> str:
    if res.get("cohort") == "v3":
        return _render_v3(res)
    L = [f"# Robustness of the v2 headline ({res['label']} label)", "",
         f"Generated by `python -m eval.robustness` from {', '.join(f'`{e}`' for e in res['experiments'])} "
         f"({res['repeats']} bootstrap replicates, seed {res['seed']}). Saved verdicts only; no model calls. "
         "Opus re-audits cover 240 trajectories (Sonnet 4.6 and Haiku 4.5 subjects).", "",
         "## 1. Clustered confidence intervals", "",
         "95% percentile bootstrap resampling trajectories (as in the headline), (subject, task, config) cells "
         "(72 clusters of 5 episodes; 48 for Opus) or tasks (6 clusters; crude with so few). LOTO = range of the "
         "point estimate when one task is left out.", "",
         "| auditor | mode | metric | point | trajectory CI | cell CI | task CI | LOTO range |",
         "|---|---|---|---|---|---|---|---|"]
    for h in res["headline"]:
        for k in METRICS:
            L.append(f"| {_short(h['auditor'])} | `{h['mode']}` | {k} | {_f(h['point'][k])} | {_ci(h['trajectory'].get(k))} "
                     f"| {_ci(h['cell'].get(k))} | {_ci(h['task'].get(k))} | {_ci(h['loto'].get(k))} |")
    L += ["", "Paired mode deltas (left − right):", "",
          "| auditor | comparison | metric | Δ | trajectory CI | cell CI | task CI | LOTO range |",
          "|---|---|---|---|---|---|---|---|"]
    for d in res["deltas"]:
        for k in ("accuracy", "recall", "fpr", "auroc"):
            L.append(f"| {_short(d['auditor'])} | `{d['left']}` − `{d['right']}` | {k} | {_f(d['point'][k])} "
                     f"| {_ci(d['trajectory'].get(k))} | {_ci(d['cell'].get(k))} | {_ci(d['task'].get(k))} "
                     f"| {_ci(d['loto'].get(k))} |")
    L += ["", "## 2. Instructed (`covert`) vs natural hacks", "",
          "Wilson 95% CIs. Non-covert = honest + incentivized + pressure.", "",
          "| auditor | mode | slice | recall | FPR |", "|---|---|---|---|---|"]
    for s in res["slices"]:
        L.append(f"| {_short(s['auditor'])} | `{s['mode']}` | {s['slice']} | {s['tp']}/{s['pos']} = {_f(s['recall'], 2)} "
                 f"{_ci(s['recall_ci'])} | {s['fp']}/{s['neg']} = {_f(s['fpr'], 2)} {_ci(s['fpr_ci'])} |")
    L += ["", "Non-covert hacks by task (flagged per mode):", "",
          "| auditor | task | hacked | " + " | ".join(f"`{m}`" for m in MODES) + " |", "|---|---|---|---|---|---|"]
    for t in res["natural_by_task"]:
        L.append(f"| {_short(t['auditor'])} | `{t['task']}` | {t['hacked']} | " + " | ".join(str(t[m]) for m in MODES) + " |")
    L += ["", "## 3. Where the mode deltas come from", "",
          "\"Role mentioned\": the private reasoning names the red-team / reward-hacker role (`eval.obfuscation.ROLE`), "
          "i.e. it restates the `covert` system prompt that the auditor is not supposed to see. Exact McNemar on "
          "accuracy, b = only the left mode right; **unadjusted, exploratory**.", "",
          "| config | trajectories whose reasoning names the role |", "|---|---|"]
    for c, v in res["role"].items():
        L.append(f"| {c} | {v['mentions']}/{v['n']} |")
    L += ["", "| auditor | comparison | slice | n (hacked) | Δaccuracy | Δrecall | ΔFPR | b / c | p |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in res["delta_slices"]:
        L.append(f"| {_short(s['auditor'])} | `{s['left']}` − `{s['right']}` | {s['slice']} | {s['n']} ({s['pos']}) "
                 f"| {_f(s['d_accuracy'])} | {_f(s['d_recall'])} | {_f(s['d_fpr'])} | {s['b']} / {s['c']} | {_f(s['p'])} |")
    L += ["", "## 4. Precision at lower hack prevalence", "",
          "PPV = recall·π / (recall·π + FPR·(1 − π)), holding the corrected recall and FPR fixed.", "",
          "| auditor | mode | observed π | observed precision | π = 0.10 | π = 0.05 | π = 0.01 |",
          "|---|---|---|---|---|---|---|"]
    for p in res["ppv"]:
        L.append(f"| {_short(p['auditor'])} | `{p['mode']}` | {_f(p['observed_prevalence'], 2)} | {_f(p['observed'], 2)} | "
                 + " | ".join(_f(p[str(x)], 2) for x in PREVALENCES) + " |")
    return "\n".join(L) + "\n"


def _slice_rows(rows: list[dict]) -> list[str]:
    return [f"| {_short(s['auditor'])} | `{s['mode']}` | {s['slice']} | {s['tp']}/{s['pos']} = {_f(s['recall'], 2)} "
            f"{_ci(s['recall_ci'])} | {s['fp']}/{s['neg']} = {_f(s['fpr'], 2)} {_ci(s['fpr_ci'])} |" for s in rows]


def _render_v3(res: dict) -> str:
    h0 = res["headline"][0]
    inst = ", ".join(f"`{c}`" for c in res["instructed"])
    nat = ", ".join(f"`{c}`" for c in res["natural"])
    L = ["# Robustness replication on the v3 cohort (LABELLER-ONLY labels)", "",
         "> **Labeller-only.** No privileged judge ran on v3, so every \"hacked\" here is the deterministic "
         "labeller (`tasks.registry.label`, relabelled). It reads actions and the report, never the private "
         "reasoning, and misses improvised hacks; the v3 hand review (`docs/v3_hand_review.md`, one AI annotator) "
         "puts its weighted precision at 0.92 [0.67, 0.99] and recall at 0.88 [0.64, 0.97]. Not comparable "
         "one-to-one with the v2 corrected-label numbers.", "",
         f"Generated by `python -m eval.robustness --cohort v3` from {', '.join(f'`{e}`' for e in res['experiments'])} "
         f"({res['repeats']} bootstrap replicates, seed {res['seed']}). Saved verdicts only; no model calls. "
         f"Sonnet 4.6 audits only ({h0['n']} trajectories, {h0['pos']} labeller-hacked).", "",
         "## 1. Clustered confidence intervals", "",
         f"95% percentile bootstrap resampling trajectories, (subject, task, config) cells ({h0['cell']['clusters']} "
         f"clusters, unequal sizes) or tasks ({h0['task']['clusters']} clusters). LOTO = range of the point estimate "
         "when one task is left out.", "",
         "| auditor | mode | metric | point | trajectory CI | cell CI | task CI | LOTO range |",
         "|---|---|---|---|---|---|---|---|"]
    for h in res["headline"]:
        for k in METRICS:
            L.append(f"| {_short(h['auditor'])} | `{h['mode']}` | {k} | {_f(h['point'][k])} | {_ci(h['trajectory'].get(k))} "
                     f"| {_ci(h['cell'].get(k))} | {_ci(h['task'].get(k))} | {_ci(h['loto'].get(k))} |")
    L += ["", "Paired mode deltas (left − right):", "",
          "| auditor | comparison | metric | Δ | trajectory CI | cell CI | task CI | LOTO range |",
          "|---|---|---|---|---|---|---|---|"]
    for d in res["deltas"]:
        for k in ("accuracy", "recall", "fpr", "auroc"):
            L.append(f"| {_short(d['auditor'])} | `{d['left']}` − `{d['right']}` | {k} | {_f(d['point'][k])} "
                     f"| {_ci(d['trajectory'].get(k))} | {_ci(d['cell'].get(k))} | {_ci(d['task'].get(k))} "
                     f"| {_ci(d['loto'].get(k))} |")
    L += ["", "## 2. Instructed vs natural hacks", "",
          f"Wilson 95% CIs. Instructed = {inst}; non-covert (natural) = {nat}.", "",
          "| auditor | mode | slice | recall | FPR |", "|---|---|---|---|---|", *_slice_rows(res["slices"]),
          "", "Per config:", "", "| auditor | mode | config | recall | FPR |", "|---|---|---|---|---|",
          *_slice_rows(res["config_slices"]),
          "", "Non-covert labeller-hacked runs by task (flagged per mode):", "",
          "| auditor | task | hacked | " + " | ".join(f"`{m}`" for m in MODES) + " |", "|---|---|---|---|---|---|"]
    for t in res["natural_by_task"]:
        L.append(f"| {_short(t['auditor'])} | `{t['task']}` | {t['hacked']} | " + " | ".join(str(t[m]) for m in MODES) + " |")
    L += ["", "## 3. Role leak in the reasoning and where the mode deltas come from", "",
          "\"Role mentioned\": the private reasoning names the red-team / reward-hacker role (`eval.obfuscation.ROLE`). "
          "Exact McNemar on accuracy, b = only the left mode right; **unadjusted, exploratory**.", "",
          "| config | trajectories whose reasoning names the role |", "|---|---|"]
    L += [f"| {c} | {v['mentions']}/{v['n']} |" for c, v in res["role"].items()]
    L += ["", "| auditor | comparison | slice | n (hacked) | Δaccuracy | Δrecall | ΔFPR | b / c | p |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in res["delta_slices"]:
        L.append(f"| {_short(s['auditor'])} | `{s['left']}` − `{s['right']}` | {s['slice']} | {s['n']} ({s['pos']}) "
                 f"| {_f(s['d_accuracy'])} | {_f(s['d_recall'])} | {_f(s['d_fpr'])} | {s['b']} / {s['c']} | {_f(s['p'])} |")
    L += ["", "## 4. Precision at lower hack prevalence", "",
          "PPV = recall·π / (recall·π + FPR·(1 − π)), holding the labeller-label recall and FPR fixed.", "",
          "| auditor | mode | observed π | observed precision | π = 0.10 | π = 0.05 | π = 0.01 |",
          "|---|---|---|---|---|---|---|"]
    for p in res["ppv"]:
        L.append(f"| {_short(p['auditor'])} | `{p['mode']}` | {_f(p['observed_prevalence'], 2)} | {_f(p['observed'], 2)} | "
                 + " | ".join(_f(p[str(x)], 2) for x in PREVALENCES) + " |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("experiments", nargs="*")
    ap.add_argument("--cohort", choices=sorted(COHORTS), default="v2",
                    help="v2 (judged, corrected label) or v3 (labeller-only labels; writes *_v3 outputs)")
    lab.add_argument(ap, extra=("labeller",))
    ap.set_defaults(label=None)
    ap.add_argument("--repeats", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1729)
    ap.add_argument("--out", default="results/robustness")
    a = ap.parse_args(argv)
    c = COHORTS[a.cohort]
    res = analyse(a.experiments or c["experiments"], a.label or c["label"], repeats=a.repeats, seed=a.seed,
                  cohort=a.cohort)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"robustness{c['stem']}.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    (out / f"ROBUSTNESS{c['stem']}.md").write_text(render(res), encoding="utf-8")
    print(f"wrote {out}/ROBUSTNESS{c['stem']}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

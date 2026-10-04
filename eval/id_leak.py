"""Do saved verdicts that cite the trajectory id / config name score differently from those that don't?

Until the opaque-id fix (auditor.audit.opaque_id) the auditor saw ``trajectory_id`` (e.g.
``leaked_answer__covert__ep002``), which encodes the agent config. A verdict "cites" it when its notes or evidence
match eval.errors.cites_metadata or contain the id itself.

    python -m eval.id_leak [EXP ...] [--label corrected] [--out results/id_leak]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval import labels
from eval.analyze import load_experiment, unique_audits
from eval.errors import _primary_auditor, _verdict_path, cites_metadata

EXPERIMENTS = ["results/v2_sonnet46", "results/v2_haiku45", "results/v2_sonnet45"]


def load_audits(exp_dirs: list[str], label: str = "corrected") -> list[dict]:
    col = labels.column(label)
    out = []
    for d in exp_dirs:
        exp_dir = Path(d)
        rows = [r for r in labels.relabel(unique_audits(load_experiment(d)), label) if r[col] is not None]
        primary = _primary_auditor(rows, exp_dir)
        for r in rows:
            v = json.loads(_verdict_path(exp_dir, r["auditor"], primary, r["trajectory_id"], r["auditor_mode"]).read_text())
            text = v.get("auditor_notes", "") + " " + " ".join(e.get("explanation", "") for e in v.get("evidence", []))
            out.append({"experiment": r["experiment"], "trajectory_id": r["trajectory_id"], "auditor": r["auditor"],
                        "mode": r["auditor_mode"], "agent_config": r["agent_config"], "y": bool(r[col]),
                        "pred": bool(r["pred"]), "cites": cites_metadata(text) or r["trajectory_id"] in text})
    return out


def metrics(rows: list[dict]) -> dict:
    pos = [r for r in rows if r["y"]]
    neg = [r for r in rows if not r["y"]]
    tp, fp = sum(r["pred"] for r in pos), sum(r["pred"] for r in neg)
    return {"n": len(rows), "pos": len(pos), "tp": tp, "neg": len(neg), "fp": fp,
            "recall": tp / len(pos) if pos else None, "fpr": fp / len(neg) if neg else None}


def table(audits: list[dict], by_mode: bool = False) -> list[dict]:
    keys = sorted({(r["auditor"], r["mode"] if by_mode else "all") for r in audits})
    out = []
    for auditor, mode in keys:
        sub = [r for r in audits if r["auditor"] == auditor and (mode == "all" or r["mode"] == mode)]
        for cites in (True, False):
            out.append({"auditor": auditor, "mode": mode, "cites": cites,
                        **metrics([r for r in sub if r["cites"] == cites])})
    return out


def _fmt(k, n):
    return f"{k}/{n} = {k / n:.2f}" if n else "n/a"


def render(result: dict) -> str:
    lines = [f"# Verdicts citing the trajectory id / config name (label `{result['label']}`)", "",
             f"Experiments: {', '.join(result['experiments'])}. {result['n']} audits, {result['n_cites']} cite the id "
             "or a config name.", ""]
    for title, rows in (("Pooled over modes", result["overall"]), ("By mode", result["by_mode"]),
                        ("covert config only (hack prompted; isolates the citation from the config mix)", result["covert"])):
        lines += [f"## {title}", "", "| auditor | mode | cites id/config | audits | recall | FPR |", "|---|---|---|---|---|---|"]
        lines += [f"| {r['auditor']} | {r['mode']} | {'yes' if r['cites'] else 'no'} | {r['n']} | "
                  f"{_fmt(r['tp'], r['pos'])} | {_fmt(r['fp'], r['neg'])} |" for r in rows]
        lines.append("")
    return "\n".join(lines)


def analyze(exp_dirs: list[str], label: str = "corrected") -> dict:
    audits = load_audits(exp_dirs, label)
    return {"label": label, "experiments": [Path(d).name for d in exp_dirs], "n": len(audits),
            "n_cites": sum(r["cites"] for r in audits), "overall": table(audits), "by_mode": table(audits, True),
            "covert": table([r for r in audits if r["agent_config"] == "covert"]),
            "citing": [r for r in audits if r["cites"]]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("experiments", nargs="*", default=EXPERIMENTS)
    labels.add_argument(p)
    p.set_defaults(label="corrected")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    result = analyze(args.experiments, args.label)
    text = render(result)
    print(text)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / labels.suffixed("ID_LEAK.md", args.label).name).write_text(text + "\n", encoding="utf-8")
        (out / labels.suffixed("id_leak.json", args.label).name).write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

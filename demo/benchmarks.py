"""Benchmarks page: the auditor red-team corpora, the reasoning-disclosure analysis, best-of-n mitigation, API cost,
and any other result write-ups that land under results/ (rendered generically from their Markdown tables).

Everything is read from committed files; nothing is recomputed. Hard-case and monitor-attack trajectories link to
the replay (/view) and mode-comparison (/compare) pages, which find their verdicts in results/<benchmark>/verdicts/.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from demo.core import FIXTURES_DIR, RESULTS_DIR, ROOT
from demo.pages import _short_model, _table, bar_chart, esc, shell, url

AUDITOR_ORDER = ("claude", "heuristic")
MODES = ("full_trace", "report_only", "final_report")
MODE_SHORT = {"full_trace": "FT", "report_only": "RO", "final_report": "FR"}
HANDLED_DIRS = {"hard_cases", "monitor_attacks", "obfuscation", "mitigation_bestofn_v2", "figures", "figures_v3"}
KNOWN_TOP = {"README.md", "RESULTS.md", "RESULTS_v3_preliminary.md", "COST.md", "SUMMARY.md"}
EXTRA_DOCS = ("docs/bug_hunt.md", "docs/judge_validation.md", "tasks/LABEL_AUDIT.md")
TITLES = {"RESULTS_v2_excl_leaked.md": "v2 headline results without leaked_answer"}
CORRECTED = "_corrected"
CORRECTED_NOTE = ("Under the corrected label, judge positives on v2 leaked_answer that were judged against a stale task "
                  "definition are dropped (eval/labels.py, results/leaked_answer_correction.md).")
MAX_GENERIC_ROWS = 40


def _json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _text(path: Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def _rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


# ------------------------------------------------------------------------------------------------ Markdown bits
def md_inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def md_tables(text: str) -> list[dict]:
    """Pipe tables as {"title": nearest heading, "headers": [...], "rows": [[...]]} (cells are raw Markdown)."""
    out, heading, lines = [], "", text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]
            headers, rows = cells(line), []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            out.append({"title": heading, "headers": headers, "rows": rows})
            continue
        i += 1
    return out


def md_intro(text: str, max_paras: int = 2) -> list[str]:
    """First prose paragraphs (not headings, tables, lists or code)."""
    paras, cur, fence = [], [], False
    for line in text.splitlines() + [""]:
        s = line.strip()
        if s.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if not s or s.startswith(("#", "|", "- ", "* ", "1.")):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            if len(paras) >= max_paras:
                break
            continue
        cur.append(s)
    return paras[:max_paras]


def md_title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


# ------------------------------------------------------------------------------------------------ loaders
def _runs(d: Path) -> dict[str, dict]:
    out = {}
    for aud in AUDITOR_ORDER:
        j = _json(d / f"results_{aud}.json")
        if isinstance(j, dict) and j.get("rows"):
            out[aud] = j
    return out


def _labels(d: Path) -> dict[str, dict]:
    return {p.name[: -len(".label.json")]: _json(p) or {} for p in sorted(Path(d).glob("*.label.json"))}


def hard_cases(results_dir: Path, fixtures_dir: Path) -> dict | None:
    runs = _runs(results_dir / "hard_cases")
    if not runs:
        return None
    labels = _labels(fixtures_dir / "hard_cases")
    return {"runs": runs, "labels": labels,
            "keys": {c: _rel(fixtures_dir / "hard_cases" / f"{c}.jsonl") for c in labels},
            "sources": [_rel(results_dir / "hard_cases" / f"results_{a}.json") for a in runs]}


def monitor_attacks(results_dir: Path, fixtures_dir: Path) -> dict | None:
    runs = _runs(results_dir / "monitor_attacks")
    if not runs:
        return None
    labels = _labels(fixtures_dir / "monitor_attacks")
    return {"runs": runs, "labels": labels,
            "keys": {c: _rel(fixtures_dir / "monitor_attacks" / f"{c}.jsonl") for c in labels},
            "sources": [_rel(results_dir / "monitor_attacks" / f"results_{a}.json") for a in runs]}


def obfuscation(results_dir: Path) -> dict | None:
    j = _json(results_dir / "obfuscation" / "OBFUSCATION.json")
    if not isinstance(j, dict):
        return None
    doc = _text(ROOT / "docs" / "obfuscation.md") or ""
    m = re.search(r"^\*\*Short answer\.\*\*(.+?)(?:\n\n|\Z)", doc, re.MULTILINE | re.DOTALL)
    extra = sorted(p.name for p in (results_dir / "obfuscation").glob("OBFUSCATION_*.json"))
    return {"summary": j.get("summary") or [], "hand_check": j.get("hand_check"),
            "short_answer": m.group(1).strip() if m else "", "extra": extra,
            "variants": _variants(results_dir / "obfuscation" / "OBFUSCATION_corrected.md", results_dir),
            "sources": [_rel(results_dir / "obfuscation" / "OBFUSCATION.json"), "docs/obfuscation.md"]}


def bestofn(results_dir: Path) -> dict | None:
    d = results_dir / "mitigation_bestofn_v2"
    j = _json(d / "MITIGATION_bestofn.json")
    if not isinstance(j, dict):
        return None
    md = _text(d / "MITIGATION_bestofn.md") or ""
    return {"auditor": j.get("auditor"), "mode": j.get("mode"), "overall": j.get("overall") or {},
            "slices": j.get("slices") or [], "sweep": j.get("sweep") or [], "intro": md_intro(md, 1),
            "variants": _variants(d / "MITIGATION_bestofn_corrected.md", results_dir),
            "sources": [_rel(d / "MITIGATION_bestofn.json")]}


def relabel(results_dir: Path) -> dict | None:
    """v3 relabelling with the fixed labeller: results/<exp>/relabel.json (runtime vs relabelled hack rates, flips)."""
    exps = []
    for p in sorted(results_dir.glob("*/relabel.json")):
        j = _json(p)
        if not isinstance(j, dict) or "hack_rate_by_config" not in j:
            continue
        exp = p.parent.name
        flips = [{"trajectory_id": t, "runtime": f.get("runtime"), "relabelled": f.get("relabelled"),
                  "key": _rel(p.parent / "trajectories" / f"{t}.jsonl")}
                 for t, f in sorted((j.get("flipped") or {}).items())]
        exps.append({"experiment": exp, "trajectories": j.get("trajectories"), "commit": j.get("labeller_commit"),
                     "by_config": j["hack_rate_by_config"], "flipped": flips, "source": _rel(p)})
    return {"experiments": exps, "sources": [e["source"] for e in exps]} if exps else None


def _money(s: str) -> float | None:
    m = re.search(r"\$([\d,]+\.?\d*)", s or "")
    return float(m.group(1).replace(",", "")) if m else None


def cost(results_dir: Path) -> dict | None:
    text = _text(results_dir / "COST.md")
    if not text:
        return None
    tables = md_tables(text)
    per_row = next((t for t in tables if "results dir" in t["headers"] and "USD" in t["headers"]), None)
    by_role = next((t for t in tables if t["headers"][:1] == ["role"] and "USD" in t["headers"]), None)
    dirs: dict[str, dict] = {}
    if per_row:
        h = per_row["headers"]
        for r in per_row["rows"]:
            row = dict(zip(h, r, strict=False))
            d = dirs.setdefault(row["results dir"].strip("`"), {"usd": 0.0, "calls": 0, "roles": {}})
            usd = _money(row.get("USD", "")) or 0.0
            d["usd"] += usd
            d["calls"] += int(re.sub(r"\D", "", row.get("calls", "")) or 0)
            d["roles"][row.get("role", "?")] = d["roles"].get(row.get("role", "?"), 0.0) + usd
    roles = []
    if by_role:
        for r in by_role["rows"]:
            row = dict(zip(by_role["headers"], r, strict=False))
            roles.append({"role": row["role"].strip("*"), "calls": row.get("calls", ""), "usd": _money(row.get("USD", ""))})
    notes = [p for p in md_intro(text, 4) if p.startswith("Prices")]
    return {"dirs": dirs, "roles": roles, "notes": notes, "sources": [_rel(results_dir / "COST.md")]}


def _figures(md: Path, results_dir: Path) -> list[str]:
    """SVG figures for a write-up: those next to it in results/<dir>/, or results/figures/<stem>_*.svg for top-level ones."""
    if md.parent.resolve() == results_dir.resolve():
        found = sorted((results_dir / "figures").glob(f"{md.stem.lower()}*.svg"))
    elif md.parent.parent.resolve() == results_dir.resolve():
        found = sorted(md.parent.glob("*.svg"))
    else:
        found = []
    return [_rel(p) for p in found]


def inline_svg(path: Path) -> str:
    text = _text(path) or ""
    text = re.sub(r"<\?xml[^>]*>|<!DOCTYPE[^>]*>", "", text)
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\son\w+=\"[^\"]*\"", "", text)
    return text if text.lstrip().startswith("<svg") else ""


def _num(cell: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", cell or "")
    if not m:
        return None
    return float(m.group(0)) / (100 if "%" in cell[: m.end() + 1] else 1)


def cascade_chart(doc: dict) -> str:
    t = next((t for t in doc["tables"] if {"policy", "recall", "FPR"} <= set(t["headers"])), None)
    if not t:
        return ""
    h = t["headers"]
    usd = "USD / trajectory" if "USD / trajectory" in h else None
    groups = []
    for r in t["rows"]:
        row = dict(zip(h, r, strict=False))
        label = re.sub(r"^\(\w\)\s*", "", row["policy"]).replace(" only", "").replace(" -> ", "→")
        cost_ = re.search(r"\$[\d.]+", row.get(usd, "")) if usd else None
        groups.append((label + (f"\n{cost_.group(0)}/traj" if cost_ else ""),
                       [("recall", _num(row["recall"])), ("FPR", _num(row["FPR"]))]))
    return bar_chart("Default operating points: recall vs false-positive rate, and cost per trajectory", groups,
                     ["recall", "FPR"], colors={"recall": "#2ecc71", "FPR": "#ff4d5e"}, width=640)


def calibration_chart(doc: dict) -> str:
    t = next((t for t in doc["tables"] if "ECE raw" in t["headers"]), None)
    if not t:
        return ""
    h = t["headers"]
    series = [s for s in ("ECE raw", "ECE platt", "ECE iso") if s in h]
    groups = [(f'{_short_model(dict(zip(h, r, strict=False))["auditor"])}\n{dict(zip(h, r, strict=False)).get("mode", "")}',
               [(s, _num(dict(zip(h, r, strict=False))[s])) for s in series]) for r in t["rows"]]
    top = max([v for _, vals in groups for _, v in vals if v] + [0.1])
    return bar_chart("Expected calibration error by auditor and mode (lower is better, leave-one-task-out)", groups,
                     series, ymax=round(top * 1.2, 2), fmt=lambda v: f"{v:.2f}", width=760)


def md_doc(p: Path, results_dir: Path) -> dict | None:
    text = _text(p) or ""
    tables = md_tables(text)
    if not tables:
        return None
    figs = _figures(p, results_dir)
    return {"id": "doc-" + re.sub(r"[^a-z0-9]+", "-", _rel(p).lower()).strip("-"), "name": p.name, "chart": p.name,
            "title": TITLES.get(p.name) or md_title(text, p.stem.replace("_", " ")), "intro": md_intro(text, 2),
            "tables": tables[:3], "more_tables": max(0, len(tables) - 3), "figures": figs,
            "sources": [_rel(p)] + figs}


def _variants(p: Path, results_dir: Path) -> list[dict]:
    v = md_doc(p, results_dir) if p.is_file() else None
    return [v] if v else []


def _base_of(p: Path) -> Path | None:
    """X_corrected.md -> X.md; results/<name>_corrected/X.md -> results/<name>/X.md, else docs/<name>.md."""
    if p.stem.endswith(CORRECTED):
        return p.with_name(p.stem[: -len(CORRECTED)] + p.suffix)
    if p.parent.name.endswith(CORRECTED):
        name = p.parent.name[: -len(CORRECTED)]
        sibling = p.parent.with_name(name) / p.name
        return sibling if sibling.is_file() else ROOT / "docs" / f"{name}.md"
    return None


def _attach(base: dict, v: dict) -> None:
    corr = lambda fs: [f for f in fs if CORRECTED in Path(f).stem]
    moved = corr(base["figures"])
    base["figures"] = [f for f in base["figures"] if f not in moved]
    base["sources"] = [s for s in base["sources"] if s not in moved]
    v["figures"] = list(dict.fromkeys(moved + corr(v["figures"])))
    v["chart"], v["sources"] = base["chart"], v["sources"][:1] + v["figures"]
    base.setdefault("variants", []).append(v)


def generic_docs(results_dir: Path) -> list[dict]:
    """Result write-ups we have no bespoke view for: new results/<dir>/*.md, new top-level results/*.md, EXTRA_DOCS.
    A *_corrected write-up is folded into its original as a variant."""
    paths: list[Path] = []
    for d in sorted(p for p in results_dir.iterdir() if p.is_dir()):
        if d.name in HANDLED_DIRS or (d / "trajectories").is_dir() or d.name.startswith("figures"):
            continue
        paths += sorted(d.glob("*.md"))
    paths += sorted(p for p in results_dir.glob("*.md") if p.name not in KNOWN_TOP)
    paths += [ROOT / p for p in EXTRA_DOCS if (ROOT / p).is_file()]
    docs = {p.resolve(): d for p in paths if (d := md_doc(p, results_dir))}
    bases = {p: (b.resolve() if (b := _base_of(p)) else None) for p in docs}
    for p, b in bases.items():
        if b in docs:
            _attach(docs[b], docs[p])
    return [d for p, d in docs.items() if bases[p] not in docs]


def headline(results_dir: Path) -> dict | None:
    p = results_dir / "figures" / "headline.svg"
    svg = inline_svg(p) if p.is_file() else ""
    if not svg:
        return None
    tag = lambda t: html.unescape(m.group(1).strip()) if (m := re.search(rf"<{t}[^>]*>(.*?)</{t}>", svg, re.DOTALL)) else ""
    return {"svg": svg, "title": tag("title") or "Headline", "desc": tag("desc"), "sources": [_rel(p)]}


def benchmarks(results_dir: Path = RESULTS_DIR, fixtures_dir: Path = FIXTURES_DIR) -> dict:
    results_dir, fixtures_dir = Path(results_dir), Path(fixtures_dir)
    return {"headline": headline(results_dir), "hard_cases": hard_cases(results_dir, fixtures_dir),
            "monitor_attacks": monitor_attacks(results_dir, fixtures_dir),
            "relabel": relabel(results_dir), "obfuscation": obfuscation(results_dir), "bestofn": bestofn(results_dir),
            "cost": cost(results_dir),
            "docs": generic_docs(results_dir)}


def trajectory_keys(data: dict) -> list[str]:
    """Every benchmark trajectory the page links to (the static export renders these)."""
    out = []
    for name in ("hard_cases", "monitor_attacks"):
        sec = data.get(name)
        if sec:
            out += [k for k in sec["keys"].values() if (ROOT / k).exists()]
    return out


# ------------------------------------------------------------------------------------------------ rendering
def _f(x, digits: int = 2) -> str:
    return "–" if x is None else f"{x:.{digits}f}"


_AVAILABLE: set[str] | None = None  # static export: only these trajectories have compare/replay pages


def _has(key: str) -> bool:
    return _AVAILABLE is None or key in _AVAILABLE


def _links(key: str) -> str:
    if not _has(key):
        return '<span class="dim" title="not in the static export; run python -m demo.app">–</span>'
    return (f'<a href="{esc(url("/compare", traj=key))}">compare</a> · '
            f'<a href="{esc(url("/view", traj=key, live=0, progressive=1))}">replay</a>')


def _cell(row: dict | None, truth: bool | None, compact: bool = False) -> str:
    if row is None:
        return '<span class="vb">–</span>'
    if row.get("predicted") is None:
        return '<span class="vb wrong" title="error">err</span>'
    hack = bool(row["predicted"])
    wrong = truth is not None and hack != truth
    conf = row.get("confidence")
    return (f'<span class="vb {"hack" if hack else "clean"}{" wrong" if wrong else ""}" '
            f'title="{"HACK" if hack else "clean"} · confidence {_f(conf)}">{"⚑" if hack else "✓"}'
            f'{"" if compact else " " + _f(conf)}</span>')


def _modes_in(runs: dict) -> list[str]:
    return [m for m in MODES if any(r["mode"] == m for j in runs.values() for r in j["rows"])]


def _section(sid: str, title: str, sources: list[str], body: str, lede: str = "") -> str:
    src = ", ".join(f"<code>{esc(s)}</code>" for s in sources)
    return (f'<section class="bench" id="{sid}"><h2>{esc(title)}</h2>'
            + (f'<p class="lede">{lede}</p>' if lede else "") + body
            + f'<p class="src">Source: {src}</p></section>')


def render_headline(sec: dict) -> str:
    return _section("headline", sec["title"], sec["sources"], f'<div class="fig headline">{sec["svg"]}</div>',
                    esc(sec["desc"]))


def render_hard_cases(sec: dict) -> str:
    cats = ["hard_negative", "obfuscated_hack", "reasoning_only", "report_only"]
    parts = []
    for aud, run in sec["runs"].items():
        modes = [m for m in MODES if m in run["summary"]]
        rows, groups = [], []
        for cat in cats + ["all"]:
            for m in modes:
                s = run["summary"][m].get(cat)
                if not s:
                    continue
                rows.append([f"<b>{esc(cat)}</b>" if cat == "all" else esc(cat), esc(m), s["n"], s["tp"], s["fp"], s["fn"],
                             s["tn"], _f(s.get("precision")), _f(s.get("recall")), _f(s.get("fpr"))])
        for cat in cats:
            vals = []
            for m in modes:
                s = run["summary"][m].get(cat)
                vals.append((m, None if not s or not s["n"] else (s["tp"] + s["fp"]) / s["n"]))
            groups.append((cat.replace("_", " ") + ("\n(FPR)" if cat == "hard_negative" else "\n(recall)"), vals))
        title = f"{aud} auditor" + (f" ({run['model']})" if run.get("model") else "")
        parts.append(f'<h3>{esc(title)}</h3><div class="two">'
                     + bar_chart("Flag rate by category: recall on hacks, false-positive rate on hard negatives",
                                 groups, modes, width=560)
                     + _table(["category", "mode", "n", "TP", "FP", "FN", "TN", "precision", "recall", "FPR"], rows, 2)
                     + "</div>")
    # per-case list with the preferred auditor's verdicts
    by = {}
    for aud, run in sec["runs"].items():
        for r in run["rows"]:
            by[(r["case_id"], aud, r["mode"])] = r
    cols = [(a, m) for a in sec["runs"] for m in _modes_in({a: sec["runs"][a]})]
    head = ["case", "category", "task", "truth"] + [f"{a[:6]} {MODE_SHORT[m]}" for a, m in cols] + ["open"]
    body = []
    for case, label in sorted(sec["labels"].items(), key=lambda kv: (kv[1].get("category", ""), kv[0])):
        truth = label.get("hacked")
        body.append([f'<code title="{esc(label.get("why", ""))}">{esc(case)}</code>', esc(label.get("category", "")),
                     esc(label.get("task_id", "")),
                     f'<span class="pill {"solid-red" if truth else "green"}">{"HACK" if truth else "clean"}</span>']
                    + [_cell(by.get((case, a, m)), truth) for a, m in cols] + [_links(sec["keys"][case])])
    parts.append(f'<details open><summary>All {len(body)} cases (hover a case for why it is labelled so; '
                 f'red outline = auditor disagrees with the hand label)</summary>{_table(head, body, 4)}</details>')
    return _section("hard-cases", "Hard cases: hand-built red-team trajectories", sec["sources"], "".join(parts),
                    "Hand-labelled trajectories built to fool the auditor: honest runs that look suspicious (hard "
                    "negatives), hacks that hide in the report or the reasoning only, and obfuscated hacks.")


def render_monitor_attacks(sec: dict) -> str:
    parts = []
    attacks = []
    for run in sec["runs"].values():
        attacks += [a for a in run["summary"] if a not in attacks]
    for aud, run in sec["runs"].items():
        modes = [m for m in MODES if any(m in cells for cells in run["summary"].values())]
        rows, groups = [], []
        for a in attacks:
            cells = run["summary"].get(a, {})
            row = [f"<b>{esc(a)}</b>" if a == "none" else esc(a)]
            for m in modes:
                s = cells.get(m)
                if not s or not s["n"]:
                    row.append("n/a")
                    continue
                delta = "" if a == "none" or s.get("delta") is None else (
                    f' <span class="{"neg" if s["delta"] < 0 else "dim"}">Δ {s["delta"]:+.2f}'
                    + (f', {s["flipped"]} flipped' if s.get("flipped") else "") + "</span>")
                row.append(f'{s["detected"]}/{s["n"]} = {s["rate"]:.2f}{delta}')
            rows.append(row)
            groups.append((a.replace("_", " ").replace("evidence ", "").replace("reasoning ", "reasoning\n"),
                           [(m, (cells.get(m) or {}).get("rate")) for m in modes]))
        title = f"{aud} auditor" + (f" ({run['model']})" if run.get("model") else "")
        parts.append(f'<h3>{esc(title)}</h3><div class="two">'
                     + bar_chart("Detection rate per attack (every variant still contains the hack)", groups, modes,
                                 width=620, show_na=False)
                     + _table(["attack"] + modes, rows, 1) + "</div>")
    # source x attack matrix; each cell opens that variant
    aud = next(iter(sec["runs"]))
    run = sec["runs"][aud]
    modes = [m for m in MODES if any(r["mode"] == m for r in run["rows"])]
    by = {(r["case_id"], r["mode"]): r for r in run["rows"]}
    sources: dict[str, dict[str, str]] = {}
    for case, label in sec["labels"].items():
        sources.setdefault(label.get("source", ""), {})[label.get("attack", "")] = case
    body = []
    for src in sorted(sources):
        parts_ = Path(src).parts
        name = "/".join(parts_[-3::2]).replace(".jsonl", "") if len(parts_) >= 3 else src
        row = [f"<code>{esc(name)}</code>"]
        for a in attacks:
            case = sources[src].get(a)
            if not case:
                row.append("")
                continue
            marks = " ".join(f'<span class="mm">{MODE_SHORT[m]}</span>{_cell(by.get((case, m)), True, True)}' for m in modes)
            row.append(f'<a class="mx" href="{esc(url("/compare", traj=sec["keys"][case]))}" '
                       f'title="{esc(case)}">{marks}</a>')
        body.append(row)
    parts.append(f'<details open><summary>Per trajectory ({aud} auditor). Click a cell to compare its verdicts across modes; '
                 f'✓ in red = hack missed</summary><div class="scroll">{_table(["source"] + [a.replace("_", " ") for a in attacks], body, 99)}</div></details>')
    return _section("monitor-attacks", "Monitor attacks: real hacks plus an attack on the auditor", sec["sources"],
                    "".join(parts),
                    "Ten judge-positive covert runs from v2, each re-built with an attack aimed at the monitor: a "
                    "prompt injection in the report or echoed from a written file, laundered reasoning, padding with "
                    "benign tool calls, a fake integrity self-check, or all of them. Δ is against the unattacked run.")


def _rate(d: dict | None) -> float | None:
    return None if not d or not d.get("n") else d["hacked"] / d["n"]


def render_relabel(sec: dict) -> str:
    groups, rows, flips = [], [], []
    for e in sec["experiments"]:
        rt, rl = e["by_config"].get("runtime", {}), e["by_config"].get("relabelled", {})
        tot = lambda d: {"hacked": sum(v["hacked"] for v in d.values()), "n": sum(v["n"] for v in d.values())}
        groups.append((e["experiment"].replace("_", "\n", 1), [("runtime labeller", _rate(tot(rt))),
                                                               ("fixed labeller", _rate(tot(rl)))]))
        for cfg in sorted(set(rt) | set(rl), key=lambda c: catalog_order(c)):
            a, b = rt.get(cfg), rl.get(cfg)
            rows.append([f"<code>{esc(e['experiment'])}</code>", esc(cfg),
                         f'{a["hacked"]}/{a["n"]} = {_rate(a):.2f}' if a else "–",
                         f'{b["hacked"]}/{b["n"]} = {_rate(b):.2f}' if b else "–"])
        for f in e["flipped"]:
            name = f"{e['experiment']}/{f['trajectory_id']}"
            arrow = f'{"HACK" if f["runtime"] else "clean"} → {"HACK" if f["relabelled"] else "clean"}'
            link = (f'<a href="{esc(url("/compare", traj=f["key"]))}"><code>{esc(name)}</code></a>' if _has(f["key"])
                    else f"<code>{esc(name)}</code>")
            flips.append(f'<li>{link} <span class="dim">{arrow}</span></li>')
    chart = bar_chart("Hack rate before and after relabelling (all configs)", groups,
                      ["runtime labeller", "fixed labeller"], colors={"runtime labeller": "#8a96ad", "fixed labeller": "#ff4d5e"},
                      width=640)
    body = (f'<div class="two">{chart}{_table(["experiment", "config", "runtime labeller", "fixed labeller"], rows, 2)}</div>'
            f'<details><summary>{len(flips)} trajectories whose label flipped</summary><ul class="flips">{"".join(flips)}</ul></details>')
    return _section("relabel", "v3 relabelling with the fixed labeller", sec["sources"], body,
                    "The v3 runs were labelled at run time by a labeller with known false positives (e.g. honest "
                    "reports quoting \"large effect\" only to reject it). The fixed labeller re-scores every stored "
                    "episode; this is how the hack rates moved.")


def catalog_order(cfg: str) -> int:
    order = ["honest", "incentivized", "pressure", "sycophantic_pi", "covert_monitored", "covert"]
    return order.index(cfg) if cfg in order else len(order)


def judge_chart(doc: dict) -> str:
    t = next((t for t in doc["tables"] if "accuracy" in t["headers"] and "comparison" in t["headers"]), None)
    if not t:
        return ""
    h = t["headers"]
    kappa = next((x for x in h if "κ" in x or "kappa" in x.lower()), None)
    series = ["accuracy"] + (["Cohen's κ"] if kappa else [])
    groups = [(dict(zip(h, r, strict=False))["comparison"].replace("`", ""),
               [("accuracy", _num(dict(zip(h, r, strict=False))["accuracy"]))] + ([("Cohen's κ", _num(dict(zip(h, r, strict=False))[kappa]))] if kappa else []))
              for r in t["rows"]]
    return bar_chart("Agreement with blind labels", groups, series, width=520, fmt=lambda v: f"{v:.2f}")


def render_obfuscation(sec: dict) -> str:
    rows, groups = [], {}
    subjects = []
    for s in sec["summary"]:
        subj = _short_model(s["subject_model"]).replace("-4-", "-4.")
        if subj not in subjects:
            subjects.append(subj)
        ci = s.get("disclosure_ci") or [None, None]
        rows.append([esc(subj), esc(s["agent_config"]), esc(s.get("label_source", "")), s["n"], s["hacked"],
                     s.get("disclosed", 0),
                     "–" if s.get("disclosure_rate") is None else f'{s["disclosure_rate"]:.2f} [{_f(ci[0])}, {_f(ci[1])}]',
                     _f(s.get("recall_full_trace")), _f(s.get("recall_report_only")), _f(s.get("recall_final_report"))])
        if s["hacked"]:
            groups.setdefault(s["agent_config"], []).append((subj, s.get("disclosure_rate")))
    hc = sec.get("hand_check") or {}
    check = (f'<p class="sub">Rubric vs hand labels: n = {hc["n"]}, accuracy {_f(hc.get("accuracy"))}, precision '
             f'{_f(hc.get("precision"))}, recall {_f(hc.get("recall"))}.</p>') if hc.get("n") else ""
    order = ["covert", "covert_monitored", "pressure", "incentivized", "sycophantic_pi", "honest"]
    g = sorted(groups.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)
    body = ('<div class="stack">' + bar_chart("Share of hacked runs whose private reasoning spells out the hack",
                                            [(k.replace("_", " "), v) for k, v in g], subjects, width=600, show_na=False)
            + _table(["subject", "config", "label", "n", "hacked", "disclosed", "disclosure [95% CI]",
                      "recall FT", "recall RO", "recall FR"], rows, 3) + "</div>" + check)
    if sec.get("extra"):
        body += '<p class="sub">Also in results/obfuscation: ' + ", ".join(f"<code>{esc(x)}</code>" for x in sec["extra"]) + "</p>"
    body += _variant_blocks(sec.get("variants"))
    return _section("obfuscation", "Reasoning disclosure: do hackers say so in their reasoning?", sec["sources"], body,
                    md_inline(sec["short_answer"]) if sec.get("short_answer") else "")


POLICIES = [("random", "random"), ("grader_only", "grader-only"), ("veto_random", "veto+random"),
            ("veto_grader", "veto+grader"), ("oracle", "oracle")]


def render_bestofn(sec: dict) -> str:
    ov = sec["overall"]
    vals = [(label, ov.get(f"{k}_hack", ov.get(k))) for k, label in POLICIES]
    chart = bar_chart(f"Hack rate of the shipped trajectory (all {ov.get('groups', '?')} groups, n = "
                      f"{ov.get('trajectories', '?')})", [(lab, [("hack rate", v)]) for lab, v in vals], ["hack rate"],
                      colors={"hack rate": "#e5484d"}, ymax=max([v for _, v in vals if v] + [0.5]), width=560)
    rows = []
    for s in sec["slices"] + [dict(ov, subject_model="all", agent_config="")]:
        rows.append([esc(_short_model(s.get("subject_model", ""))) + (f" / {esc(s['agent_config'])}" if s.get("agent_config") else ""),
                     s.get("groups"), s.get("trajectories")]
                    + [_f(s.get(f"{k}_hack", s.get(k)), 3) for k, _ in POLICIES] + [_f(s.get("fallback_rate"), 3)])
    sweep = [[esc(_short_model(s["auditor"])), esc(s["mode"]), _f(s["overall"].get("veto_grader_hack"), 3),
              _f(s["overall"].get("veto_random_hack"), 3), _f(s["overall"].get("fallback_rate"), 3)]
             for s in sec["sweep"] if s.get("veto") == "hack_detected"]
    body = (f'<div class="stack">{chart}{_table(["slice", "groups", "n"] + [lab for _, lab in POLICIES] + ["fallback"], rows, 1)}</div>'
            + (f'<h3>Which auditor vetoes (veto = hack_detected)</h3>'
               f'{_table(["auditor", "mode", "veto+grader", "veto+random", "fallback"], sweep, 2)}' if sweep else ""))
    lede = md_inline(sec["intro"][0]) if sec.get("intro") else ""
    body += _variant_blocks(sec.get("variants"))
    return _section("bestofn", f"Best-of-n with an auditor veto ({_short_model(sec.get('auditor') or '')}, "
                               f"{sec.get('mode') or ''})", sec["sources"], body, lede)


def render_cost(sec: dict) -> str:
    roles = [r for r in sec["roles"] if r["role"] != "total"]
    total = next((r for r in sec["roles"] if r["role"] == "total"), None)
    top = max([r["usd"] or 0 for r in roles] + [1])
    chart = bar_chart("API spend by role (USD)", [(r["role"], [("USD", r["usd"])]) for r in roles], ["USD"],
                      colors={"USD": "#3e9bff"}, ymax=top * 1.15, fmt=lambda v: f"${v:,.0f}", width=480)
    dirs = sorted(sec["dirs"].items(), key=lambda kv: -kv[1]["usd"])
    role_names = [r["role"] for r in roles]
    rows = [[f"<code>{esc(d)}</code>", f'{v["calls"]:,}'] + [f'${v["roles"].get(r, 0):,.2f}' for r in role_names]
            + [f'<b>${v["usd"]:,.2f}</b>'] for d, v in dirs]
    if total:
        rows.append(["<b>total</b>", esc(total["calls"])] + [f'${(r["usd"] or 0):,.2f}' for r in roles]
                    + [f'<b>${(total["usd"] or 0):,.2f}</b>'])
    body = f'<div class="two">{chart}{_table(["results dir", "calls"] + role_names + ["USD"], rows, 1)}</div>'
    body += "".join(f'<p class="sub">{md_inline(n)}</p>' for n in sec.get("notes", []))
    lede = f"Total API spend: <b>${total['usd']:,.2f}</b> over {esc(total['calls'])} calls." if total and total["usd"] else ""
    return _section("cost", "Cost", sec["sources"], body, lede)


DOC_CHARTS = {"CASCADE.md": cascade_chart, "CALIBRATION.md": calibration_chart, "judge_validation.md": judge_chart}


def _doc_body(doc: dict, paras: list[str]) -> str:
    body = "".join(f'<p class="sub">{md_inline(p)}</p>' for p in paras)
    chart = DOC_CHARTS[doc["chart"]](doc) if doc.get("chart") in DOC_CHARTS else ""
    figs = "".join(f'<div class="fig">{s}</div>' for s in (inline_svg(ROOT / f) for f in doc.get("figures", [])) if s)
    if chart or figs:
        body += f'<div class="figs">{chart}{figs}</div>'
    for t in doc["tables"]:
        rows = [[md_inline(c) for c in r] for r in t["rows"][:MAX_GENERIC_ROWS]]
        more = len(t["rows"]) - len(rows)
        body += (f'<h3>{md_inline(t["title"])}</h3>' if t["title"] and t["title"] != doc["title"] else "")
        body += _table([re.sub(r"[`*]", "", h) for h in t["headers"]], rows, 99)
        if more > 0:
            body += f'<p class="sub">… {more} more rows in the source file.</p>'
    if doc["more_tables"]:
        body += f'<p class="sub">{doc["more_tables"]} more table(s) in the source file.</p>'
    return body


def _variant_blocks(variants: list[dict] | None) -> str:
    out = []
    for v in variants or []:
        src = ", ".join(f"<code>{esc(s)}</code>" for s in v["sources"])
        out.append(f'<details class="variant"><summary>The same analysis under the <b>corrected label</b></summary>'
                   f'<p class="sub">{esc(CORRECTED_NOTE)}</p>{_doc_body(v, [])}<p class="src">Source: {src}</p></details>')
    return "".join(out)


def render_doc(doc: dict) -> str:
    body = _doc_body(doc, doc["intro"][1:]) + _variant_blocks(doc.get("variants"))
    return _section(doc["id"], doc["title"], doc["sources"], body, md_inline(doc["intro"][0]) if doc["intro"] else "")


BENCH_CSS = """
.bench{margin:28px 0 40px;padding-top:8px;border-top:1px solid var(--line)}
.bench h2{margin:10px 0 6px}.bench h3{margin:22px 0 8px;color:var(--dim);font-size:15px;text-transform:uppercase;letter-spacing:.04em}
.bench .lede{color:var(--text);max-width:980px;line-height:1.5}.bench .src{color:var(--faint);font-size:13px;margin-top:14px}
.bench .two{display:grid;grid-template-columns:minmax(380px,1fr) minmax(420px,1.3fr);gap:24px;align-items:start}
.bench .stack>.chart{max-width:760px;margin-bottom:16px}
@media(max-width:1100px){.bench .two{grid-template-columns:1fr}}
.bench table{font-size:13px}.bench details summary{cursor:pointer;color:var(--dim);margin:14px 0 8px}
.bench .neg{color:#ff8a8a}.bench .dim{color:var(--faint)}.bench .mm{color:var(--faint);font-size:11px;margin:0 2px 0 4px}
.bench .figs{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;margin:12px 0}
.bench .figs>.chart{flex:0 1 760px}.bench .fig{flex:1 1 560px;max-width:980px;background:#fff;border-radius:12px;padding:6px}
.bench .fig svg{width:100%;height:auto;display:block}
.bench .fig.headline{max-width:1080px}
.bench .scroll{overflow-x:auto}.bench .scroll td,.bench .scroll th{padding-left:6px;padding-right:6px}
.bench details.variant{border:1px solid var(--line);border-radius:10px;padding:2px 14px;margin:16px 0}
.bench details.variant>summary{color:var(--text)}
.bench ul.flips{columns:3 360px;font-size:13px;margin:6px 0}
a.mx{text-decoration:none;white-space:nowrap}a.mx:hover .vb{filter:brightness(1.3)}
.jump{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}.jump a{cursor:pointer}
"""
JUMP_JS = """document.querySelectorAll('[data-jump]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();
const t=document.getElementById(a.dataset.jump);if(t)t.scrollIntoView({behavior:'smooth'});}));"""


def benchmarks_page(data: dict, available: set[str] | None = None) -> str:
    """available: trajectory keys that have pages (static export); None = all (server)."""
    global _AVAILABLE
    _AVAILABLE = available
    try:
        return _benchmarks_page(data)
    finally:
        _AVAILABLE = None


def _benchmarks_page(data: dict) -> str:
    sections = []
    for name, fn, title in (("headline", render_headline, "Headline"), ("hard_cases", render_hard_cases, "Hard cases"),
                            ("monitor_attacks", render_monitor_attacks, "Monitor attacks"),
                            ("relabel", render_relabel, "Relabelling"),
                            ("obfuscation", render_obfuscation, "Reasoning disclosure"),
                            ("bestofn", render_bestofn, "Best-of-n"), ("cost", render_cost, "Cost")):
        if data.get(name):
            html_ = fn(data[name])
            sections.append((re.search(r'id="([^"]+)"', html_).group(1), title, html_))
    for doc in data.get("docs") or []:
        sections.append((doc["id"], doc["title"], render_doc(doc)))
    jump = "".join(f'<a class="btn" data-jump="{sid}">{esc(t)}</a>' for sid, t, _ in sections)
    body = ('<h1>Benchmarks</h1><p class="sub">Stress tests of the auditor and what the results cost, read from the '
            'committed result files. Hard-case and attack trajectories open in the replay and mode-comparison views.</p>'
            f'<div class="jump">{jump}</div>' + "".join(h for _, _, h in sections))
    if not sections:
        body += '<p class="sub">No benchmark results found under results/.</p>'
    return shell("Benchmarks", body, "benchmarks", head=BENCH_CSS, script=JUMP_JS)

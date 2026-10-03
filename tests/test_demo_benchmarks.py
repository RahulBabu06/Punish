"""Benchmarks page (demo.benchmarks): red-team corpora, obfuscation, best-of-n, cost and generic write-ups."""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo import benchmarks, catalog, export
from demo.app import AppConfig, BadRequest, make_server, resolve_options
from demo.core import StreamOptions, verdict_candidates

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
HARD = ROOT / "fixtures" / "hard_cases"
ATTACKS = ROOT / "fixtures" / "monitor_attacks"
needs_results = pytest.mark.skipif(not (RESULTS / "hard_cases" / "results_heuristic.json").exists()
                                   or not (RESULTS / "monitor_attacks" / "results_heuristic.json").exists(),
                                   reason="committed benchmark results not present")


def test_markdown_helpers():
    text = "# Title\n\nFirst **bold** `x` para\ncontinues.\n\n## Part\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\nAfter."
    assert benchmarks.md_title(text, "f") == "Title"
    assert benchmarks.md_intro(text) == ["First **bold** `x` para continues.", "After."]
    assert benchmarks.md_tables(text) == [{"title": "Part", "headers": ["a", "b"], "rows": [["1", "2"], ["3", "4"]]}]
    assert benchmarks.md_inline("**b** `c` <i>") == "<b>b</b> <code>c</code> &lt;i&gt;"


@needs_results
def test_benchmarks_from_committed_results():
    d = benchmarks.benchmarks()
    for name in ("hard_cases", "monitor_attacks", "obfuscation", "bestofn", "cost"):
        assert d[name], name
    keys = benchmarks.trajectory_keys(d)
    assert len(keys) == len(list(HARD.glob("*.jsonl"))) + len(list(ATTACKS.glob("*.jsonl")))
    assert all((ROOT / k).exists() for k in keys)
    assert d["cost"]["roles"] and any(r["role"] == "total" and r["usd"] > 0 for r in d["cost"]["roles"])
    html = benchmarks.benchmarks_page(d)
    for sid in ("hard-cases", "monitor-attacks", "obfuscation", "bestofn", "cost"):
        assert f'id="{sid}"' in html
    assert html.count("<svg") >= 5
    assert "/compare?traj=fixtures%2Fhard_cases%2F" in html and "/compare?traj=fixtures%2Fmonitor_attacks%2F" in html
    assert "/view?traj=fixtures%2Fhard_cases%2F" in html
    json.dumps(d)  # the /api/benchmarks payload is JSON-serialisable


@needs_results
def test_benchmark_trajectories_find_their_verdicts_and_labels():
    case = sorted(HARD.glob("*.jsonl"))[0]
    assert RESULTS / "hard_cases" / "verdicts" / f"{case.stem}__report_only__heuristic.json" in \
        verdict_candidates(case, mode="report_only")
    c = catalog.compare(case)
    label = json.loads(case.with_name(f"{case.stem}.label.json").read_text())
    assert c["info"]["experiment"] == "hard_cases"
    assert c["info"]["labeller"] is label["hacked"] and c["info"]["labeller_source"] == "label"
    assert c["verdicts"]["full_trace"] and c["verdicts"]["report_only"]
    att = sorted(ATTACKS.glob("*__combined.jsonl"))[0]
    assert catalog.compare(att)["info"]["verdicts"]["full_trace"]["path"].startswith("results/monitor_attacks/verdicts/")


def test_benchmark_fixtures_are_served_but_other_fixtures_are_not():
    cfg = AppConfig()
    case = sorted(HARD.glob("*.jsonl"))[0]
    assert Path(resolve_options(cfg, {"traj": [str(case.relative_to(ROOT))]}).trajectory) == case.resolve()
    with pytest.raises(BadRequest):
        resolve_options(cfg, {"traj": ["fixtures/hard_cases/build.py"]})
    with pytest.raises(BadRequest):
        resolve_options(cfg, {"traj": ["fixtures/verdicts/example.json"]})


def test_generic_docs_pick_up_new_writeups(tmp_path):
    (tmp_path / "exp" / "trajectories").mkdir(parents=True)
    (tmp_path / "exp" / "NOTES.md").write_text("# Ignored\n\n| a |\n|---|\n| 1 |\n")
    (tmp_path / "newbench").mkdir()
    (tmp_path / "newbench" / "NEW.md").write_text("# Judge validation\n\nIntro.\n\n| k | v |\n|---|---|\n| x | 1 |\n")
    (tmp_path / "newbench" / "plot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>x</script>'
                                                    '<rect onclick="y" width="1"/></svg>')
    (tmp_path / "README.md").write_text("# Known\n\n| a |\n|---|\n| 1 |\n")
    (tmp_path / "CASCADE.md").write_text("# Cascade\n\n| policy | recall | FPR |\n|---|---|---|\n| (a) h only | 50% | 5% |\n")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "cascade_frontier.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    docs = {d["title"]: d for d in benchmarks.generic_docs(tmp_path)}
    assert {"Judge validation", "Cascade"} <= set(docs) and "Ignored" not in docs and "Known" not in docs
    assert docs["Cascade"]["figures"] and docs["Judge validation"]["figures"]
    html = benchmarks.render_doc(docs["Judge validation"])
    assert "Intro." in html and "<svg" in html and "<script" not in html and "onclick" not in html
    assert "<svg" in benchmarks.render_doc(docs["Cascade"]) and "recall" in benchmarks.render_doc(docs["Cascade"])


@needs_results
def test_server_benchmarks_routes():
    opts = StreamOptions(trajectory=ROOT / "fixtures" / "trajectories" / "example.jsonl", delay=0, poll=0.02)
    srv = make_server(AppConfig(defaults=opts), "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/benchmarks", timeout=20) as r:
            assert r.status == 200 and "Monitor attacks" in r.read().decode()
        with urllib.request.urlopen(base + "/api/benchmarks", timeout=20) as r:
            assert json.loads(r.read())["hard_cases"]
        case = "fixtures/monitor_attacks/" + sorted(ATTACKS.glob("*.jsonl"))[0].name
        for path in (f"/compare?traj={case}", f"/view?traj={case}", f"/verdict?traj={case}&auditor_mode=report_only"):
            with urllib.request.urlopen(base + path, timeout=20) as r:
                assert r.status == 200, path
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/view?traj=fixtures/hard_cases/build.py", timeout=20)
    finally:
        srv.shutdown()
        srv.server_close()


def test_export_dedupes_shared_blocks():
    style = "<style>" + "x" * 500 + "</style>"
    pages_ = {"/a": f"<head>{style}</head>A", "/b": f"<head>{style}</head><script>{'y' * 500}</script>"}
    blocks = export.shared_blocks(pages_)
    assert blocks == [style]
    assert export.dedupe(pages_["/a"], {style: 0}) == "<head><!--punish:0--></head>A"


@needs_results
def test_export_includes_benchmarks_and_their_trajectories():
    html, stats = export.build(max_gallery=5)
    m = __import__("re").search(r'<script type="application/json" id="punish-data">(.*?)</script>', html, 2 | 16)
    data = json.loads(m.group(1))
    assert "/benchmarks" in data["pages"] and data["blocks"]
    case = "fixtures/hard_cases/" + sorted(HARD.glob("*.jsonl"))[0].name
    assert f"/compare?traj={case}" in data["pages"]
    assert any(k.startswith(f"/view?traj={case}") for k in data["views"]) and case in data["lines"]
    assert stats["bytes"] < 5_000_000

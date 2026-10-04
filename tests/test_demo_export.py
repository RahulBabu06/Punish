"""Static export (demo.export): one self-contained HTML file, offline, from the committed results."""

import base64
import gzip
import json
import re

import pytest

from demo import catalog, export

pytestmark = pytest.mark.filterwarnings("ignore")


def _data(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="punish-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def _unpack(b64: str) -> str:
    return gzip.decompress(base64.b64decode(b64)).decode("utf-8")


@pytest.fixture(scope="module")
def built():
    return export.build(max_gallery=30)


def test_route_key_normalises_links():
    exps = ["a", "b"]
    fx = "fixtures/trajectories/example.jsonl"
    assert export.route_key("/view", exps, fx) == f"/view?traj={fx}&auditor_mode=full_trace&progressive=0&audit=file"
    assert export.route_key("/view?traj=x%2Fy.jsonl&amp;progressive=true&amp;delay=2&amp;auditor_mode=report_only", exps, fx) \
        == "/view?traj=x/y.jsonl&auditor_mode=report_only&progressive=1&audit=file"
    assert export.route_key("/dashboard?exp=b&exp=a&label=either", exps, fx) == "/dashboard?exp=&label=either"
    assert export.route_key("/dashboard", exps, fx) == "/dashboard?exp=&label=either"
    assert export.route_key("/dashboard?exp=b&label=judge", exps, fx) == "/dashboard?exp=b&label=judge"
    assert export.route_key("/?task_id=x", exps, fx) == "/"


def test_curate_keeps_must_and_spreads_experiments():
    items = catalog.gallery()
    must = {"results/probe_v1/trajectories/metric_gaming__covert__ep000.jsonl"}
    chosen = export.curate(items, must, 25)
    keys = {it["key"] for it in chosen}
    assert must <= keys and len(chosen) == 25
    assert len({it["experiment"] for it in chosen}) >= 8


def test_export_is_self_contained_and_small(built):
    html, stats = built
    assert stats["bytes"] < 5_000_000
    assert not re.search(r'(src|href)="(https?:)?//', html)
    assert "@import" not in html and "fetch(" not in html.split('id="punish-data"')[0]
    d = _data(html)
    for page in map(_unpack, d["pages"].values()):
        assert not re.search(r'(src|href)="(https?:)?//', page)
        assert 'rel="icon"' not in page


def test_export_covers_story_gallery_compare_dashboard(built):
    html, stats = built
    d = _data(html)
    assert {"/", "/story", "/dashboard?exp=&label=either"} <= set(d["pages"])
    exps = d["experiments"]
    assert all(f"/dashboard?exp={e}&label=judge" in d["pages"] for e in exps)
    assert stats["gallery"] >= 30
    for step in d["story"]:
        k = export.route_key(step["url"], exps, d["defaultTraj"])
        assert k in d["pages"] or k in d["views"], step
        if step["kind"] == "view":
            assert export.route_key("/compare?traj=" + step["traj"], exps, d["defaultTraj"]) in d["pages"]
    gallery = _unpack(d["pages"]["/"])
    assert "Static export" in gallery
    for href in re.findall(r'href="(/compare[^"]*)"', gallery):
        assert export.route_key(href, exps, d["defaultTraj"]) in d["pages"]


def test_export_replays_share_trajectory_lines(built):
    d = _data(built[0])
    view = json.loads(_unpack(next(iter(d["views"].values()))).replace("<\\/", "</"))
    lines = json.loads(_unpack(d["lines"][view["traj"]]).replace("<\\/", "</"))
    refs = [e[1] for e in view["events"] if e[0] == "@"]
    assert refs and max(refs) < len(lines)
    names = [e[0] for e in view["events"]]
    assert names[0] == "meta" and names[-1] == "done" and "ping" not in names


def test_default_story_includes_covert_monitored(built):
    d = _data(built[0])
    trajs = [s.get("traj") or "" for s in d["story"]]
    assert any("covert_monitored" in t for t in trajs)
    monitored = next(s for s in d["story"] if "covert_monitored" in (s.get("traj") or "") and s["kind"] == "compare")
    v = catalog.compare(catalog.ROOT / monitored["traj"])["verdicts"]
    assert v["full_trace"]["hack_detected"] and v["report_only"]["hack_detected"]


def test_cli_writes_file(tmp_path, capsys):
    out = tmp_path / "sub" / "demo.html"
    assert export.main(["--out", str(out), "--max-gallery", "10"]) == 0
    assert out.exists() and out.stat().st_size < 5_000_000
    assert "wrote" in capsys.readouterr().out

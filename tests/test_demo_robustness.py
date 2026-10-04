"""Robustness cards use saved numbers and keep both reports accessible offline."""

import html
import json
import re
from urllib.parse import unquote

import pytest

from demo import benchmarks


def _write_report(results, suffix="", label="corrected"):
    directory = results / "robustness"
    directory.mkdir(exist_ok=True)
    summary = {
        "label": label,
        "slices": [
            {"auditor": "claude-sonnet-4-6", "mode": "full_trace", "slice": "covert" if not suffix else "covert + covert_monitored",
             "tp": 6, "pos": 10, "recall": 0.6, "recall_ci": [0.3, 0.8]},
            {"auditor": "claude-sonnet-4-6", "mode": "full_trace", "slice": "non-covert",
             "tp": 2, "pos": 5, "recall": 0.4, "recall_ci": [0.1, 0.7]},
        ],
        "ppv": [{"auditor": "claude-sonnet-4-6", "mode": "full_trace", "0.05": 0.16}],
        "role": {"covert": {"mentions": 8, "n": 10}, "honest": {"mentions": 0, "n": 5}},
    }
    markdown = f'# Robustness {suffix or "v2"}\n\nA & B <not markup>.\n'
    (directory / f"robustness{suffix}.json").write_text(json.dumps(summary))
    (directory / f"ROBUSTNESS{suffix}.md").write_text(markdown)
    return summary, markdown


def test_robustness_card_absent_without_results(tmp_path):
    assert benchmarks.robustness(tmp_path) is None


@pytest.mark.parametrize("summary", ["invalid", "[]", "{}"])
def test_robustness_skips_incomplete_summaries(tmp_path, summary):
    directory = tmp_path / "robustness"
    directory.mkdir()
    (directory / "robustness.json").write_text(summary)
    (directory / "ROBUSTNESS.md").write_text("# Incomplete")
    assert benchmarks.robustness(tmp_path) is None


def test_robustness_card_uses_saved_numbers_and_offline_reports(tmp_path):
    _, v2 = _write_report(tmp_path)
    _, v3 = _write_report(tmp_path, "_v3", "labeller")
    data = benchmarks.robustness(tmp_path)
    assert data is not None
    assert [r["version"] for r in data["reports"]] == ["v2", "v3"]
    page = benchmarks.render_robustness(data)
    for text in ("60.0% (6/10)", "40.0% (2/5)", "16.0%", "95% CI 30.0%–80.0%",
                 "8/10", "0/5", "corrected labels", "labeller-only", "no privileged judge", "projected PPV"):
        assert text in page
    links = re.findall(r'href="(data:text/markdown;[^"]+)" download="([^"]+)"', page)
    assert {name: unquote(html.unescape(href).partition(",")[2]) for href, name in links} == {
        "ROBUSTNESS.md": v2, "ROBUSTNESS_v3.md": v3,
    }


def test_robustness_handles_undefined_values(tmp_path):
    summary, _ = _write_report(tmp_path)
    summary["slices"][0].update(tp=0, pos=0, recall=None, recall_ci=[None, None])
    summary["slices"].pop()
    summary["ppv"][0]["0.05"] = None
    summary["role"] = {}
    (tmp_path / "robustness" / "robustness.json").write_text(json.dumps(summary))
    data = benchmarks.robustness(tmp_path)
    assert data is not None
    page = benchmarks.render_robustness(data)
    assert "– (0/0)" in page and "not available" in page


def test_robustness_keeps_the_headline_first(tmp_path):
    _write_report(tmp_path)
    data = benchmarks.robustness(tmp_path)
    headline = {"title": "Headline", "desc": "", "svg": "<svg></svg>", "sources": []}
    page = benchmarks.benchmarks_page({"headline": headline, "robustness": data})
    assert page.index('id="headline"') < page.index('id="robustness"')
    assert 'data-jump="robustness"' in page
    assert "#robustness{scroll-margin-top:80px}" in page


def test_committed_v2_v3_robustness_is_available():
    data = benchmarks.robustness(benchmarks.RESULTS_DIR)
    assert data is not None
    assert {r["version"] for r in data["reports"]} == {"v2", "v3"}
    page = benchmarks.render_robustness(data)
    for report in data["reports"]:
        assert report["source"] in page
        for row in report["summary"]["ppv"]:
            assert f'{100 * row["0.05"]:.1f}%' in page

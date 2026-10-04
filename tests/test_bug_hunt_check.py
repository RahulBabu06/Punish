"""Read-only integrity checks on the before/after result comparator."""

from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.bug_hunt_check import compare, differences, table_cells


def baseline():
    return {"episodes_sha256": "same", "headline_svg_sha256": "same", "metrics": {}, "analysis": {},
            "trajectories": {"cache": {"current_rule": False, "loaded_report": False, "heuristic": {}}}}


def test_comparison_reports_flips_and_recovery_without_mutating_snapshots():
    before = baseline()
    after = deepcopy(before)
    after["trajectories"]["cache"].update(current_rule=True, loaded_report=True)
    original = deepcopy(after)
    report = compare(before, after)
    assert report["label_flips"] == {"cache": {"before": False, "after": True}}
    assert (report["to_hacked"], report["to_clean"]) == (1, 0)
    assert report["recovered_reports"] == ["cache"]
    assert after == original and before == baseline()


def test_comparison_refuses_changed_historical_episode_files():
    after = baseline()
    after["episodes_sha256"] = "changed"
    with pytest.raises(ValueError, match="Historical episode"):
        compare(baseline(), after)


def test_comparison_refuses_different_populations():
    after = baseline()
    after["trajectories"].clear()
    with pytest.raises(ValueError, match="populations differ"):
        compare(baseline(), after)


def test_metric_diff_preserves_zero_versus_undefined():
    assert differences({"f1": None}, {"f1": 0}) == [{"path": "/f1", "before": None, "after": 0}]


def test_markdown_comparison_preserves_displayed_numbers():
    text = "# Report\n| task | F1 |\n|---|---|\n| t | n/a |\n"
    assert table_cells(text) == {"Report/table1/t/F1": "n/a"}
    assert differences(table_cells(text), table_cells(text.replace("n/a", "0.000"))) == [
        {"path": "/Report/table1/t/F1", "before": "n/a", "after": "0.000"}]


def test_committed_primary_summaries_match_frozen_episode_records():
    from eval.metrics import compute_metrics, load_episodes, render_summary

    root = Path(__file__).resolve().parents[1] / "results"
    summaries = [exp / "SUMMARY.md" for exp in root.iterdir()
                 if (exp / "episodes").is_dir() and (exp / "SUMMARY.md").is_file()]
    assert len(summaries) == 10
    for path in summaries:
        expected = render_summary(compute_metrics(load_episodes(str(path.parent / "episodes"))))
        assert path.read_text() == expected, f"Stale summary: {path}"

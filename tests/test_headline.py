"""Corrected-v2 headline figure: source parity and deterministic rendering."""

import json

import pytest

from eval import headline


def read(path):
    return json.loads((headline.ROOT / path).read_text(encoding="utf-8"))


def test_headline_values_match_committed_sources():
    data = headline.load_data()
    corrected = read(headline.CORRECTION)["headline"]["corrected"]
    cascade = read(headline.CASCADE)
    mitigation = read(headline.MITIGATION)
    expected_point = next(row for row in cascade["crossfit"]["0.05"] if row["family"] == "h->sonnet")

    assert data["n"] == corrected["n_trajectories"] == 360
    assert data["positives"] == corrected["positives"] == 93
    assert data["hack_rates"] == corrected["hack_rate_by_config"]
    assert data["auditors"] == corrected["auditor"]
    assert data["cascade"] == expected_point
    assert data["mitigation"] == mitigation["overall"]


def test_expected_headline_operating_points():
    data = headline.load_data()
    rates = data["hack_rates"]
    assert {key: value["hacked"] / value["n"] for key, value in rates.items()} == pytest.approx(
        {"covert": 66 / 90, "honest": 0, "incentivized": 11 / 90, "pressure": 16 / 90})
    assert (data["cascade"]["recall"], data["cascade"]["fpr"]) == pytest.approx((36 / 56, 10 / 184))
    assert (data["mitigation"]["grader_only_hack"], data["mitigation"]["veto_grader_hack"]) == pytest.approx(
        (0.2791666666666667, 0.14583333333333334))


def test_svg_regenerates_deterministically(tmp_path):
    first, second = tmp_path / "first.svg", tmp_path / "second.svg"
    assert headline.main(["--out", str(first)]) == headline.main(["--out", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes() == headline.OUTPUT.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert "corrected label (n=360)" in text
    assert "73.3%" in text and "34.5%" in text and "64.3%" in text and "14.6%" in text
    assert "v3" not in text.lower()

"""Offline guards for showcased paths and one-indexed physical JSONL citations."""

import re
from pathlib import Path

import pytest

from demo.catalog import DEFAULT_STORY

ROOT = Path(__file__).resolve().parents[1]
CASE_STUDIES = (ROOT / "docs" / "case_studies.md").read_text(encoding="utf-8")
PATH_REF = re.compile(r"\bresults/[\w-]+/trajectories/[\w.-]+\.jsonl\b")
RUN_ID_REF = re.compile(r"`([\w-]+)`\s*/\s*`([\w.-]+)`")
LINE_REF = re.compile(r"\[L(-?\d+)(?:\s*[-–]\s*L?(-?\d+))?\]")


def trajectory_refs(text):
    paths = set(PATH_REF.findall(text))
    paths.update(f"results/{run}/trajectories/{stem}.jsonl"
                 for run, stem in RUN_ID_REF.findall(text))
    return paths


def line_refs(text):
    return [(int(start), int(end or start)) for start, end in LINE_REF.findall(text)]


def check_reference(path, citations, root=ROOT):
    target = root / path
    assert target.is_file(), f"Missing showcased trajectory: {path}"
    n_lines = len(target.read_text(encoding="utf-8").splitlines())
    assert n_lines, f"Empty showcased trajectory: {path}"
    for start, end in citations:
        assert 1 <= start <= end <= n_lines, (
            f"{path}: cited L{start}–L{end}, but physical JSONL lines are 1–{n_lines}"
        )


@pytest.mark.parametrize("step", DEFAULT_STORY, ids=lambda step: step["title"])
def test_story_references(step):
    citations = line_refs(step.get("title", "") + " " + step.get("caption", ""))
    if step["kind"] in ("view", "compare"):
        assert step.get("traj"), "Story view has no trajectory"
        check_reference(step["traj"], citations)
    else:
        assert not citations, "Story line citations have no trajectory to resolve against"


@pytest.mark.parametrize("path", sorted(trajectory_refs(CASE_STUDIES)))
def test_every_case_study_trajectory_exists(path):
    check_reference(path, [])


CASE_SECTIONS = re.findall(r"(?ms)^## \d+\. .*?(?=^## |\Z)", CASE_STUDIES)


@pytest.mark.parametrize("section", CASE_SECTIONS, ids=lambda section: section.splitlines()[0])
def test_case_study_line_references(section):
    paths = trajectory_refs(section)
    assert len(paths) == 1, "Each case must unambiguously name its cited trajectory"
    citations = line_refs(section)
    assert citations, "Case study has no physical line citations"
    check_reference(next(iter(paths)), citations)


def test_case_study_inventory_matches_examples():
    assert CASE_SECTIONS, "No case studies found; citation checks would be vacuous"
    assert trajectory_refs(CASE_STUDIES) == set().union(
        *(trajectory_refs(section) for section in CASE_SECTIONS)
    ), "Inventory and case bodies reference different trajectories"


@pytest.mark.parametrize("text,expected", [
    ("[L3]", [(3, 3)]),
    ("[L3-L7]", [(3, 7)]),
    ("[L3–L7]", [(3, 7)]),
    ("[L3-7] and [L9]", [(3, 7), (9, 9)]),
])
def test_citation_parser(text, expected):
    assert line_refs(text) == expected


def test_path_parser():
    text = "`results/probe_v1/trajectories/example.jsonl` and `v2_haiku45` / `other`"
    assert trajectory_refs(text) == {
        "results/probe_v1/trajectories/example.jsonl",
        "results/v2_haiku45/trajectories/other.jsonl",
    }


@pytest.mark.parametrize("citation", [[(0, 1)], [(-1, 1)], [(2, 1)], [(1, 3)]])
def test_invalid_citations_fail(tmp_path, citation):
    (tmp_path / "example.jsonl").write_text('{}\n{}\n', encoding="utf-8")
    with pytest.raises(AssertionError, match="physical JSONL lines"):
        check_reference("example.jsonl", citation, root=tmp_path)


def test_missing_trajectory_fails(tmp_path):
    with pytest.raises(AssertionError, match="Missing showcased trajectory"):
        check_reference("missing.jsonl", [], root=tmp_path)


def test_physical_lines_not_rendered_report_lines(tmp_path):
    (tmp_path / "example.jsonl").write_text('{"content":"first\\nsecond"}\n{}\n', encoding="utf-8")
    check_reference("example.jsonl", [(1, 2)], root=tmp_path)
    with pytest.raises(AssertionError, match="physical JSONL lines"):
        check_reference("example.jsonl", [(3, 3)], root=tmp_path)

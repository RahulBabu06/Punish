"""Relative links, images and #anchors in the submission docs (README, REPORT, PITCH, docs/*.md) resolve."""

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent
MD_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_DEF = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*<?(\S+?)>?(?:\s+\"[^\"]*\")?\s*$")
HTML_REF = re.compile(r"<(?:img|a|source)\b[^>]*?\b(?:src|href)=[\"']([^\"']+)[\"']", re.I)
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r"<a\s+[^>]*\b(?:name|id)=[\"']([^\"']+)[\"']", re.I)
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)


def doc_files() -> list[Path]:
    files = [ROOT / name for name in ("README.md", "REPORT.md", "PITCH.md")]
    return [p for p in files if p.is_file()] + sorted((ROOT / "docs").glob("*.md"))


def _prose_lines(text: str):
    fenced = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            yield n, line


def slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(text: str) -> set[str]:
    out, seen = set(), {}
    for _, line in _prose_lines(text):
        out.update(HTML_ANCHOR.findall(line))
        if m := HEADING.match(line):
            s = slug(m.group(1))
            out.add(f"{s}-{seen[s]}" if s in seen else s)
            seen[s] = seen.get(s, 0) + 1
    return out


def targets(text: str) -> list[tuple[int, str]]:
    """(line, target) of every relative link or image outside code."""
    out = []
    for n, line in _prose_lines(text):
        prose = INLINE_CODE.sub("", line)
        found = MD_LINK.findall(prose) + HTML_REF.findall(prose)
        if m := REF_DEF.match(prose):
            found.append(m.group(1))
        out += [(n, t) for t in found if not EXTERNAL.match(t)]
    return out


def broken(path: Path, root: Path = ROOT) -> list[str]:
    bad, cache = [], {}
    for n, target in targets(path.read_text(encoding="utf-8")):
        file_part, _, frag = target.partition("#")
        dest = (path.parent / unquote(file_part.split("?", 1)[0])) if file_part else path
        where = f"{path.relative_to(root)}:{n}: {target}"
        if not dest.exists():
            bad.append(where + " (no such file)")
        elif frag and dest.suffix == ".md":
            if dest not in cache:
                cache[dest] = anchors(dest.read_text(encoding="utf-8"))
            if unquote(frag).lower() not in cache[dest]:
                bad.append(where + " (no such heading)")
    return bad


def test_slug_matches_github():
    assert slug("8.0 Known issue: stale `leaked_answer` judge context (read first)") == (
        "80-known-issue-stale-leaked_answer-judge-context-read-first"
    )
    assert slug("Reproducing the results") == "reproducing-the-results"


def test_anchors_number_duplicate_headings():
    assert anchors("# A\n## A\n```\n# B\n```\n<a name=\"x\"></a>\n") == {"a", "a-1", "x"}


def test_targets_skip_code_and_external():
    text = (
        "[a](x.md) ![i](f.svg \"t\") <img src=\"g.png\"> [e](https://e.com) `[c](no.md)`\n"
        "```\n[f](no.md)\n```\n[ref]: y.md#s\n[h](#top)"
    )
    assert targets(text) == [(1, "x.md"), (1, "f.svg"), (1, "g.png"), (5, "y.md#s"), (6, "#top")]


def test_broken_reports_missing_file_and_anchor(tmp_path):
    (tmp_path / "b.md").write_text("# Real heading\n", encoding="utf-8")
    doc = tmp_path / "a.md"
    doc.write_text("[ok](b.md#real-heading) [gone](c.md) [bad](b.md#nope) [self](#missing)\n", encoding="utf-8")
    assert broken(doc, tmp_path) == [
        "a.md:1: c.md (no such file)",
        "a.md:1: b.md#nope (no such heading)",
        "a.md:1: #missing (no such heading)",
    ]


@pytest.mark.parametrize("path", doc_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_doc_links_resolve(path):
    assert broken(path) == []

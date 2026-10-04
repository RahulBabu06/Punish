"""Relative links in committed Markdown files point at files that exist."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.I)


def md_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        files = [ROOT / p for p in out.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        files = [p for p in ROOT.rglob("*.md") if ".venv" not in p.parts]
    return sorted(p for p in files if p.is_file())


def relative_links(text: str) -> list[tuple[int, str]]:
    """(line number, target) of relative links outside code fences and inline code."""
    out, fenced = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for m in LINK.finditer(INLINE_CODE.sub("", line)):
            target = m.group(1)
            if not EXTERNAL.match(target):
                out.append((n, target))
    return out


def broken_links(path: Path) -> list[str]:
    bad = []
    for n, target in relative_links(path.read_text(encoding="utf-8")):
        file_part = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if file_part and not (path.parent / file_part).exists():
            bad.append(f"{path.relative_to(ROOT)}:{n}: {target}")
    return bad


def test_relative_links_parse():
    text = "[a](docs/x.md) [b](https://e.com) ![c](fig.svg \"t\") [d](#anchor) `[e](no.md)`\n```\n[f](no.md)\n```\n[g](y.md#s)"
    assert relative_links(text) == [(1, "docs/x.md"), (1, "fig.svg"), (5, "y.md#s")]


@pytest.mark.parametrize("path", md_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_markdown_relative_links_resolve(path):
    assert broken_links(path) == []

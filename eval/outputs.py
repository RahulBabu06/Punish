"""Non-clobbering output paths shared by the offline analysis CLIs.

- Without an explicit output path, a CLI writes next to its input: inside ``<exp>/`` for one experiment, or in
  ``<parent>/combined__<a>+<b>+.../`` for several, never over a committed top-level file such as results/RESULTS.md.
- Label (and mode) variants are tagged into the filename (``CASCADE_corrected.md``), also for explicit paths, unless
  the path already names the tag (``--out results/CASCADE_corrected.md`` is kept as is).
- :func:`guard_inputs` refuses to replace an existing report that was built from a different set of inputs.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

DEFAULT_TAGS = {None, "", "either", "full_trace", "task"}
MAX_NAME = 120


def default_dir(experiments: list[str] | tuple[str, ...]) -> Path:
    """``<exp>`` for one experiment, ``<common parent>/combined__<names>`` for several (order-insensitive)."""
    paths = list(dict.fromkeys(Path(e) for e in experiments))
    if len(paths) == 1:
        return paths[0]
    parents = {p.parent for p in paths}
    parent = parents.pop() if len(parents) == 1 else Path("results")
    names = sorted(p.name for p in paths)
    name = "combined__" + "+".join(names)
    if len(name) > MAX_NAME:
        digest = hashlib.sha256("\n".join(names).encode()).hexdigest()[:8]
        name = f"combined__{names[0]}+{len(names) - 1}more_{digest}"
    return parent / name


def _has_tag(name: str, tag: str) -> bool:
    return re.search(rf"(^|_){re.escape(tag)}(_|$)", name) is not None


def tagged(path: str | Path, *tags: str | None) -> Path:
    """``x/NAME.md`` -> ``x/NAME_<tag>....md`` for each non-default tag not already named by the file (or its dir)."""
    p = Path(path)
    stem = p.stem if p.suffix else p.name
    for tag in tags:
        if tag in DEFAULT_TAGS or _has_tag(stem, tag) or _has_tag(p.parent.name, tag):
            continue
        stem = f"{stem}_{tag}"
    return p.with_name(stem + p.suffix)


def output(explicit: str | None, experiments, name: str, *tags: str | None) -> Path:
    """The path a CLI should write: ``explicit`` or ``default_dir(experiments)/name``, tagged."""
    return tagged(explicit if explicit else default_dir(experiments) / name, *tags)


def _recorded_inputs(path: Path, prefix: str) -> set[str] | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            body = line[len(prefix):].split(". ", 1)[0].rstrip(".")
            return {Path(x.strip().strip("`")).name for x in body.split(",") if x.strip()}
    return None


def guard_inputs(path: str | Path, inputs, prefix: str, force: bool = False) -> str | None:
    """An error message if ``path`` exists and records (on its ``prefix`` line) a different input set."""
    p = Path(path)
    if force or not p.is_file():
        return None
    recorded = _recorded_inputs(p, prefix)
    current = {Path(str(i)).name for i in inputs}
    if recorded is None or recorded == current:
        return None
    return (f"{p} was built from {', '.join(sorted(recorded))}; refusing to replace it with a report on "
            f"{', '.join(sorted(current))} (pick another --out, or pass --force)")

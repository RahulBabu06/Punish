from pathlib import Path
from runpy import run_path

BUILDER = run_path(str(Path(__file__).resolve().parents[1] / "docs" / "build_slides.py"))
CSS, OUT = BUILDER["CSS"], BUILDER["OUT"]


def test_code_pills_override_inherited_dark_slide_colors():
    rule = CSS.split("code,.mono{", 1)[1].split("}", 1)[0]
    assert "background:var(--bg)" in rule
    assert "color:var(--ink)" in rule


def test_committed_slides_match_builder_styles():
    assert f"<style>{CSS}</style>" in OUT.read_text(encoding="utf-8")

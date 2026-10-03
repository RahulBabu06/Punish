"""Pure stdlib SVG output: deterministic, escaped, finite and readable offline."""

import json
import math
import xml.etree.ElementTree as ET

from eval import analyze, figures

SVG_NS = "{http://www.w3.org/2000/svg}"


def rows():
    out = []
    for auditor in ("auditor A", "auditor <B> & C"):
        for mode in analyze.MODES:
            for i, truth in enumerate([True, True, False, False]):
                out.append({"experiment": "synthetic", "trajectory_id": str(i), "task_id": "task",
                            "agent_config": "covert" if i == 0 else "honest", "subject_model": "model <M> & N",
                            "auditor": auditor, "auditor_mode": mode, "pred": truth, "confidence": 0.9 if truth else 0.1,
                            "labeller": truth, "judge": truth, "either": truth,
                            "judge_hack_types": ["fabricated_source"] if truth else [],
                            "hack_types": ["fabricated_source"] if truth else []})
    return out


def test_svg_files_are_deterministic_valid_xml_with_accessible_labels(tmp_path):
    stats = analyze.summarize(rows(), repeats=20)
    paths = figures.write_figures(stats, tmp_path / "nested" / "figures")
    assert {p.name for p in paths} == {"hack_rate_by_model_config.svg", "roc_by_mode.svg",
                                     "recall_by_mode_config.svg", "calibration.svg"}
    original = {path.name: path.read_bytes() for path in paths}
    figures.write_figures(stats, paths[0].parent)
    for path in paths:
        assert original[path.name] == path.read_bytes()
        root = ET.parse(path).getroot()
        assert root.tag == SVG_NS + "svg" and root.attrib["role"] == "img"
        title, desc = root.find(SVG_NS + "title"), root.find(SVG_NS + "desc")
        assert title is not None and title.text
        assert desc is not None and desc.text
        assert not root.findall(".//" + SVG_NS + "script")
        assert "<B>" not in path.read_text()
        for element in root.iter():
            for key in ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "width", "height"):
                if key in element.attrib:
                    assert math.isfinite(float(element.attrib[key]))
            for key in ("width", "height", "r"):
                if key in element.attrib:
                    assert float(element.attrib[key]) >= 0


def test_svg_titles_axes_legends_and_multi_auditor_panels(tmp_path):
    stats = analyze.summarize(rows(), repeats=20)
    paths = {p.stem: ET.parse(p).getroot() for p in figures.write_figures(stats, tmp_path)}
    texts = {name: " ".join(el.text or "" for el in root.iter(SVG_NS + "text")) for name, root in paths.items()}
    assert "model <M> & N" in texts["hack_rate_by_model_config"]
    assert "known-label trajectories" in texts["hack_rate_by_model_config"]
    for name in ("roc_by_mode", "recall_by_mode_config", "calibration"):
        for mode in figures.MODE_LABELS.values():
            assert mode in texts[name]
        assert "Auditor: auditor A" in texts[name] and "Auditor: auditor <B> & C" in texts[name]
    assert "False positive rate" in texts["roc_by_mode"]
    assert "5% FPR" in texts["roc_by_mode"]
    assert "Mean predicted P(hacked)" in texts["calibration"]
    assert "Observed hack frequency" in texts["calibration"]
    assert "subject models are pooled" in texts["recall_by_mode_config"]


def test_svg_degenerate_and_empty_samples_are_explicit(tmp_path):
    clean = [r | {"pred": False, "confidence": 0, "judge": False, "either": False, "labeller": False,
                  "judge_hack_types": [], "hack_types": []} for r in rows()]
    stats = analyze.summarize(clean, repeats=10)
    assert "AUC n/a" in figures.roc_svg(stats)
    assert "n/a" in figures.recall_svg(stats)
    assert stats["hack_rates"][0]["labels"]["either"]["rate"] == 0
    empty = analyze.summarize([], repeats=10)
    for path in figures.write_figures(empty, tmp_path):
        assert "No " in path.read_text()
        ET.parse(path)


def test_standalone_figures_cli(tmp_path, capsys):
    stats = analyze.summarize(rows(), repeats=10)
    source = tmp_path / "analysis.json"
    source.write_text(json.dumps(stats))
    assert figures.main([str(source), "--out", str(tmp_path / "figures")]) == 0
    assert "roc_by_mode.svg" in capsys.readouterr().out
    assert len(list((tmp_path / "figures").glob("*.svg"))) == 4

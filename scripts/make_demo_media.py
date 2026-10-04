#!/usr/bin/env python3
"""Render submission media from the self-contained static demo.

Run after regenerating ``docs/demo.html``::

    uv pip install -p .venv playwright==1.56.0
    .venv/bin/python -m playwright install ffmpeg
    .venv/bin/python scripts/make_demo_media.py

The script launches an installed Chrome/Chromium, makes no network requests,
and writes only to ``docs/media``. It requires system ``ffmpeg``/``ffprobe``.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO = ROOT / "docs" / "demo.html"
DEFAULT_OUT = ROOT / "docs" / "media"
PREFERRED_TRAJECTORY = "results/probe_v1/trajectories/metric_gaming__covert__ep000.jsonl"
WIDTH, HEIGHT = 1280, 720
STILLS = (
    "01-dashboard.png",
    "02-evidence.png",
    "03-mode-comparison.png",
    "04-benchmarks.png",
)


@dataclass(frozen=True)
class Case:
    trajectory: str
    full_confidence: float
    final_confidence: float


def _unpack_json(value: str) -> Any:
    return json.loads(gzip.decompress(base64.b64decode(value)))


def load_demo(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="punish-data">(.*?)</script>', text, re.DOTALL)
    if not match:
        raise ValueError(f"{path} is not a Punish static demo export")
    return json.loads(match.group(1))


def _verdict(data: dict, trajectory: str, mode: str) -> dict | None:
    prefix = f"/view?traj={trajectory}&auditor_mode={mode}&"
    for key, packed in data["views"].items():
        if not key.startswith(prefix):
            continue
        view = _unpack_json(packed)
        lines = _unpack_json(data["lines"][view["traj"]])
        for name, event in view["events"]:
            if name == "@":
                name, event = lines[event]
            if name == "verdict":
                return event["verdict"]
    return None


def choose_case(data: dict) -> Case:
    comparisons = [key.partition("=")[2] for key in data["pages"] if key.startswith("/compare?traj=")]
    ordered = [PREFERRED_TRAJECTORY, *sorted(set(comparisons) - {PREFERRED_TRAJECTORY})]
    for trajectory in ordered:
        if not trajectory.startswith("results/"):
            continue
        full = _verdict(data, trajectory, "full_trace")
        final = _verdict(data, trajectory, "final_report")
        if not full or not final or full.get("hack_detected") is not True or final.get("hack_detected") is not False:
            continue
        if not isinstance(full.get("confidence"), (int, float)) or not isinstance(final.get("confidence"), (int, float)):
            continue
        return Case(trajectory, full["confidence"], final["confidence"])
    raise ValueError("static demo has no real trajectory caught by full_trace and missed by final_report")


def _route(page, route: str, ready: str) -> None:
    page.evaluate("route => { location.hash = '#' + route; }", route)
    target = page.frame_locator("#f").locator(ready).first
    target.wait_for(state="visible", timeout=15_000)


def _caption(page, title: str, subtitle: str, duration: float) -> None:
    page.locator("#media-title").evaluate("(el, text) => { el.textContent = text; }", title)
    page.locator("#media-subtitle").evaluate("(el, text) => { el.textContent = text; }", subtitle)
    page.locator("#media-progress").evaluate(
        """(el, seconds) => {
          el.style.transition = 'none'; el.style.width = '0%'; void el.offsetWidth;
          el.style.transition = `width ${seconds}s linear`; el.style.width = '100%';
        }""",
        duration,
    )


def _install_caption(page) -> None:
    page.evaluate(
        """() => {
          const style = document.createElement('style');
          style.textContent = `
            #f { height: calc(100% - 78px) !important; }
            #media-caption { position:fixed; z-index:10; left:0; right:0; bottom:0; height:78px;
              display:grid; grid-template-columns:330px 1fr; gap:22px; align-items:center; padding:12px 32px;
              background:#0d1119; border-top:1px solid #2b3446; color:#e6ebf5;
              font-family:system-ui,-apple-system,'Segoe UI',sans-serif; box-sizing:border-box; }
            #media-title { color:#ff6170; font-size:14px; font-weight:900; letter-spacing:.09em; }
            #media-subtitle { font-size:18px; font-weight:600; line-height:1.25; }
            #media-progress { position:absolute; left:0; top:-2px; height:3px; width:0;
              background:linear-gradient(90deg,#ff4d5e,#b48cff,#4da3ff); }
          `;
          document.head.append(style);
          const bar = document.createElement('div'); bar.id = 'media-caption';
          bar.innerHTML = '<div id="media-progress"></div><div id="media-title"></div><div id="media-subtitle"></div>';
          document.body.append(bar);
        }"""
    )


def _percent(value: float) -> str:
    return f"{value:.0%}"


def _screenshot(page, directory: Path, name: str) -> None:
    page.screenshot(path=directory / name, type="png")


def record_walkthrough(demo: Path, directory: Path, browser_path: str, case: Case) -> tuple[Path, float]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("install Playwright with: uv pip install -p .venv playwright==1.56.0") from exc

    errors: list[str] = []
    network: list[str] = []
    raw_video: Path | None = None
    gif_start = 0.0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=browser_path,
            headless=True,
            args=["--disable-background-networking", "--force-device-scale-factor=1"],
        )
        try:
            context = browser.new_context(
                viewport={"width": WIDTH, "height": HEIGHT},
                device_scale_factor=1,
                record_video_dir=directory,
                record_video_size={"width": WIDTH, "height": HEIGHT},
            )
            context.route(
                "**/*",
                lambda route: (network.append(route.request.url), route.abort())
                if route.request.url.startswith(("http://", "https://"))
                else route.continue_(),
            )
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            video = page.video
            if video is None:
                raise RuntimeError("Playwright video recording did not start")
            started = time.monotonic()
            page.goto(demo.as_uri() + "#/", wait_until="load")
            page.frame_locator("#f").locator("#gallery").wait_for(state="visible")
            _install_caption(page)

            _caption(
                page,
                "01 / 05  EXPLORE SAVED RUNS",
                "Browse real trajectories, ground-truth labels, and auditor verdicts—fully offline.",
                6,
            )
            page.wait_for_timeout(6_000)

            _route(page, "/dashboard?exp=v2_sonnet46&label=either", ".charts")
            charts = page.frame_locator("#f").locator(".charts")
            charts.evaluate("el => el.scrollIntoView({behavior:'smooth', block:'start'})")
            _caption(
                page,
                "02 / 05  MEASURE RESULTS",
                "Break down hack rates and auditor quality by experiment, configuration, and visibility mode.",
                10,
            )
            page.wait_for_timeout(1_500)
            charts.evaluate("() => window.scrollBy({top:-70, behavior:'smooth'})")
            page.wait_for_timeout(500)
            _screenshot(page, directory, STILLS[0])
            page.wait_for_timeout(8_000)

            query = urlencode(
                {
                    "traj": case.trajectory,
                    "auditor_mode": "full_trace",
                    "progressive": "1",
                    "audit": "file",
                    "delay": "0.65",
                }
            )
            _route(page, f"/view?{query}", "#stream")
            _caption(
                page,
                "03 / 05  WATCH A REAL HACK",
                "Saved metric-gaming run: flags arrive as soon as their supporting trace lines appear.",
                17,
            )
            evidence = page.frame_locator("#f").locator("#ev1")
            evidence.wait_for(state="visible", timeout=15_000)
            evidence.click()
            gif_start = time.monotonic() - started - 0.8
            _screenshot(page, directory, STILLS[1])
            page.frame_locator("#f").locator("#ev3").wait_for(state="attached", timeout=15_000)
            page.wait_for_timeout(5_000)

            _route(page, f"/compare?traj={case.trajectory}", ".vcard")
            _caption(
                page,
                "04 / 05  CHANGE TRACE ACCESS",
                f"Full trace: HACK ({_percent(case.full_confidence)}). Final report: CLEAN ({_percent(case.final_confidence)}).",
                13,
            )
            page.wait_for_timeout(1_500)
            _screenshot(page, directory, STILLS[2])
            page.wait_for_timeout(11_500)

            _route(page, "/benchmarks", "#headline")
            headline = page.frame_locator("#f").locator("#headline")
            headline.evaluate("el => el.scrollIntoView({behavior:'smooth', block:'start'})")
            _caption(
                page,
                "05 / 05  TEST WHAT HOLDS UP",
                "Corrected labels, false-positive rates, held-out results: useful, not solved.",
                18,
            )
            page.wait_for_timeout(1_500)
            _screenshot(page, directory, STILLS[3])
            page.wait_for_timeout(8_500)
            page.frame_locator("#f").locator("#headline svg").evaluate(
                "el => el.scrollIntoView({behavior:'smooth', block:'end'})"
            )
            page.wait_for_timeout(8_000)

            context.close()
            raw_video = Path(video.path())
        finally:
            browser.close()

    if errors:
        raise RuntimeError("browser errors during capture: " + "; ".join(errors))
    if network:
        raise RuntimeError("static walkthrough attempted network access: " + ", ".join(sorted(set(network))))
    if raw_video is None:
        raise RuntimeError("browser did not produce a video")
    return raw_video, max(gif_start, 0)


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _probe(path: Path) -> dict:
    run = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(run.stdout)


def encode(raw: Path, gif_start: float, temporary: Path) -> tuple[Path, Path]:
    mp4 = temporary / "walkthrough.mp4"
    gif = temporary / "walkthrough.gif"
    _run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-vf", "scale=1280:720:flags=lanczos,format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-maxrate", "1100k", "-bufsize", "2200k",
            "-movflags", "+faststart", str(mp4),
        ]
    )
    gif_filter = (
        "fps=8,scale=854:-1:flags=lanczos,split[a][b];"
        "[a]palettegen=max_colors=96:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    _run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{gif_start:.3f}", "-t", "18", "-i", str(mp4),
            "-filter_complex", gif_filter, "-loop", "0", str(gif),
        ]
    )
    return mp4, gif


def validate(mp4: Path, gif: Path, stills: list[Path]) -> None:
    mp4_info, gif_info = _probe(mp4), _probe(gif)
    video = next(stream for stream in mp4_info["streams"] if stream["codec_type"] == "video")
    duration = float(mp4_info["format"]["duration"])
    gif_duration = float(gif_info["format"]["duration"])
    problems = []
    if (video["codec_name"], int(video["width"]), int(video["height"])) != ("h264", WIDTH, HEIGHT):
        problems.append("MP4 must be H.264 at 1280x720")
    if not 60 <= duration <= 90:
        problems.append(f"MP4 duration is {duration:.1f}s, expected 60–90s")
    if mp4.stat().st_size >= 8_000_000:
        problems.append(f"MP4 is {mp4.stat().st_size / 1_000_000:.2f} MB, expected under 8 MB")
    if not 15 <= gif_duration <= 20:
        problems.append(f"GIF duration is {gif_duration:.1f}s, expected 15–20s")
    if gif.stat().st_size >= 5_000_000:
        problems.append(f"GIF is {gif.stat().st_size / 1_000_000:.2f} MB, expected under 5 MB")
    if len(stills) != 4 or any(not path.is_file() for path in stills):
        problems.append("exactly four PNG stills are required")
    if problems:
        raise RuntimeError("; ".join(problems))


def find_browser(explicit: str | None) -> str:
    if explicit:
        return explicit
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if path := shutil.which(name):
            return path
    raise RuntimeError("Chrome/Chromium not found; pass --browser /path/to/chrome")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, default=DEFAULT_DEMO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--browser", help="Chrome/Chromium executable (auto-detected by default)")
    args = parser.parse_args(argv)

    for executable in ("ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            parser.error(f"{executable} is required")
    demo, output = args.demo.resolve(), args.out.resolve()
    data = load_demo(demo)
    case = choose_case(data)
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="punish-demo-media-") as temp_name:
        temporary = Path(temp_name)
        raw, gif_start = record_walkthrough(demo, temporary, find_browser(args.browser), case)
        mp4, gif = encode(raw, gif_start, temporary)
        stills = [temporary / name for name in STILLS]
        validate(mp4, gif, stills)
        for source in (mp4, gif, *stills):
            shutil.copy2(source, output / source.name)

    sizes = ", ".join(f"{path.name}={path.stat().st_size / 1_000_000:.2f} MB" for path in sorted(output.iterdir()))
    print(f"Rendered {case.trajectory}: {sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

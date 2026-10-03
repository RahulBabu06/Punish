"""Export the offline demo: static HTML snapshots of the pitch pages plus a runnable source bundle.

    python scripts/export_demo.py [--out dist/demo]

Writes ``index.html`` (gallery), ``dashboard.html``, ``compare/<trajectory>.html`` for the story's comparison
steps, ``story.html`` and the matching ``api/*.json`` data, all rendered by ``demo.app`` from the committed
results. The trajectory replay (``/view``) streams over SSE, so it needs the server; ``punish-demo.tar.gz`` is
``git archive HEAD`` (code + fixtures + results, stdlib-only demo): unpack it and run ``python3 -m demo.app``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.app import AppConfig, make_server  # noqa: E402
from demo.catalog import load_story  # noqa: E402
from demo.pages import url  # noqa: E402


def _slug(traj: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(traj).parent.parent.name + "__" + Path(traj).stem)


def export(out: Path, bundle: bool = True) -> list[Path]:
    server = make_server(AppConfig(), "127.0.0.1", 0)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    compares = [s["traj"] for s in load_story(None) if s["kind"] == "compare"]
    pages = {"/": "index.html", "/dashboard": "dashboard.html", "/story": "story.html",
             **{url("/compare", traj=t): f"compare/{_slug(t)}.html" for t in compares}}
    apis = {"/api/gallery": "api/gallery.json", "/api/dashboard": "api/dashboard.json",
            "/api/story": "api/story.json"}

    def localize(body: str, name: str) -> str:
        prefix = "../" * name.count("/")

        def sub(m: re.Match) -> str:
            target = pages.get(m.group(1).replace("&amp;", "&"))
            return f'href="{prefix}{target}"' if target else m.group(0)

        return re.sub(r'href="([^"]*)"', sub, body)

    written = []
    try:
        for route, name in {**pages, **apis}.items():
            with urlopen(base + route, timeout=300) as resp:
                body = resp.read().decode("utf-8")
            path = out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith(".html"):
                body = localize(body, name)
            else:
                body = json.dumps(json.loads(body), indent=1)
            path.write_text(body, encoding="utf-8")
            written.append(path)
    finally:
        server.shutdown()
        server.server_close()
    if bundle:
        tar = out / "punish-demo.tar.gz"
        subprocess.run(["git", "archive", "--format=tar.gz", "--prefix=punish/", "-o", str(tar), "HEAD"],
                       cwd=ROOT, check=True)
        written.append(tar)
    readme = out / "README.txt"
    readme.write_text(
        "Static snapshots of the Punish demo (open index.html or dashboard.html in a browser).\n"
        "Replay / live links need the server: tar xzf punish-demo.tar.gz && cd punish && "
        "python3 -m demo.app --story --open\n", encoding="utf-8")
    return [*written, readme]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=str(ROOT / "dist" / "demo"))
    p.add_argument("--no-bundle", action="store_true", help="skip the git-archive source bundle")
    args = p.parse_args(argv)
    for path in export(Path(args.out), bundle=not args.no_bundle):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

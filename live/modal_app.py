"""Hosted demo on Modal: the full demo UI plus ``/live`` runs audited by the open-weight model.

    modal deploy live/vllm_server.py   # GPU model server (once)
    modal deploy live/modal_app.py     # prints https://<workspace>--punish-demo-web.modal.run

Secrets: ``punish-vllm`` (``PUNISH_VLLM_API_KEY``) and, optionally, ``anthropic`` (``ANTHROPIC_API_KEY``) to offer
Claude as the live subject. ``PUNISH_VLLM_URL`` defaults to this workspace's ``punish-vllm`` endpoint.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "/root/punish"
VLLM_URL = os.environ.get("PUNISH_VLLM_URL", "")

app = modal.App("punish-demo")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("anthropic>=0.40", "numpy", "scipy")
    .env({"PUNISH_VLLM_URL": VLLM_URL, "PYTHONPATH": REMOTE})
    .add_local_dir(ROOT, REMOTE, ignore=[".git", ".venv", "results/live", "**/__pycache__", "paper", "docs/media", "*.pdf",
                                         ".pytest_cache", ".ruff_cache"])
)
secrets = [modal.Secret.from_name("punish-vllm")]
if os.environ.get("PUNISH_DEMO_CLAUDE"):
    secrets.append(modal.Secret.from_name("anthropic"))


@app.function(image=image, secrets=secrets, timeout=24 * 60 * 60, scaledown_window=30 * 60,
              min_containers=int(os.environ.get("PUNISH_DEMO_MIN_CONTAINERS", "0")), max_containers=1, cpu=2.0, memory=4096)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=8000, startup_timeout=120)
def web():
    subprocess.Popen(["python", "-m", "demo.app", "--host", "0.0.0.0", "--port", "8000", "--live-runs"], cwd=REMOTE)

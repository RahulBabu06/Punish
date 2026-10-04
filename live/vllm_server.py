"""Open-weight model server on Modal: vLLM's OpenAI-compatible API for Qwen3 (reasoning + tool calls).

    modal deploy live/vllm_server.py     # prints https://<workspace>--punish-vllm-serve.modal.run

Requests need ``Authorization: Bearer $PUNISH_VLLM_API_KEY`` (Modal secret ``punish-vllm``).
"""

from __future__ import annotations

import os
import subprocess

import modal

MODEL = os.environ.get("PUNISH_OPEN_MODEL", "Qwen/Qwen3-30B-A3B")
GPU = os.environ.get("PUNISH_OPEN_GPU", "H100")
PORT = 8000
MAX_MODEL_LEN = 40960

app = modal.App("punish-vllm")
image = (
    modal.Image.from_registry("nvidia/cuda:12.8.1-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.10.1.1", "huggingface_hub[hf_transfer]==0.34.4")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "VLLM_USE_V1": "1"})
)
hf_cache = modal.Volume.from_name("punish-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("punish-vllm-cache", create_if_missing=True)


@app.function(
    image=image,
    gpu=GPU,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_name("punish-vllm")],
    timeout=24 * 60 * 60,
    scaledown_window=20 * 60,
    min_containers=int(os.environ.get("PUNISH_OPEN_MIN_CONTAINERS", "0")),
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=PORT, startup_timeout=30 * 60)
def serve():
    cmd = [
        "vllm", "serve", MODEL,
        "--served-model-name", MODEL, "--host", "0.0.0.0", "--port", str(PORT),
        "--max-model-len", str(MAX_MODEL_LEN), "--gpu-memory-utilization", "0.92",
        "--enable-auto-tool-choice", "--tool-call-parser", "hermes", "--reasoning-parser", "qwen3",
    ]
    subprocess.Popen(cmd, env={**os.environ, "VLLM_API_KEY": os.environ["PUNISH_VLLM_API_KEY"]})

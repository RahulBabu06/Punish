"""Anthropic-``messages.create``-compatible client over an OpenAI-compatible chat API (vLLM on Modal).

Lets the unchanged subject-agent loop (``agent.runner``) and Claude auditor (``auditor.audit``) drive an
open-weight model: Anthropic content blocks are translated to OpenAI messages and back, and the model's
``reasoning_content`` becomes a ``thinking`` block, so private reasoning lands in the trajectory's
``reasoning`` field exactly as Claude's extended thinking does. Stdlib only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_OPEN_MODEL = "Qwen/Qwen3-30B-A3B"
_DROPPED = ("thinking", "extra_headers", "metadata", "temperature_override")


class OpenModelError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts)


def to_openai_messages(system, messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    if system:
        out.append({"role": "system", "content": _text_of(system)})
    for msg in messages:
        role, content = msg["role"], msg.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        blocks = [b for b in content or [] if isinstance(b, dict)]
        if role == "assistant":
            text = "\n\n".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
            calls = [{"id": b["id"], "type": "function",
                      "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {})}}
                     for b in blocks if b.get("type") == "tool_use"]
            item = {"role": "assistant", "content": text or ("" if calls else "(no output)")}
            if calls:
                item["tool_calls"] = calls
            out.append(item)
            continue
        texts = []
        for b in blocks:
            if b.get("type") == "tool_result":
                body = b.get("content")
                body = body if isinstance(body, str) else _text_of(body)
                out.append({"role": "tool", "tool_call_id": b.get("tool_use_id"),
                            "content": ("[error] " if b.get("is_error") else "") + (body or "(no output)")})
            elif b.get("type") == "text":
                texts.append(b.get("text") or "")
        if texts:
            out.append({"role": role, "content": "\n\n".join(texts)})
    return out


def to_openai_tools(tools) -> list[dict]:
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                              "parameters": t.get("input_schema") or {"type": "object"}}}
            for t in tools or []]


def to_openai_tool_choice(choice):
    if not choice:
        return None
    kind = choice.get("type")
    if kind == "tool":
        return {"type": "function", "function": {"name": choice["name"]}}
    if kind == "any":
        return "required"
    if kind == "none":
        return "none"
    return "auto"


def from_openai_response(data: dict) -> dict:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    blocks: list[dict] = []
    reasoning = msg.get("reasoning_content") or msg.get("reasoning")
    if reasoning:
        blocks.append({"type": "thinking", "thinking": reasoning.strip(), "signature": ""})
    if (msg.get("content") or "").strip():
        blocks.append({"type": "text", "text": msg["content"].strip()})
    for call in msg.get("tool_calls") or []:
        fn = call.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        blocks.append({"type": "tool_use", "id": call.get("id") or f"call_{len(blocks)}", "name": fn.get("name"),
                       "input": args if isinstance(args, dict) else {}})
    usage = data.get("usage") or {}
    return {
        "id": data.get("id"),
        "model": data.get("model"),
        "role": "assistant",
        "content": blocks,
        "stop_reason": "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn",
        "usage": {"input_tokens": int(usage.get("prompt_tokens") or 0), "output_tokens": int(usage.get("completion_tokens") or 0)},
    }


class _Messages:
    def __init__(self, client: "OpenModelClient"):
        self._client = client

    def create(self, *, model: str, max_tokens: int, messages: list[dict], system=None, tools=None,
               tool_choice=None, **kwargs) -> dict:
        for key in _DROPPED:
            kwargs.pop(key, None)
        body = {"model": model or self._client.model, "messages": to_openai_messages(system, messages),
                "max_tokens": min(int(max_tokens), self._client.max_tokens)}
        if tools:
            body["tools"] = to_openai_tools(tools)
            choice = to_openai_tool_choice(tool_choice)
            if choice is not None:
                body["tool_choice"] = choice
        if "temperature" in kwargs:
            body["temperature"] = kwargs.pop("temperature")
        return from_openai_response(self._client.post("/chat/completions", body))


class OpenModelClient:
    """``client.messages.create(...)`` against ``$PUNISH_VLLM_URL`` (``.../v1``) with ``$PUNISH_VLLM_API_KEY``."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None,
                 max_tokens: int | None = None, timeout: float = 900.0, attempts: int = 4):
        base_url = base_url or os.environ.get("PUNISH_VLLM_URL")
        if not base_url:
            raise OpenModelError("PUNISH_VLLM_URL is not set (deploy live/vllm_server.py and export its URL)")
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url += "/v1"
        self.api_key = api_key if api_key is not None else os.environ.get("PUNISH_VLLM_API_KEY", "")
        self.model = model or os.environ.get("PUNISH_OPEN_MODEL") or DEFAULT_OPEN_MODEL
        self.max_tokens = int(max_tokens or os.environ.get("PUNISH_OPEN_MAX_TOKENS") or 8192)
        self.timeout, self.attempts = timeout, attempts
        self.messages = _Messages(self)

    def post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        for attempt in range(1, self.attempts + 1):
            req = urllib.request.Request(self.base_url + path, data=data, method="POST", headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:500]
                if exc.code < 500 and exc.code not in (408, 429) or attempt == self.attempts:
                    raise OpenModelError(f"open model HTTP {exc.code}: {detail}", exc.code) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt == self.attempts:
                    raise OpenModelError(f"open model unreachable: {exc}") from None
            time.sleep(min(30, 3 * 2 ** (attempt - 1)))
        raise AssertionError("unreachable")

    def health(self) -> bool:
        req = urllib.request.Request(self.base_url + "/models", headers={"Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

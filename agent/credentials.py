"""Fail fast, with a clear message, when a live command has no Anthropic credentials."""

from __future__ import annotations

import os
import sys

ENV_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def has_anthropic_credentials() -> bool:
    return any(os.environ.get(name) for name in ENV_VARS)


def require_anthropic(command: str, offline_hint: str = "") -> None:
    """Exit with status 2 and a one-line explanation (no traceback) when no key is set."""
    if has_anthropic_credentials():
        return
    msg = f"error: {command} calls the Anthropic API, but ANTHROPIC_API_KEY is not set. Export it and retry."
    if offline_hint:
        msg += f" Offline alternative: {offline_hint}"
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def anthropic_client(command: str, offline_hint: str = ""):
    """``anthropic.Anthropic()``, after :func:`require_anthropic`."""
    require_anthropic(command, offline_hint)
    import anthropic

    return anthropic.Anthropic()

"""Tiny stdlib-only client for the BharatCode model API.

BharatCode exposes an OpenAI-compatible Chat Completions endpoint at
``https://bharatcode.ai/api/model/v1/chat/completions``. We deliberately
avoid the ``openai`` SDK so the package stays installable with no extra
dependencies beyond ``forge-foundation``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


DEFAULT_BASE_URL = "https://bharatcode.ai/api/model/v1"
DEFAULT_MODEL = "qwen-3.8-27b"


class BharatCodeHTTPError(Exception):
    """Raised when the BharatCode API returns a non-2xx response."""


def resolve_api_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.environ.get("BHARATCODE_API_KEY", "").strip()
    if not key:
        raise BharatCodeHTTPError(
            "BHARATCODE_API_KEY is not set. Get a key at "
            "https://bharatcode.ai/account and export it as "
            "BHARATCODE_API_KEY.")
    return key


def resolve_base_url(explicit: Optional[str] = None) -> str:
    return (explicit or os.environ.get("BHARATCODE_BASE_URL", "")).strip() \
        or DEFAULT_BASE_URL


def resolve_model(explicit: Optional[str] = None) -> str:
    return (explicit or os.environ.get("BHARATCODE_MODEL", "")).strip() \
        or DEFAULT_MODEL


def chat_completion(
    messages: List[Dict[str, str]],
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
    timeout: float = 120.0,
) -> str:
    """Send a chat/completions request and return the assistant text."""
    key = resolve_api_key(api_key)
    url = resolve_base_url(base_url).rstrip("/") + "/chat/completions"
    mdl = resolve_model(model)

    payload: Dict[str, Any] = {
        "model": mdl,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise BharatCodeHTTPError(
            f"BharatCode API HTTP {e.code}: {body or e.reason}") from e
    except urllib.error.URLError as e:
        raise BharatCodeHTTPError(f"BharatCode API unreachable: {e.reason}") \
            from e

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BharatCodeHTTPError(f"invalid JSON from API: {e}") from e

    try:
        return obj["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise BharatCodeHTTPError(f"unexpected API response shape: {obj}") \
            from e

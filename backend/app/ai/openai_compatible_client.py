from __future__ import annotations

import httpx

from .provider import AIResponse


def _require_ascii(name: str, value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{name} is required")
    # HTTP headers are ASCII-only; non-ASCII characters in keys (e.g. long dash “—”)
    # lead to UnicodeEncodeError deep inside httpx.
    try:
        v.encode("ascii")
    except UnicodeEncodeError as e:
        raise ValueError(
            f"{name} must contain only ASCII characters. Re-paste the value (avoid long dashes/quotes)."
        ) from e
    if any(ch.isspace() for ch in v):
        raise ValueError(f"{name} must not contain whitespace")
    return v


async def run_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout_seconds: int = 60,
) -> AIResponse:
    base_url = _require_ascii("base_url", base_url)
    api_key = _require_ascii("api_key", api_key)
    model = _require_ascii("model", model)

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        content = str(content)
    return AIResponse(text=content)

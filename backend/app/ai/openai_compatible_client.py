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
    # OpenRouter recommends providing these headers; some deployments enforce them.
    if "openrouter.ai" in base_url:
        headers.setdefault("HTTP-Referer", "http://localhost")
        headers.setdefault("X-Title", "doc_gen")
    def build_payload(*, include_system: bool) -> dict:
        if include_system:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        else:
            merged = (system or "").strip()
            if merged:
                merged = merged + "\n\n---\n\n" + (user or "")
            else:
                merged = user or ""
            messages = [{"role": "user", "content": merged}]

        return {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }

    payload = build_payload(include_system=True)

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        def truncate(text: str, limit: int) -> str:
            t = (text or "").strip()
            return t if len(t) <= limit else t[:limit] + "…"

        def is_system_instruction_rejected(response: httpx.Response) -> bool:
            # Some models/providers (e.g. Google AI Studio via OpenRouter) reject system/developer instructions.
            # Detect and retry by folding system prompt into the user message.
            try:
                data = response.json() or {}
            except Exception:
                return False
            err = data.get("error") if isinstance(data, dict) else None
            if not isinstance(err, dict):
                return False
            msg = err.get("message")
            if isinstance(msg, str) and "developer instruction" in msg.lower():
                return True
            meta = err.get("metadata")
            if isinstance(meta, dict):
                raw = meta.get("raw")
                if isinstance(raw, str) and "developer instruction" in raw.lower():
                    return True
            return False

        async def do_post(payload_to_send: dict) -> httpx.Response:
            try:
                return await client.post(url, json=payload_to_send, headers=headers)
            except httpx.RequestError as e:
                raise RuntimeError(f"upstream request error: {e}") from e

        resp = await do_post(payload)

        if resp.status_code >= 400 and resp.status_code == 400 and is_system_instruction_rejected(resp):
            # One retry without system message.
            resp = await do_post(build_payload(include_system=False))

        if resp.status_code >= 400:
            body = truncate(resp.text, 1000)
            raise RuntimeError(
                f"upstream returned HTTP {resp.status_code}: {body}" if body else f"upstream returned HTTP {resp.status_code}"
            )

        try:
            data = resp.json()
        except Exception as e:
            snippet = truncate(resp.text, 300)
            raise RuntimeError(f"upstream returned invalid JSON: {snippet}") from e

    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        content = str(content)
    return AIResponse(text=content)

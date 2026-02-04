from __future__ import annotations

import httpx

from ..settings import settings
from .provider import AIProvider, AIResponse


class OpenAICompatibleProvider(AIProvider):
    async def run(self, *, system: str, user: str) -> AIResponse:
        if not settings.openai_base_url or not settings.openai_api_key or not settings.openai_model:
            raise RuntimeError("OpenAI-compatible provider is not fully configured")

        url = settings.openai_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        payload = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            content = str(content)
        return AIResponse(text=content)

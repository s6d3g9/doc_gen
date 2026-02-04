from __future__ import annotations

from .provider import AIProvider, AIResponse


class NoneProvider(AIProvider):
    async def run(self, *, system: str, user: str) -> AIResponse:
        return AIResponse(
            text=(
                "MODEL_PROVIDER=none: AI is disabled. "
                "Configure backend/.env (MODEL_PROVIDER=openai-compatible) to enable.\n\n"
                f"SYSTEM: {system}\n\nUSER: {user}"
            )
        )

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AIResponse:
    text: str


class AIProvider:
    async def run(self, *, system: str, user: str) -> AIResponse:
        raise NotImplementedError

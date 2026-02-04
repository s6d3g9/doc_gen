from __future__ import annotations

from ..settings import settings
from .none import NoneProvider
from .openai_compatible import OpenAICompatibleProvider
from .provider import AIProvider


def get_provider() -> AIProvider:
    provider = (settings.model_provider or "none").strip().lower()
    if provider in {"none", "disabled"}:
        return NoneProvider()
    if provider in {"openai-compatible", "openai_compatible"}:
        return OpenAICompatibleProvider()
    raise ValueError(f"Unknown MODEL_PROVIDER: {settings.model_provider}")

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from .settings import settings


def ensure_artifacts_dir() -> Path:
    base = Path(settings.artifacts_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base


def write_bytes(data: bytes, *, suffix: str) -> str:
    base = ensure_artifacts_dir()
    name = f"{uuid4().hex}{suffix}"
    path = base / name
    # Best-effort: avoid following symlinks outside the artifacts dir.
    # (Pathlib doesn't have O_NOFOLLOW; keep it simple for now.)
    path.write_bytes(data)
    return str(path)


def write_text(text: str, *, suffix: str = ".txt", encoding: str = "utf-8") -> str:
    base = ensure_artifacts_dir()
    name = f"{uuid4().hex}{suffix}"
    path = base / name
    path.write_text(text, encoding=encoding)
    return str(path)

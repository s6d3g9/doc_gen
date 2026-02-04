from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from .settings import settings


def resolve_artifact_path(artifact_path: str) -> Path:
    """Resolve an artifact path safely inside ARTIFACTS_DIR.

    Artifacts are expected to be stored under settings.artifacts_dir.
    This prevents serving arbitrary files when a DB row contains an unsafe path.
    """

    base = Path(settings.artifacts_dir).resolve()
    p = Path(artifact_path)

    if not p.is_absolute():
        p = base / p

    try:
        resolved = p.resolve()
    except FileNotFoundError:
        resolved = p.absolute()

    if resolved != base and base not in resolved.parents:
        raise HTTPException(status_code=400, detail="Invalid artifact path")

    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return resolved


def try_unlink_artifact(artifact_path: str) -> bool:
    """Best-effort delete of an artifact file inside ARTIFACTS_DIR.

    Returns True if a file was deleted, False otherwise.
    """

    base = Path(settings.artifacts_dir).resolve()
    p = Path(artifact_path)

    if not p.is_absolute():
        p = base / p

    resolved = p.resolve(strict=False)

    if resolved != base and base not in resolved.parents:
        # Do not delete anything outside artifacts dir.
        return False

    if resolved.exists() and resolved.is_file():
        resolved.unlink(missing_ok=True)
        return True

    return False

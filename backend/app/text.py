from __future__ import annotations

from .models import DocumentVersion


def read_version_text(version: DocumentVersion) -> str:
    # Minimal: for text files we read directly; for docx/pdf we leave placeholder.
    # Full FreshDoc/Doczilla-like behavior would parse and preserve formatting.
    if version.content_type.startswith("text/"):
        try:
            with open(version.artifact_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return "(failed to read text artifact)"
    return f"(binary artifact at {version.artifact_path}; content_type={version.content_type})"

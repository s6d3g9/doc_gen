from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import delete, select

from ..artifacts import write_bytes, write_text
from ..db import get_session
from ..deps import get_current_user
from ..models import Document, DocumentType, DocumentTypeAssignment, DocumentVersion
from ..files import resolve_artifact_path, try_unlink_artifact

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentCreateResponse(BaseModel):
    document: Document
    version: DocumentVersion


class DocumentIndexItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    type_id: str | None = None
    latest_version_id: str | None = None
    latest_version_created_at: datetime | None = None
    latest_version_content_type: str | None = None


class DocumentTypeSetRequest(BaseModel):
    type_id: str | None = None


class VersionsPurgeRequest(BaseModel):
    keep_latest: int = 1
    delete_artifacts: bool = True


@router.get("")
def list_documents(user=Depends(get_current_user)) -> list[Document]:
    with get_session() as session:
        return list(
            session.exec(
                select(Document)
                .where(Document.owner_user_id == user.id)
                .order_by(Document.created_at.desc())
            ).all()
        )


@router.get("/index")
def list_documents_index(user=Depends(get_current_user)) -> list[DocumentIndexItem]:
    """Document list optimized for UI: includes latest version info."""

    with get_session() as session:
        docs = list(
            session.exec(
                select(Document)
                .where(Document.owner_user_id == user.id)
                .order_by(Document.created_at.desc())
            ).all()
        )
        out: list[DocumentIndexItem] = []
        for d in docs:
            a = session.exec(
                select(DocumentTypeAssignment)
                .where(DocumentTypeAssignment.document_id == d.id)
                .limit(1)
            ).first()
            v = session.exec(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == d.id)
                .order_by(DocumentVersion.created_at.desc())
                .limit(1)
            ).first()
            out.append(
                DocumentIndexItem(
                    id=d.id,
                    title=d.title,
                    created_at=d.created_at,
                    type_id=a.type_id if a else None,
                    latest_version_id=v.id if v else None,
                    latest_version_created_at=v.created_at if v else None,
                    latest_version_content_type=v.content_type if v else None,
                )
            )
        return out


@router.get("/{document_id}")
def get_document(document_id: str, user=Depends(get_current_user)) -> Document:
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc


@router.put("/{document_id}/type")
def set_document_type(document_id: str, req: DocumentTypeSetRequest, user=Depends(get_current_user)) -> dict[str, str | None]:
    """Set or unset a document's type.

    Stored as a separate assignment row to avoid altering the existing Document table schema.
    """

    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Document not found")

        if req.type_id is not None:
            t = session.get(DocumentType, req.type_id)
            if not t:
                raise HTTPException(status_code=404, detail="Document type not found")

        session.exec(delete(DocumentTypeAssignment).where(DocumentTypeAssignment.document_id == document_id))
        if req.type_id is not None:
            session.add(DocumentTypeAssignment(document_id=document_id, type_id=req.type_id))
        session.commit()

        return {"document_id": document_id, "type_id": req.type_id}


@router.get("/{document_id}/versions")
def list_versions(document_id: str, user=Depends(get_current_user)) -> list[DocumentVersion]:
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Document not found")
        return list(
            session.exec(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.created_at.desc())
            ).all()
        )


@router.post("/{document_id}/versions/purge")
def purge_old_versions(document_id: str, req: VersionsPurgeRequest, user=Depends(get_current_user)) -> dict[str, int]:
    """Delete old versions for a document, keeping only the N latest.

    This is destructive.
    """

    keep_latest = int(req.keep_latest or 0)
    if keep_latest < 1:
        raise HTTPException(status_code=400, detail="keep_latest must be >= 1")

    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Document not found")

        versions = list(
            session.exec(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.created_at.desc())
            ).all()
        )

        to_keep = versions[:keep_latest]
        to_delete = versions[keep_latest:]

        deleted_rows = 0
        deleted_files = 0
        for v in to_delete:
            if req.delete_artifacts and v.artifact_path:
                if try_unlink_artifact(v.artifact_path):
                    deleted_files += 1
            session.exec(delete(DocumentVersion).where(DocumentVersion.id == v.id))
            deleted_rows += 1

        session.commit()

        return {
            "kept": len(to_keep),
            "deleted_versions": deleted_rows,
            "deleted_artifacts": deleted_files,
        }


@router.post("")
def create_document(
    title: str = Form(...),
    type_id: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    user=Depends(get_current_user),
) -> DocumentCreateResponse:
    if file is None and not text:
        raise HTTPException(status_code=400, detail="Provide either file or text")

    if file is not None:
        content = file.file.read()
        artifact_path = write_bytes(content, suffix=_suffix_for_content_type(file.content_type))
        content_type = file.content_type or "application/octet-stream"
    else:
        artifact_path = write_text(text or "", suffix=".txt")
        content_type = "text/plain"

    doc = Document(title=title, owner_user_id=user.id)
    version = DocumentVersion(document_id=doc.id, artifact_path=artifact_path, content_type=content_type)

    with get_session() as session:
        if type_id is not None:
            t = session.get(DocumentType, type_id)
            if not t:
                raise HTTPException(status_code=404, detail="Document type not found")
        session.add(doc)
        session.add(version)
        if type_id is not None:
            session.add(DocumentTypeAssignment(document_id=doc.id, type_id=type_id))
        session.commit()
        session.refresh(doc)
        session.refresh(version)
        return DocumentCreateResponse(document=doc, version=version)


@router.post("/{document_id}/versions")
def add_version(
    document_id: str,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    user=Depends(get_current_user),
) -> DocumentVersion:
    if file is None and not text:
        raise HTTPException(status_code=400, detail="Provide either file or text")

    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Document not found")

        if file is not None:
            content = file.file.read()
            artifact_path = write_bytes(content, suffix=_suffix_for_content_type(file.content_type))
            content_type = file.content_type or "application/octet-stream"
        else:
            artifact_path = write_text(text or "", suffix=".txt")
            content_type = "text/plain"

        version = DocumentVersion(document_id=document_id, artifact_path=artifact_path, content_type=content_type)
        session.add(version)
        session.commit()
        session.refresh(version)
        return version


@router.get("/versions/{version_id}")
def get_version(version_id: str, user=Depends(get_current_user)) -> DocumentVersion:
    with get_session() as session:
        v = session.exec(
            select(DocumentVersion)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(DocumentVersion.id == version_id)
            .where(Document.owner_user_id == user.id)
            .limit(1)
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail="Version not found")
        return v


@router.get("/versions/{version_id}/artifact")
def download_version_artifact(version_id: str, user=Depends(get_current_user)) -> FileResponse:
    """Download an artifact safely by version id."""

    with get_session() as session:
        v = session.exec(
            select(DocumentVersion)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(DocumentVersion.id == version_id)
            .where(Document.owner_user_id == user.id)
            .limit(1)
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail="Version not found")

    path = resolve_artifact_path(v.artifact_path)
    return FileResponse(path=str(path), media_type=v.content_type, filename=path.name)


def _suffix_for_content_type(content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "text/plain" in ct:
        return ".txt"
    if "application/pdf" in ct:
        return ".pdf"
    if "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ct:
        return ".docx"
    if "application/msword" in ct:
        return ".doc"
    return ".bin"

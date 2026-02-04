from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..db import get_session
from ..models import DocumentType

router = APIRouter(prefix="/document-types", tags=["document-types"])


class DocumentTypeCreateRequest(BaseModel):
    key: str
    title: str
    description: str | None = None


class DocumentTypeUpdateRequest(BaseModel):
    key: str | None = None
    title: str | None = None
    description: str | None = None


class DocumentTypeBulkUpsertResponse(BaseModel):
    created: list[DocumentType]
    existing: list[DocumentType]


@router.get("")
def list_document_types() -> list[DocumentType]:
    with get_session() as session:
        return list(session.exec(select(DocumentType).order_by(DocumentType.title.asc())).all())


@router.post("")
def create_document_type(req: DocumentTypeCreateRequest) -> DocumentType:
    key = req.key.strip()
    title = req.title.strip()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    dt = DocumentType(key=key, title=title, description=req.description)
    with get_session() as session:
        existing = session.exec(select(DocumentType).where(DocumentType.key == key).limit(1)).first()
        if existing:
            raise HTTPException(status_code=409, detail="Document type with this key already exists")
        session.add(dt)
        session.commit()
        session.refresh(dt)
        return dt


@router.post("/bulk")
def bulk_upsert_document_types(req: list[DocumentTypeCreateRequest]) -> DocumentTypeBulkUpsertResponse:
    created: list[DocumentType] = []
    existing: list[DocumentType] = []

    with get_session() as session:
        for item in req:
            key = (item.key or "").strip()
            title = (item.title or "").strip()
            if not key or not title:
                continue

            found = session.exec(select(DocumentType).where(DocumentType.key == key).limit(1)).first()
            if found:
                existing.append(found)
                continue

            dt = DocumentType(key=key, title=title, description=item.description)
            session.add(dt)
            session.commit()
            session.refresh(dt)
            created.append(dt)

    return DocumentTypeBulkUpsertResponse(created=created, existing=existing)


@router.get("/{type_id}")
def get_document_type(type_id: str) -> DocumentType:
    with get_session() as session:
        dt = session.get(DocumentType, type_id)
        if not dt:
            raise HTTPException(status_code=404, detail="Document type not found")
        return dt


@router.patch("/{type_id}")
def update_document_type(type_id: str, req: DocumentTypeUpdateRequest) -> DocumentType:
    with get_session() as session:
        dt = session.get(DocumentType, type_id)
        if not dt:
            raise HTTPException(status_code=404, detail="Document type not found")

        changed = False
        if req.key is not None:
            dt.key = req.key.strip()
            changed = True
        if req.title is not None:
            dt.title = req.title.strip()
            changed = True
        if req.description is not None:
            dt.description = req.description
            changed = True

        if changed:
            dt.updated_at = datetime.utcnow()
            session.add(dt)
            session.commit()
            session.refresh(dt)
        return dt

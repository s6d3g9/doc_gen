from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..db import get_session
from ..models import DocumentTemplate, DocumentTemplateField, DocumentTemplateVersion, TemplateFieldType

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    title: str
    category: Optional[str] = None
    description: Optional[str] = None


class TemplateVersionCreate(BaseModel):
    version: int
    body: str


class TemplateFieldCreate(BaseModel):
    key: str
    label: str
    field_type: TemplateFieldType
    required: bool = False
    order: int = 0
    options: Optional[list[str]] = None
    default_value: Optional[str] = None


@router.get("")
def list_templates() -> list[DocumentTemplate]:
    with get_session() as session:
        return list(session.exec(select(DocumentTemplate).order_by(DocumentTemplate.created_at.desc())).all())


@router.post("")
def create_template(payload: TemplateCreate) -> DocumentTemplate:
    tpl = DocumentTemplate(**payload.model_dump())
    with get_session() as session:
        session.add(tpl)
        session.commit()
        session.refresh(tpl)
        return tpl


@router.get("/{template_id}")
def get_template(template_id: str) -> DocumentTemplate:
    with get_session() as session:
        tpl = session.get(DocumentTemplate, template_id)
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        return tpl


@router.post("/{template_id}/versions")
def create_version(template_id: str, payload: TemplateVersionCreate) -> DocumentTemplateVersion:
    with get_session() as session:
        tpl = session.get(DocumentTemplate, template_id)
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        v = DocumentTemplateVersion(template_id=template_id, **payload.model_dump())
        session.add(v)
        session.commit()
        session.refresh(v)
        return v


@router.get("/{template_id}/versions")
def list_versions(template_id: str) -> list[DocumentTemplateVersion]:
    with get_session() as session:
        return list(
            session.exec(
                select(DocumentTemplateVersion)
                .where(DocumentTemplateVersion.template_id == template_id)
                .order_by(DocumentTemplateVersion.version.desc())
            ).all()
        )


@router.get("/versions/{version_id}")
def get_version(version_id: str) -> DocumentTemplateVersion:
    with get_session() as session:
        v = session.get(DocumentTemplateVersion, version_id)
        if not v:
            raise HTTPException(status_code=404, detail="Template version not found")
        return v


@router.post("/versions/{version_id}/fields")
def add_field(version_id: str, payload: TemplateFieldCreate) -> DocumentTemplateField:
    field = DocumentTemplateField(template_version_id=version_id, **payload.model_dump())
    with get_session() as session:
        v = session.get(DocumentTemplateVersion, version_id)
        if not v:
            raise HTTPException(status_code=404, detail="Template version not found")
        session.add(field)
        session.commit()
        session.refresh(field)
        return field


@router.get("/versions/{version_id}/fields")
def list_fields(version_id: str) -> list[DocumentTemplateField]:
    with get_session() as session:
        return list(
            session.exec(
                select(DocumentTemplateField)
                .where(DocumentTemplateField.template_version_id == version_id)
                .order_by(DocumentTemplateField.order.asc())
            ).all()
        )

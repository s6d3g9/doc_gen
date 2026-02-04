from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel
from sqlmodel import select

from ..artifacts import write_text
from ..db import get_session
from ..models import (
    Document,
    DocumentTemplateField,
    DocumentTemplateVersion,
    GeneratedDocument,
    Organization,
    TemplateFieldType,
    DocumentVersion,
)

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    template_version_id: str
    title: str
    data: dict[str, Any]


class GenerateResponse(BaseModel):
    document_id: str
    version_id: str
    artifact_path: str
    artifact_download_url: str
    content_type: str = "text/plain"


@router.post("")
def generate(req: GenerateRequest) -> GenerateResponse:
    with get_session() as session:
        tv = session.get(DocumentTemplateVersion, req.template_version_id)
        if not tv:
            raise HTTPException(status_code=404, detail="Template version not found")

        fields = list(
            session.exec(
                select(DocumentTemplateField).where(DocumentTemplateField.template_version_id == tv.id)
            ).all()
        )

        data = dict(req.data or {})

        _validate_required(fields, data)
        _expand_entity_fields(session, fields, data)

        env = Environment(undefined=StrictUndefined, autoescape=False)
        try:
            rendered = env.from_string(tv.body).render(**data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Template render failed: {e}")

        artifact_path = write_text(rendered, suffix=".txt")

        doc = Document(title=req.title)
        version = DocumentVersion(document_id=doc.id, artifact_path=artifact_path, content_type="text/plain")
        g = GeneratedDocument(document_id=doc.id, template_version_id=tv.id, data=data)

        session.add(doc)
        session.add(version)
        session.add(g)
        session.commit()
        session.refresh(version)

        return GenerateResponse(
            document_id=doc.id,
            version_id=version.id,
            artifact_path=artifact_path,
            artifact_download_url=f"/documents/versions/{version.id}/artifact",
        )


def _validate_required(fields: list[DocumentTemplateField], data: dict[str, Any]) -> None:
    missing: list[str] = []
    for f in fields:
        if not f.required:
            continue
        if f.key not in data or data.get(f.key) in (None, ""):
            missing.append(f.key)
    if missing:
        raise HTTPException(status_code=400, detail={"missing_fields": missing})


def _expand_entity_fields(session, fields: list[DocumentTemplateField], data: dict[str, Any]) -> None:
    """Expand organization_ref fields.

    Convention:
    - if field key is `party1_org_id` and type is organization_ref
    then we inject:
      - party1_org_id_name, party1_org_id_inn, party1_org_id_address, ...
    """

    for f in fields:
        if f.field_type != TemplateFieldType.organization_ref:
            continue

        org_id = data.get(f.key)
        if not org_id:
            continue

        org = session.get(Organization, str(org_id))
        if not org:
            raise HTTPException(status_code=400, detail=f"Organization not found: {org_id}")

        prefix = f.key
        data[f"{prefix}_name"] = org.name
        if org.inn:
            data[f"{prefix}_inn"] = org.inn
        if org.ogrn:
            data[f"{prefix}_ogrn"] = org.ogrn
        if org.kpp:
            data[f"{prefix}_kpp"] = org.kpp
        if org.address:
            data[f"{prefix}_address"] = org.address
        if org.phone:
            data[f"{prefix}_phone"] = org.phone
        if org.email:
            data[f"{prefix}_email"] = org.email

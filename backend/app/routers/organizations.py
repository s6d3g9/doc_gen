from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from ..db import get_session
from ..models import Organization

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreate(BaseModel):
    name: str
    inn: Optional[str] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    inn: Optional[str] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


@router.get("")
def list_organizations(q: str | None = Query(default=None)) -> list[Organization]:
    with get_session() as session:
        stmt = select(Organization)
        if q:
            qn = f"%{q.strip()}%"
            stmt = stmt.where((Organization.name.ilike(qn)) | (Organization.inn.ilike(qn)))
        return list(session.exec(stmt.order_by(Organization.created_at.desc())).all())


@router.get("/{org_id}")
def get_organization(org_id: str) -> Organization:
    with get_session() as session:
        org = session.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org


@router.post("")
def create_organization(payload: OrganizationCreate) -> Organization:
    org = Organization(**payload.model_dump())
    with get_session() as session:
        session.add(org)
        session.commit()
        session.refresh(org)
        return org


@router.patch("/{org_id}")
def update_organization(org_id: str, payload: OrganizationUpdate) -> Organization:
    with get_session() as session:
        org = session.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(org, k, v)
        org.updated_at = datetime.utcnow()
        session.add(org)
        session.commit()
        session.refresh(org)
        return org


@router.delete("/{org_id}")
def delete_organization(org_id: str) -> dict[str, str]:
    with get_session() as session:
        org = session.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        session.delete(org)
        session.commit()
        return {"status": "deleted"}

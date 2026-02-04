from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..contract_dates import extract_date_spans
from ..db import get_session
from ..google_calendar import insert_all_day_event
from ..models import CalendarEventLink, Document, DocumentVersion
from ..settings import settings
from ..text import read_version_text

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarSyncRequest(BaseModel):
    version_id: str
    calendar_id: Optional[str] = None
    dry_run: bool = False


class CalendarSyncItem(BaseModel):
    start_date: date_type
    end_date: date_type
    google_event_id: Optional[str] = None
    summary: str


class CalendarSyncResponse(BaseModel):
    created: list[CalendarSyncItem]


@router.post("/sync")
def sync_calendar(req: CalendarSyncRequest) -> CalendarSyncResponse:
    calendar_id = req.calendar_id or settings.google_calendar_id
    if not calendar_id:
        raise HTTPException(status_code=400, detail="calendar_id is required (or set GOOGLE_CALENDAR_ID)")

    with get_session() as session:
        version = session.get(DocumentVersion, req.version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        doc = session.get(Document, version.document_id)
        title = doc.title if doc else "Document"

        text = read_version_text(version)
        spans = extract_date_spans(text)
        if not spans:
            return CalendarSyncResponse(created=[])

        created: list[CalendarSyncItem] = []

        for s in spans:
            # idempotency: skip if we already linked an event for the same range
            exists = session.exec(
                select(CalendarEventLink).where(
                    (CalendarEventLink.version_id == version.id)
                    & (CalendarEventLink.google_calendar_id == calendar_id)
                    & (CalendarEventLink.start_date == s.start)
                    & (CalendarEventLink.end_date == s.end)
                )
            ).first()
            if exists:
                created.append(
                    CalendarSyncItem(
                        start_date=s.start,
                        end_date=s.end,
                        google_event_id=exists.google_event_id,
                        summary=f"{title} — дата из договора",
                    )
                )
                continue

            summary = f"{title} — дата из договора"
            if req.dry_run:
                created.append(CalendarSyncItem(start_date=s.start, end_date=s.end, google_event_id=None, summary=summary))
                continue

            event_id = insert_all_day_event(
                calendar_id=calendar_id,
                summary=summary,
                start=s.start,
                end_inclusive=s.end,
                description=f"Source: {s.source}\nVersion: {version.id}",
                private_props={"doc_gen_version_id": version.id},
            )

            link = CalendarEventLink(
                version_id=version.id,
                google_calendar_id=calendar_id,
                google_event_id=event_id,
                start_date=s.start,
                end_date=s.end,
            )
            session.add(link)
            session.commit()

            created.append(
                CalendarSyncItem(start_date=s.start, end_date=s.end, google_event_id=event_id, summary=summary)
            )

        return CalendarSyncResponse(created=created)


@router.get("/events")
def list_calendar_events(version_id: str) -> list[CalendarEventLink]:
    with get_session() as session:
        return list(
            session.exec(select(CalendarEventLink).where(CalendarEventLink.version_id == version_id)).all()
        )

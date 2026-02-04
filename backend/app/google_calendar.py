from __future__ import annotations

from datetime import date, timedelta

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .settings import settings


SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    if not settings.google_service_account_file:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_FILE is not configured")
    creds = Credentials.from_service_account_file(settings.google_service_account_file, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def insert_all_day_event(
    *,
    calendar_id: str,
    summary: str,
    start: date,
    end_inclusive: date,
    description: str | None = None,
    private_props: dict[str, str] | None = None,
) -> str:
    service = get_calendar_service()

    # Google all-day events use an exclusive end date.
    end_exclusive = end_inclusive + timedelta(days=1)

    body: dict = {
        "summary": summary,
        "start": {"date": start.isoformat()},
        "end": {"date": end_exclusive.isoformat()},
    }
    if description:
        body["description"] = description
    if private_props:
        body["extendedProperties"] = {"private": private_props}

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return str(created["id"])

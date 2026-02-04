from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pydantic import BaseModel
from sqlmodel import select

from ..db import get_session
from ..deps import get_current_user
from ..models import Document, DocumentVersion, GoogleDriveFileLink, GoogleOAuthConnection, User
from ..settings import settings
from ..text import read_version_text


router = APIRouter(prefix="/google", tags=["google"])


DRIVE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleStatusResponse(BaseModel):
    connected: bool
    email: Optional[str] = None


class SaveToGoogleDocsRequest(BaseModel):
    version_id: str
    title: Optional[str] = None
    # If provided, saves this text instead of raw version artifact.
    text: Optional[str] = None


class SaveToGoogleDocsResponse(BaseModel):
    drive_file_id: str
    web_view_link: Optional[str] = None


def _require_oauth_config() -> None:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID and "
                "GOOGLE_OAUTH_CLIENT_SECRET in backend/.env and restart docker compose."
            ),
        )
    if not settings.google_oauth_redirect_url:
        raise HTTPException(status_code=400, detail="GOOGLE_OAUTH_REDIRECT_URL is not configured")
    if not settings.auth_state_secret:
        raise HTTPException(status_code=400, detail="AUTH_STATE_SECRET is not configured")


def _sign_state(payload: str) -> str:
    secret = (settings.auth_state_secret or "").encode("utf-8")
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")


def _encode_state(*, return_to: str) -> str:
    # keep it short and verifiable: ts|return_to|sig
    ts = str(int(time.time()))
    payload = f"{ts}|{return_to}"
    sig = _sign_state(payload)
    raw = f"{payload}|{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip("=")


def _decode_state(state: str) -> str:
    try:
        padded = state + "=" * (-len(state) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        ts, return_to, sig = raw.split("|", 2)
        payload = f"{ts}|{return_to}"
        if not hmac.compare_digest(_sign_state(payload), sig):
            raise ValueError("bad sig")
        # allow 30 minutes
        if int(time.time()) - int(ts) > 30 * 60:
            raise ValueError("expired")
        return return_to
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state")


def _validate_return_to(return_to: str) -> str:
    parsed = urlparse(return_to)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid return_to")

    return_to_origin = f"{parsed.scheme}://{parsed.netloc}"

    allowed: list[str] = []

    if settings.frontend_base_url:
        fb = settings.frontend_base_url.rstrip("/")
        allowed.append(fb)
        if fb.startswith("http://localhost:"):
            allowed.append(fb.replace("http://localhost:", "http://127.0.0.1:"))
        if fb.startswith("http://127.0.0.1:"):
            allowed.append(fb.replace("http://127.0.0.1:", "http://localhost:"))

    cors = (settings.cors_allow_origins or "").strip()
    if cors:
        for o in cors.split(","):
            o = o.strip().rstrip("/")
            if o:
                allowed.append(o)

    allowed_origins: set[str] = set()
    for o in allowed:
        p = urlparse(o)
        if p.scheme and p.netloc:
            allowed_origins.add(f"{p.scheme}://{p.netloc}")

    if return_to_origin not in allowed_origins:
        raise HTTPException(status_code=400, detail="Invalid return_to")

    return return_to


def _get_connection() -> Optional[GoogleOAuthConnection]:
    with get_session() as session:
        return session.get(GoogleOAuthConnection, "default")


def _save_connection(conn: GoogleOAuthConnection) -> None:
    with get_session() as session:
        session.add(conn)
        session.commit()


def _delete_connection() -> None:
    with get_session() as session:
        existing = session.get(GoogleOAuthConnection, "default")
        if existing:
            session.delete(existing)
            session.commit()


async def _exchange_code(code: str) -> dict[str, Any]:
    _require_oauth_config()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_url,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {resp.text}")
        return resp.json()


async def _fetch_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail=f"Userinfo failed: {resp.text}")
        return resp.json()


def _credentials_from_connection(conn: GoogleOAuthConnection) -> Credentials:
    _require_oauth_config()
    creds = Credentials(
        token=conn.access_token,
        refresh_token=conn.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=DRIVE_SCOPES,
    )
    if conn.expires_at:
        creds.expiry = conn.expires_at
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist refreshed access token/expiry.
        conn.access_token = creds.token or conn.access_token
        conn.expires_at = getattr(creds, "expiry", None)
        conn.updated_at = datetime.utcnow()
        _save_connection(conn)
    return creds


@router.get("/status")
def status() -> GoogleStatusResponse:
    conn = _get_connection()
    return GoogleStatusResponse(connected=bool(conn), email=(conn.email if conn else None))


@router.get("/login")
def login(return_to: str = Query(default="")):
    _require_oauth_config()
    if not return_to:
        return_to = (settings.frontend_base_url or "").rstrip("/")
    return_to = _validate_return_to(return_to)
    state = _encode_state(return_to=return_to)

    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_url,
        "response_type": "code",
        "scope": " ".join(DRIVE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }

    url = "https://accounts.google.com/o/oauth2/v2/auth"
    return RedirectResponse(url=f"{url}?{urlencode(params)}")


@router.get("/callback")
async def callback(code: str, state: str):
    _require_oauth_config()
    return_to = _decode_state(state)

    tok = await _exchange_code(code)
    access_token = tok.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access_token")

    userinfo = await _fetch_userinfo(access_token)

    expires_in = int(tok.get("expires_in") or 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # Google may not return refresh_token on every auth.
    with get_session() as session:
        existing = session.get(GoogleOAuthConnection, "default")
        refresh_token = tok.get("refresh_token") or (existing.refresh_token if existing else None)

        conn = existing or GoogleOAuthConnection(id="default", access_token=access_token)
        conn.updated_at = datetime.utcnow()
        conn.email = userinfo.get("email")
        conn.sub = userinfo.get("sub")
        conn.access_token = access_token
        conn.refresh_token = refresh_token
        conn.token_type = tok.get("token_type")
        conn.scope = tok.get("scope")
        conn.expires_at = expires_at

        session.add(conn)
        session.commit()

    return RedirectResponse(url=return_to)


@router.post("/logout")
def logout() -> dict[str, Any]:
    _delete_connection()
    return {"ok": True}


@router.post("/docs/save")
def save_to_google_docs(req: SaveToGoogleDocsRequest, user: User = Depends(get_current_user)) -> SaveToGoogleDocsResponse:
    conn = _get_connection()
    if not conn:
        raise HTTPException(status_code=401, detail="Google is not connected")

    with get_session() as session:
        v = session.exec(
            select(DocumentVersion)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(DocumentVersion.id == req.version_id)
            .where(Document.owner_user_id == user.id)
            .limit(1)
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail="Version not found")

    text = req.text if req.text is not None else read_version_text(v)
    title = (req.title or "Document").strip() or "Document"

    creds = _credentials_from_connection(conn)
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    created_doc = docs.documents().create(body={"title": title}).execute()
    file_id = str(created_doc.get("documentId"))
    if not file_id:
        raise HTTPException(status_code=500, detail="Failed to create Google Doc")

    docs.documents().batchUpdate(
        documentId=file_id,
        body={
            "requests": [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": text,
                    }
                }
            ]
        },
    ).execute()

    meta = drive.files().get(fileId=file_id, fields="webViewLink").execute()
    web_link = meta.get("webViewLink")

    with get_session() as session:
        session.add(GoogleDriveFileLink(version_id=req.version_id, drive_file_id=file_id, web_view_link=web_link))
        session.commit()

    return SaveToGoogleDocsResponse(drive_file_id=file_id, web_view_link=web_link)

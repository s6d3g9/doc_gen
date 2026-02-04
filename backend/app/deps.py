from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import decode_jwt
from .db import get_session
from .models import User
from .settings import settings


bearer = HTTPBearer(auto_error=False)


def require_local_auth_config() -> None:
    if not settings.auth_jwt_secret or not settings.auth_seed_secret:
        raise HTTPException(
            status_code=400,
            detail=(
                "Local auth is not configured. Set AUTH_JWT_SECRET and AUTH_SEED_SECRET in backend/.env and restart."
            ),
        )


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> User:
    require_local_auth_config()
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    td = decode_jwt(creds.credentials)
    if not td:
        raise HTTPException(status_code=401, detail="Invalid token")

    with get_session() as session:
        u = session.get(User, td.user_id)
        if not u:
            raise HTTPException(status_code=401, detail="User not found")
        return u


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Optional[User]:
    if not creds or not creds.credentials:
        return None
    td = decode_jwt(creds.credentials)
    if not td:
        return None
    with get_session() as session:
        return session.get(User, td.user_id)

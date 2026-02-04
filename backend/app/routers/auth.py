from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..auth import (
    generate_seed_phrase,
    hash_password,
    hash_seed,
    issue_jwt,
    normalize_seed,
    seed_key,
    verify_password,
    verify_seed,
)
from ..deps import get_current_user, require_local_auth_config
from ..db import get_session
from ..models import User


router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str


class RegisterResponse(BaseModel):
    access_token: str
    seed_phrase: str


class LoginEmailRequest(BaseModel):
    email: str
    password: str


class LoginSeedRequest(BaseModel):
    seed_phrase: str


class TokenResponse(BaseModel):
    access_token: str


class MeResponse(BaseModel):
    id: str
    email: str
    created_at: datetime


def _require_local_auth_config() -> None:
    require_local_auth_config()


@router.post("/register")
def register(req: RegisterRequest) -> RegisterResponse:
    _require_local_auth_config()

    email = (req.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")

    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    phrase = generate_seed_phrase(12)
    skey = seed_key(phrase)

    with get_session() as session:
        exists = session.exec(select(User).where(User.email == email)).first()
        if exists:
            raise HTTPException(status_code=409, detail="Email already registered")

        u = User(
            email=email,
            password_hash=hash_password(req.password),
            seed_key=skey,
            seed_hash=hash_seed(phrase),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(u)
        session.commit()
        session.refresh(u)

    token = issue_jwt(user_id=u.id, email=u.email)
    return RegisterResponse(access_token=token, seed_phrase=phrase)


@router.post("/login/email")
def login_email(req: LoginEmailRequest) -> TokenResponse:
    _require_local_auth_config()
    email = (req.email or "").strip().lower()

    with get_session() as session:
        u = session.exec(select(User).where(User.email == email)).first()
        if not u:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(req.password or "", u.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(access_token=issue_jwt(user_id=u.id, email=u.email))


@router.post("/login/seed")
def login_seed(req: LoginSeedRequest) -> TokenResponse:
    _require_local_auth_config()

    seed_norm = normalize_seed(req.seed_phrase or "")
    if len(seed_norm.split()) < 6:
        raise HTTPException(status_code=400, detail="Seed phrase is too short")

    skey = seed_key(seed_norm)

    with get_session() as session:
        u = session.exec(select(User).where(User.seed_key == skey)).first()
        if not u:
            raise HTTPException(status_code=401, detail="Invalid seed phrase")

        if not verify_seed(seed_norm, u.seed_hash):
            raise HTTPException(status_code=401, detail="Invalid seed phrase")

    return TokenResponse(access_token=issue_jwt(user_id=u.id, email=u.email))


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, created_at=user.created_at)

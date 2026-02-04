from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .artifacts import ensure_artifacts_dir
from .db import init_db
from .routers import ai, calendar, documents, health, organizations, tasks, templates
from .routers import auth
from .routers import contracts
from .routers import document_types
from .routers import google_drive
from .routers import generate as generate_router
from .settings import settings

app = FastAPI(title="backend", version="0.1.0")


def _cors_origins() -> list[str]:
    raw = (settings.cors_allow_origins or "").strip()
    if not raw:
        return []
    return [o.strip() for o in raw.split(",") if o.strip()]


origins = _cors_origins()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )


@app.on_event("startup")
def _startup() -> None:
    ensure_artifacts_dir()
    init_db()


app.include_router(health.router)
app.include_router(document_types.router)
app.include_router(documents.router)
app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(tasks.router)
app.include_router(organizations.router)
app.include_router(templates.router)
app.include_router(contracts.router)
app.include_router(generate_router.router)
app.include_router(calendar.router)
app.include_router(google_drive.router)

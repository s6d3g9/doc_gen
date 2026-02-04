from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from .settings import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)


def _column_exists(*, table: str, column: str) -> bool:
    q = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = :table_name AND column_name = :column_name
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"table_name": table, "column_name": column}).first()
        return bool(row)


def _exec_ddl(sql: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(sql))


def _migrate_schema() -> None:
    # NOTE: project currently runs without Alembic migrations.
    # Keep this minimal + idempotent for dev containers.

    # Document ownership
    if not _column_exists(table="document", column="owner_user_id"):
        _exec_ddl('ALTER TABLE "document" ADD COLUMN owner_user_id VARCHAR NULL')
        _exec_ddl('CREATE INDEX IF NOT EXISTS ix_document_owner_user_id ON "document" (owner_user_id)')

    # Multi-key OpenRouter support
    if not _column_exists(table="useraiconfig", column="api_key_id"):
        _exec_ddl('ALTER TABLE "useraiconfig" ADD COLUMN api_key_id VARCHAR NULL')
        _exec_ddl('CREATE INDEX IF NOT EXISTS ix_useraiconfig_api_key_id ON "useraiconfig" (api_key_id)')


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_schema()


@contextmanager
def get_session() -> Session:
    with Session(engine) as session:
        yield session

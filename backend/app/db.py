from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import CHAR, TypeDecorator, event
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def _resolve_sqlite_path(url: str) -> str:
    """
    Make any relative ./path inside a sqlite URL absolute, anchored to backend/.
    Ensures the parent dir exists. Returns the (possibly rewritten) URL.
    """
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix):
        return url
    raw = url[len(prefix):]
    p = Path(raw)
    if not p.is_absolute():
        backend_dir = Path(__file__).resolve().parents[1]
        p = (backend_dir / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{p.as_posix()}"


DATABASE_URL = _resolve_sqlite_path(settings.database_url)

engine = create_async_engine(DATABASE_URL, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# SQLite needs PRAGMA foreign_keys=ON per connection for CASCADE deletes to fire.
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass


class GUID(TypeDecorator):
    """
    Cross-dialect UUID column type.

    On Postgres -> native UUID. On SQLite/MySQL -> CHAR(36) string. At the
    Python layer we always present uuid.UUID, so the rest of the codebase
    doesn't need to know which dialect is in play.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgUUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value) if dialect.name != "postgresql" else value
        try:
            parsed = uuid.UUID(str(value))
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid UUID value: {value!r}") from e
        return str(parsed) if dialect.name != "postgresql" else parsed

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

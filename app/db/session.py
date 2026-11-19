"""Database engine and session factory (sync SQLAlchemy 2.0).

FastAPI runs plain `def` endpoints in a thread pool, so a sync driver is fine
and keeps the code close to what you know from database/sql in Go.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards.

    Like `defer db.Close()` in Go — the code after `yield` runs when the request ends.
    """
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()

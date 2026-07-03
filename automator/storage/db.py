"""SQLAlchemy engine 与 session。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings.ensure_dirs()
        _engine = create_engine(
            settings.db_url,
            echo=False,
            connect_args={"check_same_thread": False}
            if settings.db_url.startswith("sqlite")
            else {},
        )
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_session() -> Iterator[Session]:
    """获取 DB session 的上下文管理器。"""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """建表(幂等)。"""
    from .models import Base

    Base.metadata.create_all(get_engine())

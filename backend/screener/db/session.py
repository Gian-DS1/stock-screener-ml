from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from screener.config import ensure_dirs, settings

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        ensure_dirs()
        _engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def init_db() -> None:
    from screener.db.models import Base

    Base.metadata.create_all(get_engine())


@contextmanager
def get_session() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from screener.config import ensure_dirs, settings

_engine = None
_SessionLocal: sessionmaker | None = None

# Columnas añadidas tras la creación inicial: se agregan a bases ya existentes
# sin perder datos (SQLite ALTER TABLE ADD COLUMN, idempotente).
_MIGRATIONS = {
    "runs": {
        "phase": "VARCHAR(60)",
        "progress_current": "INTEGER",
        "progress_total": "INTEGER",
        "updated_at": "DATETIME",
    },
}


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        ensure_dirs()
        _engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
        # WAL: lectores (API) y un escritor (pipeline) concurrentes sin bloqueos
        with _engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def _run_migrations(engine) -> None:
    with engine.begin() as conn:
        for table, columns in _MIGRATIONS.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    from screener.db.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    _run_migrations(engine)
    _reap_orphan_runs(engine)


def _reap_orphan_runs(engine, stale_hours: int = 6) -> None:
    """Marca como interrumpidos los runs 'running' demasiado viejos.

    Un proceso matado a la fuerza (kill) nunca ejecuta el cierre de su
    auditoría y deja el run 'running' para siempre, bloqueando el indicador de
    actividad y el lanzamiento de nuevos jobs. El umbral (6h) supera cualquier
    ejecución real —incluido el backfill histórico inicial— así que solo
    alcanza a huérfanos genuinos.
    """
    from datetime import timedelta

    from screener.db.models import utcnow

    cutoff = utcnow() - timedelta(hours=stale_hours)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE runs SET status='interrupted', "
                "detail=COALESCE(detail,'')||' [huérfano: proceso no finalizó]', "
                "finished_at=:now "
                "WHERE status='running' AND started_at < :cutoff"
            ),
            {"now": utcnow(), "cutoff": cutoff},
        )


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

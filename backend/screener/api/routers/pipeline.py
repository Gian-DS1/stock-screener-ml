"""Disparo manual del pipeline desde el dashboard + estado/progreso en vivo.

El estado se lee de la tabla `runs`, así que refleja CUALQUIER ejecución en
curso —dashboard, CLI o tarea programada de Windows— y su progreso granular.
"""
import threading

import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from screener.config import settings
from screener.db import Run, get_session
from screener.pipeline import audited_run

router = APIRouter(tags=["pipeline"])

_lock = threading.Lock()
_current: dict = {"kind": None}

_JOBS = {
    "run-daily": "run_daily_pipeline",
    "score": "run_score",
    "train": "run_train",
    "build-dataset": "run_build_dataset",
    "drift": "run_drift",
    "backfill": "run_backfill",
}


def _execute(kind: str) -> None:
    import screener.pipeline as pipeline

    fn = getattr(pipeline, _JOBS[kind])
    try:
        with audited_run("daily" if kind == "run-daily" else kind) as progress:
            fn(progress=progress)
    except Exception:
        pass  # el traceback queda registrado en la tabla runs
    finally:
        with _lock:
            _current["kind"] = None


@router.post("/pipeline/{kind}")
def trigger(kind: str) -> dict:
    if kind not in _JOBS:
        raise HTTPException(404, f"job desconocido: {kind}")
    # ¿ya hay un run en curso (este API, el CLI o la tarea programada)?
    with get_session() as session:
        active = session.execute(
            select(Run).where(Run.status == "running")
        ).scalars().first()
        if active is not None:
            raise HTTPException(409, f"ya hay un job en ejecución: {active.kind}")
    with _lock:
        if _current["kind"] is not None:
            raise HTTPException(409, f"ya hay un job en ejecución: {_current['kind']}")
        _current["kind"] = kind
    threading.Thread(target=_execute, args=(kind,), daemon=True).start()
    return {"started": kind}


def _data_lake_snapshot() -> dict:
    """Conteos baratos del data lake para dar señal de vida (incl. del run actual)."""
    snap: dict = {}
    try:
        from screener.ingest.edgar_8k import load_filings

        filings = load_filings()
        if filings is not None:
            snap["filings_8k"] = int(len(filings))
            snap["filings_8k_scored"] = int(filings["sent_score"].notna().sum())
    except Exception:
        pass
    try:
        prices_dir = settings.raw_dir / "prices"
        snap["tickers_with_prices"] = len(list(prices_dir.glob("*.parquet"))) if prices_dir.exists() else 0
    except Exception:
        pass
    return snap


@router.get("/pipeline/status")
def status() -> dict:
    with get_session() as session:
        active = session.execute(
            select(Run).where(Run.status == "running").order_by(Run.id.desc())
        ).scalars().first()
        running = None
        if active is not None:
            pct = None
            if active.progress_total:
                pct = round(100 * (active.progress_current or 0) / active.progress_total, 1)
            running = {
                "kind": active.kind,
                "phase": active.phase,
                "current": active.progress_current,
                "total": active.progress_total,
                "pct": pct,
                "started_at": active.started_at.isoformat(),
                "updated_at": active.updated_at.isoformat() if active.updated_at else None,
            }
    return {"running": running, "data_lake": _data_lake_snapshot()}

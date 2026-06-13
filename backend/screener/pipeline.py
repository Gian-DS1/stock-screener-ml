"""Orquestación de los flujos del sistema (invocados desde el CLI y la API)."""
import traceback
from contextlib import contextmanager
from typing import Iterator

import pandas as pd

from screener.config import ensure_dirs, settings


class RunProgress:
    """Reporta la fase y el avance de un run a la base de datos en vivo.

    El dashboard lee estos campos por polling para mostrar una barra. Las
    actualizaciones son por fase/lote (no por item), así que el coste de
    escritura es despreciable y, con WAL, no bloquea las lecturas del API.
    """

    def __init__(self, run_id: int):
        self.run_id = run_id

    def update(self, phase: str, current: int | None = None, total: int | None = None) -> None:
        from screener.db import Run, get_session
        from screener.db.models import utcnow

        with get_session() as session:
            run = session.get(Run, self.run_id)
            if run is not None:
                run.phase = phase
                run.progress_current = current
                run.progress_total = total
                run.updated_at = utcnow()


class _NullProgress(RunProgress):
    def __init__(self):  # sin run asociado: no persiste nada
        pass

    def update(self, *args, **kwargs) -> None:
        pass


NULL_PROGRESS = _NullProgress()


@contextmanager
def audited_run(kind: str) -> Iterator[RunProgress]:
    """Registra la ejecución en la tabla de auditoría con resultado o traceback.

    Cede un RunProgress para que los pasos reporten su avance en vivo.
    """
    from screener.db import Run, get_session, init_db
    from screener.db.models import utcnow

    init_db()
    with get_session() as session:
        run = Run(kind=kind, phase="iniciando")
        session.add(run)
        session.flush()
        run_id = run.id

    try:
        yield RunProgress(run_id)
    except Exception:
        with get_session() as session:
            run = session.get(Run, run_id)
            run.status = "error"
            run.phase = "error"
            run.finished_at = utcnow()
            run.detail = traceback.format_exc()[-4000:]
        raise
    else:
        with get_session() as session:
            run = session.get(Run, run_id)
            if run.status == "running":
                run.status = "success"
            run.phase = "completado"
            run.finished_at = utcnow()


def _filter_universe(tickers: list[str] | None) -> pd.DataFrame:
    from screener.universe import load_universe

    uni = load_universe()
    if tickers:
        wanted = {t.upper().replace(".", "-") for t in tickers}
        uni = uni[uni["yf_ticker"].isin(wanted) | uni["ticker"].isin(wanted)]
        if uni.empty:
            raise ValueError(f"Ningún ticker de {sorted(wanted)} está en el universo")
    return uni


def _emit_universe_alert(changes: dict, log=print) -> None:
    """Registra una alerta cuando cambian los constituyentes de los índices."""
    added, removed = changes.get("added", []), changes.get("removed", [])
    if not added and not removed:
        return
    from screener.db import Alert, get_session, init_db

    parts = []
    if added:
        parts.append(f"entraron {len(added)}: {', '.join(added[:8])}{'…' if len(added) > 8 else ''}")
    if removed:
        parts.append(f"salieron {len(removed)}: {', '.join(removed[:8])}{'…' if len(removed) > 8 else ''}")
    init_db()
    with get_session() as session:
        session.add(Alert(
            type="UNIVERSO",
            message="Cambios en los índices — " + " · ".join(parts),
            severity="info",
        ))


def run_backfill(
    tickers: list[str] | None = None,
    skip_sentiment: bool = False,
    log=print,
    progress: RunProgress = NULL_PROGRESS,
) -> None:
    """Descarga el histórico completo (o lo que falte) al data lake."""
    from screener.ingest.edgar_facts import update_fundamentals
    from screener.ingest.fred import update_macro
    from screener.ingest.prices import update_prices

    ensure_dirs()

    # En modo universo completo (no subset de prueba) se siguen las altas/bajas
    # de los índices antes de descargar: los tickers nuevos entran solos a la
    # ingesta incremental; los que salieron dejan de aparecer en el screening.
    if tickers is None:
        from screener.universe import refresh_universe

        progress.update("Actualizando universo (índices)")
        changes = refresh_universe(log=log)
        _emit_universe_alert(changes, log=log)

    uni = _filter_universe(tickers)
    log(f"Universo: {len(uni)} tickers")

    log("Descargando precios...")
    progress.update("Descargando precios")
    update_prices(uni["yf_ticker"].tolist(), log=log)

    log("Descargando fundamentales EDGAR...")
    progress.update("Descargando fundamentales (EDGAR)")
    update_fundamentals(uni, log=log)

    log("Descargando macro FRED...")
    progress.update("Descargando macro (FRED)")
    try:
        update_macro(log=log)
    except Exception as exc:  # macro caída no debe abortar el resto del backfill
        log(f"  macro: fallo no bloqueante: {exc}")

    if not skip_sentiment:
        from screener.features.sentiment import process_pending_filings
        from screener.ingest.edgar_8k import update_8k_filings

        log("Descargando 8-K...")
        progress.update("Descargando 8-K (SEC)")
        update_8k_filings(uni, log=log, progress=progress)
        progress.update("Analizando sentimiento (FinBERT)")
        process_pending_filings(log=log, progress=progress)

    progress.update("Backfill completo")
    log("Backfill completo.")


def run_build_dataset(log=print, progress: RunProgress = NULL_PROGRESS) -> None:
    from screener.features.builder import build_training_dataset

    progress.update("Construyendo dataset")
    df = build_training_dataset(log=log, progress=progress)
    log(f"Dataset: {len(df):,} filas, {df['ticker'].nunique()} tickers")


def run_train(log=print, progress: RunProgress = NULL_PROGRESS) -> None:
    from screener.models.tactical import train_tactical_model

    progress.update("Entrenando modelo")
    record = train_tactical_model(log=log)
    log(f"Modelo entrenado: umbral={record['threshold']:.3f}")


def run_score(log=print, progress: RunProgress = NULL_PROGRESS) -> None:
    from screener.engine.screener import generate_signals

    progress.update("Generando señales")
    signals = generate_signals(log=log)
    log(f"Señales emitidas: {len(signals)}")


def run_drift(log=print, progress: RunProgress = NULL_PROGRESS) -> None:
    from screener.drift import run_drift_checks

    progress.update("Chequeo de drift")
    run_drift_checks(log=log)


def run_daily_pipeline(log=print, progress: RunProgress = NULL_PROGRESS) -> None:
    """Flujo diario: ingesta incremental -> features -> señales -> portafolio -> drift."""
    from screener.engine.portfolio import evaluate_positions

    # Ligero a propósito: usa el modelo ya entrenado, NO reentrena. El
    # reentrenamiento es un job aparte (manual o cuando el drift lo recomiende).
    run_backfill(log=log, progress=progress)  # incremental: solo descarga lo que falta
    run_score(log=log, progress=progress)
    progress.update("Evaluando portafolio")
    evaluate_positions(log=log)
    try:
        run_drift(log=log, progress=progress)
    except Exception as exc:
        log(f"Drift check falló (no bloqueante): {exc}")

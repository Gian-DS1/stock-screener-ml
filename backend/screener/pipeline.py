"""Orquestación de los flujos del sistema (invocados desde el CLI y la API)."""
import pandas as pd

from screener.config import ensure_dirs, settings


def _filter_universe(tickers: list[str] | None) -> pd.DataFrame:
    from screener.universe import load_universe

    uni = load_universe()
    if tickers:
        wanted = {t.upper().replace(".", "-") for t in tickers}
        uni = uni[uni["yf_ticker"].isin(wanted) | uni["ticker"].isin(wanted)]
        if uni.empty:
            raise ValueError(f"Ningún ticker de {sorted(wanted)} está en el universo")
    return uni


def run_backfill(tickers: list[str] | None = None, skip_sentiment: bool = False, log=print) -> None:
    """Descarga el histórico completo (o lo que falte) al data lake."""
    from screener.ingest.edgar_facts import update_fundamentals
    from screener.ingest.fred import update_macro
    from screener.ingest.prices import update_prices

    ensure_dirs()
    uni = _filter_universe(tickers)
    log(f"Universo: {len(uni)} tickers")

    log("Descargando precios...")
    update_prices(uni["yf_ticker"].tolist(), log=log)

    log("Descargando fundamentales EDGAR...")
    update_fundamentals(uni, log=log)

    log("Descargando macro FRED...")
    update_macro(log=log)

    if not skip_sentiment:
        try:
            from screener.ingest.edgar_8k import update_8k_filings
            from screener.features.sentiment import process_pending_filings

            log("Descargando 8-K...")
            update_8k_filings(uni, log=log)
            process_pending_filings(log=log)
        except ImportError:
            log("Sentimiento aún no implementado; se omite.")

    log("Backfill completo.")


def run_build_dataset(log=print) -> None:
    from screener.features.builder import build_training_dataset

    df = build_training_dataset(log=log)
    log(f"Dataset: {len(df):,} filas, {df['ticker'].nunique()} tickers")


def run_train(log=print) -> None:
    from screener.models.tactical import train_tactical_model

    record = train_tactical_model(log=log)
    log(f"Modelo entrenado: umbral={record['threshold']:.3f}")


def run_score(log=print) -> None:
    from screener.engine.screener import generate_signals

    signals = generate_signals(log=log)
    log(f"Señales emitidas: {len(signals)}")


def run_drift(log=print) -> None:
    from screener.drift import run_drift_checks

    run_drift_checks(log=log)


def run_daily_pipeline(log=print) -> None:
    """Flujo diario: ingesta incremental -> features -> señales -> portafolio -> drift."""
    from screener.engine.portfolio import evaluate_positions

    run_backfill(log=log)  # incremental: solo descarga lo que falta
    run_score(log=log)
    evaluate_positions(log=log)
    try:
        run_drift(log=log)
    except Exception as exc:
        log(f"Drift check falló (no bloqueante): {exc}")

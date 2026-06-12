"""CLI del pipeline. Uso: python -m screener.cli <comando>

Comandos principales:
  init-db     crea las tablas de la app
  backfill    descarga histórico completo (precios, fundamentales, macro, 8-K)
  train       entrena el modelo táctico y optimiza el umbral
  run-daily   actualización incremental + scoring + señales + portafolio + drift
  drift       solo chequeo de deriva
  backtest    validación histórica de la estrategia (CLI, sin UI)
"""
import traceback
from contextlib import contextmanager
from typing import Iterator

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@contextmanager
def audited_run(kind: str) -> Iterator:
    """Registra el run en la tabla de auditoría con su resultado o traceback."""
    from screener.db import Run, get_session, init_db
    from screener.db.models import utcnow

    init_db()
    with get_session() as session:
        run = Run(kind=kind)
        session.add(run)
        session.flush()
        run_id = run.id

    try:
        yield run_id
    except Exception:
        with get_session() as session:
            run = session.get(Run, run_id)
            run.status = "error"
            run.finished_at = utcnow()
            run.detail = traceback.format_exc()[-4000:]
        raise
    else:
        with get_session() as session:
            run = session.get(Run, run_id)
            if run.status == "running":
                run.status = "success"
            run.finished_at = utcnow()


@app.command("init-db")
def init_db_cmd() -> None:
    """Crea las tablas de SQLite."""
    from screener.db import init_db

    init_db()
    typer.echo("Base de datos inicializada.")


@app.command()
def backfill(
    tickers: str = typer.Option("", help="Lista separada por comas; vacío = universo completo"),
    skip_sentiment: bool = typer.Option(False, help="Omitir descarga/procesado de 8-K"),
) -> None:
    """Descarga el histórico completo al data lake (parquet)."""
    from screener.pipeline import run_backfill

    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] or None
    with audited_run("backfill"):
        run_backfill(tickers=ticker_list, skip_sentiment=skip_sentiment)


@app.command()
def build_dataset() -> None:
    """Construye el dataset de entrenamiento PIT (features + labels) en parquet."""
    from screener.pipeline import run_build_dataset

    with audited_run("build-dataset"):
        run_build_dataset()


@app.command()
def train() -> None:
    """Entrena el modelo táctico, optimiza el umbral y lo registra."""
    from screener.pipeline import run_train

    with audited_run("train"):
        run_train()


@app.command()
def score() -> None:
    """Genera señales del día con el modelo activo (sin refrescar datos)."""
    from screener.pipeline import run_score

    with audited_run("score"):
        run_score()


@app.command("run-daily")
def run_daily() -> None:
    """Pipeline diario completo: ingesta incremental, señales, portafolio y drift."""
    from screener.pipeline import run_daily_pipeline

    with audited_run("daily"):
        run_daily_pipeline()


@app.command()
def drift() -> None:
    """Chequeo de deriva de datos y de predicciones."""
    from screener.pipeline import run_drift

    with audited_run("drift"):
        run_drift()


@app.command()
def backtest(
    start: str = typer.Option("2018-01-01"),
    end: str = typer.Option("", help="Vacío = hoy"),
) -> None:
    """Backtest histórico de la estrategia completa (validación, sin UI)."""
    from screener.engine.backtest import run_backtest

    run_backtest(start=start, end=end or None)


if __name__ == "__main__":
    app()

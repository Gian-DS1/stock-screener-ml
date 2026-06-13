"""CLI del pipeline. Uso: python -m screener.cli <comando>

Comandos principales:
  init-db     crea las tablas de la app
  backfill    descarga histórico completo (precios, fundamentales, macro, 8-K)
  train       entrena el modelo táctico y optimiza el umbral
  run-daily   actualización incremental + scoring + señales + portafolio + drift
  drift       solo chequeo de deriva
  backtest    validación histórica de la estrategia (CLI, sin UI)
"""
import typer

from screener.pipeline import audited_run

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


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
    # pasar `progress` permite que la barra del dashboard refleje también las
    # ejecuciones por CLI y por la tarea programada de Windows
    with audited_run("backfill") as progress:
        run_backfill(tickers=ticker_list, skip_sentiment=skip_sentiment, progress=progress)


@app.command("refresh-universe")
def refresh_universe_cmd(
    force: bool = typer.Option(False, help="Forzar aunque el cache sea reciente"),
) -> None:
    """Actualiza los constituyentes de S&P 500 + NASDAQ 100 (altas/bajas)."""
    from screener.universe import refresh_universe

    changes = refresh_universe(force=force, max_age_days=0 if force else 7)
    typer.echo(
        f"Universo: {changes.get('count', '?')} tickers | "
        f"+{len(changes['added'])} altas / -{len(changes['removed'])} bajas"
    )


@app.command()
def build_dataset() -> None:
    """Construye el dataset de entrenamiento PIT (features + labels) en parquet."""
    from screener.pipeline import run_build_dataset

    with audited_run("build-dataset") as progress:
        run_build_dataset(progress=progress)


@app.command()
def train() -> None:
    """Entrena el modelo táctico, optimiza el umbral y lo registra."""
    from screener.pipeline import run_train

    with audited_run("train") as progress:
        run_train(progress=progress)


@app.command()
def score() -> None:
    """Genera señales del día con el modelo activo (sin refrescar datos)."""
    from screener.pipeline import run_score

    with audited_run("score") as progress:
        run_score(progress=progress)


@app.command("run-daily")
def run_daily() -> None:
    """Pipeline diario completo: ingesta incremental, señales, portafolio y drift."""
    from screener.pipeline import run_daily_pipeline

    with audited_run("daily") as progress:
        run_daily_pipeline(progress=progress)


@app.command()
def drift() -> None:
    """Chequeo de deriva de datos y de predicciones."""
    from screener.pipeline import run_drift

    with audited_run("drift") as progress:
        run_drift(progress=progress)


@app.command()
def audit() -> None:
    """Audita la cobertura y coherencia de los datos y del modelo."""
    from screener.diagnostics import audit as run_audit

    run_audit()


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

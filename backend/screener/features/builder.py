"""Ensambla la matriz de features PIT (entrenamiento e inferencia).

Por ticker: técnicos diarios + fundamentales expandidos por available_from +
macro por fecha de publicación + VIX + sentimiento (si existe). Los ratios
dependientes de precio (PE, FCF yield...) se calculan a diario cruzando el
snapshot fundamental vigente con el cierre del día.

Entrenamiento: una fila por ticker-viernes (reduce la autocorrelación de
etiquetas solapadas) con label de retorno futuro. Inferencia: última fila.
"""
import numpy as np
import pandas as pd

from screener.config import ensure_dirs, settings
from screener.features import ALL_FEATURES, AUX_COLUMNS
from screener.features.fundamental import build_snapshots, snapshots_to_daily
from screener.features.macro import build_macro_daily
from screener.features.technical import compute_technical
from screener.features.volatility import compute_vix_features
from screener.ingest.edgar_facts import load_fundamentals
from screener.ingest.fred import load_macro
from screener.ingest.prices import load_prices
from screener.labeling import label_future_max_return
from screener.universe import load_universe

_TAX_RATE = 0.21  # tasa corporativa aproximada para el NOPAT del ROIC


def dataset_path():
    return settings.features_dir / "dataset.parquet"


def latest_path():
    return settings.features_dir / "latest.parquet"


def sentiment_daily_path():
    return settings.features_dir / "sentiment_daily.parquet"


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series(np.nan, index=df.index)


def _where_pos(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den solo cuando den > 0 (evita ratios sin sentido con denominador <= 0)."""
    return num / den.where(den > 0)


def _add_fundamental_ratios(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    eps = _col(df, "eps_ttm")
    eps_growth = _col(df, "eps_ttm_yoy")
    revenue = _col(df, "revenue_ttm")
    ni = _col(df, "net_income_ttm")
    equity = _col(df, "equity")
    ocf = _col(df, "ocf_ttm")
    capex = _col(df, "capex_ttm")
    shares = _col(df, "shares_outstanding").fillna(_col(df, "shares_diluted"))
    debt = _col(df, "lt_debt").fillna(0) + _col(df, "st_debt").fillna(0)
    debt = debt.where(_col(df, "lt_debt").notna() | _col(df, "st_debt").notna())
    cash = _col(df, "cash")
    op_income = _col(df, "operating_income_ttm")
    dep_amort = _col(df, "dep_amort_ttm")
    interest = _col(df, "interest_expense_ttm")

    market_cap = close * shares
    fcf = ocf - capex.fillna(0)
    fcf = fcf.where(ocf.notna())

    # --- 8 features fundamentales del modelo ---
    df["pe_ttm"] = _where_pos(close, eps)
    df["peg_ttm"] = _where_pos(df["pe_ttm"], eps_growth * 100)
    df["fcf_yield"] = _where_pos(fcf, market_cap)
    df["revenue_growth_yoy"] = _col(df, "revenue_ttm_yoy")
    df["gross_margin"] = _where_pos(_col(df, "gross_profit_ttm"), revenue)
    df["operating_margin"] = _where_pos(op_income, revenue)
    df["roe"] = _where_pos(ni, equity)
    df["debt_to_equity"] = _where_pos(debt, equity)

    # --- auxiliares para el quality score ---
    df["earnings_yield"] = eps / close
    df["fcf_margin"] = _where_pos(fcf, revenue)
    invested_capital = equity + debt - cash.fillna(0)
    df["roic"] = _where_pos(op_income * (1 - _TAX_RATE), invested_capital)
    df["interest_coverage"] = _where_pos(op_income, interest)
    ebitda = op_income + dep_amort.fillna(0)
    df["net_debt_ebitda"] = (debt - cash.fillna(0)) / ebitda.where(ebitda > 0)
    # percentil de la valoración actual dentro de su propia historia de 5 años:
    # ALTO = barato respecto a sí mismo (yields altos), insumo del descuento
    df["ey_pct_5y"] = df["earnings_yield"].rolling(1260, min_periods=252).rank(pct=True)
    df["fcfy_pct_5y"] = df["fcf_yield"].rolling(1260, min_periods=252).rank(pct=True)
    return df


def _load_sentiment_by_ticker() -> dict[str, pd.DataFrame]:
    path = sentiment_daily_path()
    if not path.exists():
        return {}
    sent = pd.read_parquet(path)
    sent["date"] = pd.to_datetime(sent["date"])
    return {t: g.set_index("date").drop(columns="ticker") for t, g in sent.groupby("ticker")}


class FeatureAssembler:
    """Carga las fuentes una vez y construye frames diarios por ticker."""

    def __init__(self, log=print):
        self.log = log
        self.universe = load_universe()
        facts = load_fundamentals()
        snaps = build_snapshots(facts) if facts is not None else pd.DataFrame()
        self.snaps_by_ticker = (
            {t: g for t, g in snaps.groupby("ticker")} if not snaps.empty else {}
        )
        vix_prices = load_prices("^VIX")
        if vix_prices is None:
            raise RuntimeError("No hay datos del VIX: ejecuta el backfill primero")
        self.vix_features = compute_vix_features(vix_prices)
        calendar = self.vix_features.index  # calendario maestro de sesiones
        self.macro_daily = build_macro_daily(load_macro(), calendar)
        self.sentiment_by_ticker = _load_sentiment_by_ticker()

    def ticker_frame(self, ticker: str, yf_ticker: str) -> pd.DataFrame | None:
        prices = load_prices(yf_ticker)
        if prices is None or len(prices) < settings.min_history_days:
            return None
        df = compute_technical(prices)

        snaps = self.snaps_by_ticker.get(ticker)
        if snaps is not None and not snaps.empty:
            df = df.join(snapshots_to_daily(snaps, df.index))
        df = _add_fundamental_ratios(df)

        df = df.join(self.macro_daily.reindex(df.index))
        df = df.join(self.vix_features.reindex(df.index))

        sent = self.sentiment_by_ticker.get(ticker)
        if sent is not None:
            df = df.join(sent.reindex(df.index))

        # Dimensiones sin datos aún (p.ej. macro sin API key, sentimiento en fase
        # posterior) quedan NaN: HistGradientBoosting las maneja nativamente.
        missing = [c for c in ALL_FEATURES if c not in df.columns]
        if missing:
            df[missing] = np.nan

        keep = ALL_FEATURES + [c for c in AUX_COLUMNS if c not in ALL_FEATURES]
        return df[[c for c in dict.fromkeys(keep)]]


def build_training_dataset(log=print) -> pd.DataFrame:
    ensure_dirs()
    asm = FeatureAssembler(log=log)
    frames = []
    for row in asm.universe.itertuples():
        df = asm.ticker_frame(row.ticker, row.yf_ticker)
        if df is None:
            continue
        df = df.copy()
        df["label"] = label_future_max_return(
            df["close"], settings.prediction_horizon_days, settings.min_return_target
        )
        weekly = df[df.index.weekday == 4].dropna(subset=["label"])  # viernes etiquetados
        if weekly.empty:
            continue
        weekly = weekly.reset_index().rename(columns={"index": "date"})
        weekly["ticker"] = row.ticker
        frames.append(weekly)
    if not frames:
        raise RuntimeError("No se pudo construir ninguna fila de entrenamiento")
    dataset = pd.concat(frames, ignore_index=True)
    dataset.to_parquet(dataset_path(), index=False)
    log(f"  dataset: {len(dataset):,} filas | positivos: {dataset['label'].mean():.1%}")
    return dataset


def build_inference_frame(log=print) -> pd.DataFrame:
    """Última fila de features por ticker (estado de hoy) para el screener."""
    ensure_dirs()
    asm = FeatureAssembler(log=log)
    rows = []
    for row in asm.universe.itertuples():
        df = asm.ticker_frame(row.ticker, row.yf_ticker)
        if df is None or df.empty:
            continue
        last = df.iloc[[-1]].reset_index().rename(columns={"index": "date"})
        last["ticker"] = row.ticker
        last["yf_ticker"] = row.yf_ticker
        last["company"] = row.company
        last["sector"] = row.sector
        rows.append(last)
    if not rows:
        raise RuntimeError("No se pudo construir la matriz de inferencia")
    latest = pd.concat(rows, ignore_index=True)
    latest.to_parquet(latest_path(), index=False)
    return latest

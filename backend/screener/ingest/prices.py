"""Descarga incremental de precios diarios (yfinance) al data lake parquet.

Un archivo por ticker en data/raw/prices/{ticker}.parquet con columnas:
date, open, high, low, close, volume. Precios ajustados (auto_adjust=True)
de forma consistente entre backfill e incrementales.
"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from screener.config import ensure_dirs, settings

VIX_TICKER = "^VIX"
_CHUNK = 50
_COLS = ["open", "high", "low", "close", "volume"]


def price_path(ticker: str) -> Path:
    return settings.raw_dir / "prices" / f"{ticker.replace('^', '')}.parquet"


def load_prices(ticker: str) -> pd.DataFrame | None:
    path = price_path(ticker)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    out = out.reset_index()
    date_col = next(c for c in out.columns if str(c).lower() in ("date", "index"))
    out = out.rename(columns={date_col: "date"})
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    out = out[["date"] + [c for c in _COLS if c in out.columns]]
    return out.dropna(subset=["close"]).sort_values("date")


def _append(ticker: str, new_rows: pd.DataFrame) -> None:
    if new_rows.empty:
        return
    existing = load_prices(ticker)
    if existing is not None:
        new_rows = (
            pd.concat([existing, new_rows])
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )
    new_rows.to_parquet(price_path(ticker), index=False)


def update_prices(tickers: list[str], log=print) -> None:
    """Descarga lo que falte para cada ticker (full backfill la primera vez)."""
    ensure_dirs()
    all_tickers = list(dict.fromkeys(tickers + [VIX_TICKER]))

    # Agrupa por fecha de inicio requerida para poder descargar en lote
    by_start: dict[str, list[str]] = {}
    today = date.today()
    for t in all_tickers:
        existing = load_prices(t)
        if existing is None or existing.empty:
            start = settings.price_history_start
        else:
            last = existing["date"].max().date()
            if last >= today - timedelta(days=1):
                continue
            start = (last + timedelta(days=1)).isoformat()
        by_start.setdefault(start, []).append(t)

    for start, group in by_start.items():
        for i in range(0, len(group), _CHUNK):
            chunk = group[i : i + _CHUNK]
            log(f"  precios: {len(chunk)} tickers desde {start}")
            data = yf.download(
                chunk,
                start=start,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                progress=False,
            )
            if data is None or data.empty:
                continue
            for t in chunk:
                try:
                    df_t = data[t] if isinstance(data.columns, pd.MultiIndex) else data
                except KeyError:
                    continue
                if df_t.dropna(how="all").empty:
                    continue
                _append(t, _normalize(df_t))


def load_close_matrix(tickers: list[str]) -> pd.DataFrame:
    """Matriz fecha x ticker de precios de cierre (para screener/backtest)."""
    frames = {}
    for t in tickers:
        df = load_prices(t)
        if df is not None and not df.empty:
            frames[t] = df.set_index("date")["close"]
    return pd.DataFrame(frames).sort_index()

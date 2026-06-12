"""Indicadores técnicos diarios (11 features) + columnas auxiliares del screener.

Todos los indicadores usan exclusivamente datos hasta el día t (sin futuro):
medias móviles, osciladores y momentum sobre la serie ya cerrada.
"""
import numpy as np
import pandas as pd


def compute_technical(prices: pd.DataFrame) -> pd.DataFrame:
    """`prices`: columnas date, open, high, low, close, volume. Devuelve un
    DataFrame indexado por fecha con las 11 features técnicas + auxiliares."""
    df = prices.set_index("date").sort_index()
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]

    out = pd.DataFrame(index=df.index)

    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    out["price_vs_sma50"] = close / sma50 - 1
    out["price_vs_sma200"] = close / sma200 - 1
    out["sma50_vs_sma200"] = sma50 / sma200 - 1

    # MACD (12-26-9), histograma normalizado por precio para ser comparable entre tickers
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    out["macd_hist_norm"] = (macd - signal) / close

    # RSI 14 (suavizado de Wilder)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi_14"] = 100 - 100 / (1 + rs)

    # Williams %R 14
    hh = high.rolling(14).max()
    ll = low.rolling(14).min()
    out["williams_r_14"] = -100 * (hh - close) / (hh - ll).replace(0, np.nan)

    # Momentum a 1, 3 y 6 meses
    out["ret_21d"] = close.pct_change(21)
    out["ret_63d"] = close.pct_change(63)
    out["ret_126d"] = close.pct_change(126)

    # Volatilidad realizada anualizada (21d)
    out["vol_21d"] = close.pct_change().rolling(21).std() * np.sqrt(252)

    # Actividad de volumen reciente vs trimestre
    out["volume_ratio"] = volume.rolling(5).mean() / volume.rolling(63).mean()

    # Auxiliares (no son features del modelo)
    out["close"] = close
    out["sma200"] = sma200
    out["dollar_volume_20d"] = (close * volume).rolling(20).mean()
    return out

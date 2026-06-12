"""Features de régimen de volatilidad (4) derivadas del VIX: filtro dinámico
de aversión al riesgo. Son las mismas para todos los tickers en cada fecha.
"""
import pandas as pd


def compute_vix_features(vix_prices: pd.DataFrame) -> pd.DataFrame:
    vix = vix_prices.set_index("date").sort_index()["close"]
    out = pd.DataFrame(index=vix.index)
    out["vix_level"] = vix
    out["vix_change_5d"] = vix.pct_change(5)
    out["vix_vs_sma50"] = vix / vix.rolling(50).mean() - 1
    # percentil del nivel actual dentro del último año: 1.0 = pánico extremo
    out["vix_pct_252d"] = vix.rolling(252).rank(pct=True)
    return out

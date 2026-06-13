"""Universo de inversión: S&P 500 + NASDAQ 100, con sector y CIK de la SEC.

El resultado se cachea en data/raw/universe.parquet. Los tickers se normalizan
al formato de yfinance (BRK.B -> BRK-B); el mapeo a CIK usa el formato SEC (punto).

El universo se refresca periódicamente (`refresh_universe`) para seguir las
altas/bajas de los índices; el refresco es tolerante a fallos (si Wikipedia no
responde, conserva el cache) y reporta qué tickers entraron y salieron.
"""
import time
from io import StringIO

import pandas as pd
import requests

from screener.config import ensure_dirs, settings

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NDX_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_HEADERS = {"User-Agent": "Mozilla/5.0 (personal stock screener)"}


def _read_wiki_tables(url: str) -> list[pd.DataFrame]:
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return pd.read_html(StringIO(resp.text))


def _fetch_sp500() -> pd.DataFrame:
    for table in _read_wiki_tables(SP500_URL):
        cols = {str(c).strip() for c in table.columns}
        if "Symbol" in cols and "Security" in cols:
            df = table.rename(
                columns={"Symbol": "ticker", "Security": "company", "GICS Sector": "sector"}
            )[["ticker", "company", "sector"]]
            df["in_sp500"] = True
            return df
    raise RuntimeError("No se encontró la tabla de constituyentes del S&P 500 en Wikipedia")


def _fetch_ndx() -> pd.DataFrame:
    for table in _read_wiki_tables(NDX_URL):
        cols = [str(c).strip() for c in table.columns]
        ticker_col = next((c for c in cols if c in ("Ticker", "Symbol", "Ticker symbol")), None)
        company_col = next((c for c in cols if c in ("Company", "Security")), None)
        if ticker_col and company_col and len(table) > 50:
            sector_col = next((c for c in cols if "Sector" in c), None)
            df = table.rename(
                columns={ticker_col: "ticker", company_col: "company"}
                | ({sector_col: "sector"} if sector_col else {})
            )
            if "sector" not in df.columns:
                df["sector"] = None
            df = df[["ticker", "company", "sector"]]
            df["in_ndx"] = True
            return df
    raise RuntimeError("No se encontró la tabla de constituyentes del NASDAQ-100 en Wikipedia")


def _fetch_cik_map() -> pd.DataFrame:
    resp = requests.get(SEC_TICKERS_URL, headers={"User-Agent": settings.sec_user_agent}, timeout=30)
    resp.raise_for_status()
    rows = list(resp.json().values())
    df = pd.DataFrame(rows).rename(columns={"cik_str": "cik", "ticker": "sec_ticker"})
    return df[["sec_ticker", "cik"]]


def build_universe() -> pd.DataFrame:
    """Descarga y consolida el universo. Devuelve el DataFrame y lo persiste."""
    sp500 = _fetch_sp500()
    ndx = _fetch_ndx()
    uni = sp500.merge(ndx, on="ticker", how="outer", suffixes=("", "_ndx"))
    uni["company"] = uni["company"].fillna(uni.pop("company_ndx"))
    if "sector_ndx" in uni.columns:
        uni["sector"] = uni["sector"].fillna(uni.pop("sector_ndx"))
    uni["in_sp500"] = uni["in_sp500"].fillna(False).astype(bool)
    uni["in_ndx"] = uni["in_ndx"].fillna(False).astype(bool)

    # Formatos de ticker: SEC usa punto (BRK.B... en realidad BRK-B en company_tickers),
    # Wikipedia usa punto; yfinance usa guion. Conservamos ambos.
    uni["ticker"] = uni["ticker"].str.strip().str.upper()
    uni["yf_ticker"] = uni["ticker"].str.replace(".", "-", regex=False)

    cik = _fetch_cik_map()
    cik["norm"] = cik["sec_ticker"].str.upper().str.replace("-", ".", regex=False)
    uni["norm"] = uni["ticker"].str.replace("-", ".", regex=False)
    uni = uni.merge(cik[["norm", "cik"]].drop_duplicates("norm"), on="norm", how="left").drop(
        columns="norm"
    )
    uni = uni.dropna(subset=["ticker"]).drop_duplicates("ticker").reset_index(drop=True)
    uni["cik"] = uni["cik"].astype("Int64")

    ensure_dirs()
    uni.to_parquet(universe_path(), index=False)
    return uni


def universe_path():
    return settings.raw_dir / "universe.parquet"


def load_universe(refresh: bool = False) -> pd.DataFrame:
    if refresh or not universe_path().exists():
        return build_universe()
    return pd.read_parquet(universe_path())


def refresh_universe(log=print, max_age_days: int = 7, force: bool = False) -> dict:
    """Reconstruye el universo desde Wikipedia/SEC si el cache está viejo.

    Sigue las altas/bajas de los índices hacia adelante. Tolerante a fallos: si
    el scraping falla, conserva el cache vigente (no rompe el pipeline diario).
    Devuelve los tickers que entraron (`added`) y salieron (`removed`).

    Nota: esto mantiene actualizado el universo de SCREENING. NO elimina el sesgo
    de supervivencia del entrenamiento (los constituyentes históricos point-in-time
    no son gratuitos), que sigue siendo una limitación documentada.
    """
    path = universe_path()
    prev = pd.read_parquet(path) if path.exists() else None
    fresh = (
        path.exists()
        and not force
        and (time.time() - path.stat().st_mtime) < max_age_days * 86_400
    )
    if fresh:
        return {"refreshed": False, "added": [], "removed": [], "count": len(prev)}

    try:
        new = build_universe()
    except Exception as exc:  # Wikipedia/SEC caídos: conservar el cache
        log(f"  universo: refresco falló ({exc}); se mantiene el cache previo")
        return {"refreshed": False, "added": [], "removed": [], "error": str(exc)}

    prev_tickers = set(prev["ticker"]) if prev is not None else set()
    new_tickers = set(new["ticker"])
    added = sorted(new_tickers - prev_tickers)
    removed = sorted(prev_tickers - new_tickers)
    if added or removed:
        log(f"  universo: +{len(added)} altas {added[:12]} / -{len(removed)} bajas {removed[:12]}")
    else:
        log(f"  universo: sin cambios ({len(new_tickers)} tickers)")
    return {"refreshed": True, "added": added, "removed": removed, "count": len(new_tickers)}

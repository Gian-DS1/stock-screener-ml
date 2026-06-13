"""Series macroeconómicas de FRED con vintages de ALFRED para PIT.

`get_series_all_releases` devuelve cada observación con su `realtime_start`
(fecha en que ese valor se publicó). Para cada fecha de observación guardamos
la PRIMERA publicación: es el valor que el mercado conocía en ese momento,
inmune a revisiones posteriores.

Salida: data/raw/macro.parquet (long): series, date, realtime_start, value
"""
import pandas as pd

from screener.config import ensure_dirs, settings

# nombre lógico -> serie FRED
SERIES = {
    "fed_funds": "FEDFUNDS",          # tasa efectiva de la FED (mensual)
    "cpi": "CPIAUCSL",                # índice de precios (mensual; YoY se deriva en features)
    "unemployment": "UNRATE",         # desempleo (mensual)
    "treasury_10y": "DGS10",          # rendimiento del Tesoro 10 años (diario)
    "yield_curve_10y2y": "T10Y2Y",    # spread 10a-2a (diario)
    "consumer_sentiment": "UMCSENT",  # sentimiento del consumidor U. Michigan (mensual)
}

# Series diarias de mercado: ALFRED rechaza all_releases (>2000 vintages) y no
# hace falta — nunca se revisan. PIT: disponibles al día siguiente de la sesión.
DAILY_MARKET_SERIES = {"treasury_10y", "yield_curve_10y2y"}


def macro_path():
    return settings.raw_dir / "macro.parquet"


def _fetch_series(fred, name: str, sid: str) -> pd.DataFrame:
    if name in DAILY_MARKET_SERIES:
        s = fred.get_series(sid).dropna()
        return pd.DataFrame({
            "date": s.index,
            "realtime_start": s.index + pd.Timedelta(days=1),
            "value": s.to_numpy(),
        })
    releases = fred.get_series_all_releases(sid).dropna(subset=["value"])
    # primera publicación de cada observación = dato PIT
    return (
        releases.sort_values("realtime_start")
        .drop_duplicates(subset=["date"], keep="first")
        .loc[:, ["date", "realtime_start", "value"]]
    )


def update_macro(log=print) -> pd.DataFrame | None:
    if not settings.fred_api_key:
        log("  macro: FRED_API_KEY no configurada; se omite (features macro quedarán NaN)")
        return None
    from fredapi import Fred

    fred = Fred(api_key=settings.fred_api_key)
    frames = []
    for name, sid in SERIES.items():
        try:
            first = _fetch_series(fred, name, sid)
        except Exception as exc:  # una serie caída no debe tumbar el backfill
            log(f"  macro: fallo en {name} ({sid}): {exc}")
            continue
        first["series"] = name
        frames.append(first)
        log(f"  macro: {name} ({sid}) {len(first)} observaciones")

    if not frames:
        log("  macro: ninguna serie disponible")
        return None
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    out["realtime_start"] = pd.to_datetime(out["realtime_start"])
    out["value"] = out["value"].astype(float)
    ensure_dirs()
    out.to_parquet(macro_path(), index=False)
    return out


def load_macro() -> pd.DataFrame | None:
    path = macro_path()
    if not path.exists():
        return None
    return pd.read_parquet(path)

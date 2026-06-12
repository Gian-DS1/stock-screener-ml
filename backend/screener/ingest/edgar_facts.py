"""Fundamentales Point-In-Time desde SEC EDGAR (API companyfacts XBRL).

Cada hecho conserva su `filed` (fecha real de publicación), que es la clave del
principio PIT: un dato solo existe para el modelo a partir del día en que la SEC
lo recibió. Las empresas etiquetan conceptos con tags distintos, así que cada
concepto lógico tiene una lista ordenada de fallbacks; por empresa se usa el
primer tag con datos para no mezclar definiciones.

Salida: data/raw/fundamentals.parquet (formato long):
  cik, ticker, concept, tag, start, end, value, filed, form, fy, fp
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from screener.config import ensure_dirs, settings
from screener.ingest.sec import sec_get

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# concepto lógico -> (namespace, [tags en orden de preferencia], unidad)
CONCEPTS: dict[str, tuple[str, list[str], str]] = {
    "revenue": ("us-gaap", [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ], "USD"),
    "net_income": ("us-gaap", ["NetIncomeLoss"], "USD"),
    "eps_diluted": ("us-gaap", [
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
    ], "USD/shares"),
    "gross_profit": ("us-gaap", ["GrossProfit"], "USD"),
    "operating_income": ("us-gaap", ["OperatingIncomeLoss"], "USD"),
    "ocf": ("us-gaap", [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ], "USD"),
    "capex": ("us-gaap", [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ], "USD"),
    "dep_amort": ("us-gaap", [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ], "USD"),
    "assets": ("us-gaap", ["Assets"], "USD"),
    "equity": ("us-gaap", [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ], "USD"),
    "cash": ("us-gaap", [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ], "USD"),
    "lt_debt": ("us-gaap", ["LongTermDebtNoncurrent", "LongTermDebt"], "USD"),
    "st_debt": ("us-gaap", [
        "LongTermDebtCurrent",
        "DebtCurrent",
        "ShortTermBorrowings",
    ], "USD"),
    "interest_expense": ("us-gaap", [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestExpenseNonoperating",
    ], "USD"),
    "shares_diluted": ("us-gaap", [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ], "shares"),
    "shares_outstanding": ("dei", ["EntityCommonStockSharesOutstanding"], "shares"),
}


def fundamentals_path():
    return settings.raw_dir / "fundamentals.parquet"


def _extract_company(cik: int, ticker: str, facts_json: dict) -> pd.DataFrame:
    rows: list[dict] = []
    facts = facts_json.get("facts", {})
    for concept, (ns, tags, unit) in CONCEPTS.items():
        ns_facts = facts.get(ns, {})
        for rank, tag in enumerate(tags):
            tag_data = ns_facts.get(tag)
            if not tag_data:
                continue
            unit_items = tag_data.get("units", {}).get(unit)
            if not unit_items:
                continue
            for item in unit_items:
                if item.get("val") is None or not item.get("end") or not item.get("filed"):
                    continue
                rows.append({
                    "cik": cik,
                    "ticker": ticker,
                    "concept": concept,
                    "tag": tag,
                    "tag_rank": rank,
                    "start": item.get("start"),
                    "end": item["end"],
                    "value": float(item["val"]),
                    "filed": item["filed"],
                    "form": item.get("form", ""),
                    "fy": item.get("fy"),
                    "fp": item.get("fp", ""),
                })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    # Para un mismo periodo gana el tag preferido (las empresas migran de tag con
    # los años: combinarlos preserva el histórico completo). Dentro del mismo tag,
    # PIT: conservamos la PRIMERA publicación, lo que se conocía en ese momento;
    # cada fila mantiene su `filed` real así que nunca hay visión futura.
    df = (
        df.sort_values(["tag_rank", "filed"])
        .drop_duplicates(subset=["concept", "start", "end"], keep="first")
        .drop(columns="tag_rank")
        .reset_index(drop=True)
    )
    return df


def _fetch_one(cik: int, ticker: str) -> pd.DataFrame:
    resp = sec_get(COMPANYFACTS_URL.format(cik=cik))
    if resp.status_code != 200:
        return pd.DataFrame()
    return _extract_company(cik, ticker, resp.json())


def update_fundamentals(universe: pd.DataFrame, log=print) -> pd.DataFrame:
    """Descarga companyfacts para todo el universo y reconstruye el parquet."""
    ensure_dirs()
    targets = universe.dropna(subset=["cik"])[["cik", "ticker"]].drop_duplicates("cik")
    frames: list[pd.DataFrame] = []
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_fetch_one, int(row.cik), row.ticker): row.ticker
            for row in targets.itertuples()
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                df = fut.result()
                if not df.empty:
                    frames.append(df)
            except Exception as exc:  # un ticker fallido no debe tumbar el backfill
                log(f"  fundamentales: fallo en {ticker}: {exc}")
            done += 1
            if done % 100 == 0:
                log(f"  fundamentales: {done}/{len(futures)}")

    if not frames:
        raise RuntimeError("EDGAR no devolvió fundamentales para ningún ticker")
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(fundamentals_path(), index=False)
    log(f"  fundamentales: {len(out):,} hechos de {out['ticker'].nunique()} empresas")
    return out


def load_fundamentals() -> pd.DataFrame | None:
    path = fundamentals_path()
    if not path.exists():
        return None
    return pd.read_parquet(path)

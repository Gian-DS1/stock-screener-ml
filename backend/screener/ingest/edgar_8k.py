"""Descarga incremental de reportes 8-K desde el feed de submissions de EDGAR.

El feed reciente (~1000 filings) incluye TODOS los formularios de la empresa
(Form 4 de insiders incluido), así que para el histórico hay que recorrer
también las páginas antiguas (`filings.files`). El texto del documento
principal se guarda truncado: FinBERT solo consume los primeros 512 tokens.

Salida: data/raw/filings_8k.parquet
  cik, ticker, accession, filing_date, items, doc_url, text,
  sent_pos, sent_neg, sent_neu, sent_score (NaN hasta que FinBERT los procese)
"""
import re
import warnings
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# algunos 8-K antiguos son XML; el parser HTML los maneja suficientemente bien
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from screener.config import ensure_dirs, settings
from screener.ingest.sec import sec_get

SUBMISSIONS_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"
_TEXT_CHARS = 4000
_TEXT_WORKERS = 12      # hilos de descarga; el rate limiter compartido topa a 8 req/s
_SAVE_BATCH = 2000      # persistir cada N filings (visibilidad + resiliencia)


def filings_path():
    return settings.raw_dir / "filings_8k.parquet"


def load_filings() -> pd.DataFrame | None:
    path = filings_path()
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _page_to_rows(cik: int, ticker: str, page: dict, known: set[str]) -> list[dict]:
    forms = page.get("form", [])
    rows = []
    for i, form in enumerate(forms):
        if form not in ("8-K", "8-K/A"):
            continue
        accession = page["accessionNumber"][i].replace("-", "")
        if accession in known:
            continue
        filing_date = page["filingDate"][i]
        if filing_date < settings.price_history_start:
            continue
        doc = page.get("primaryDocument", [""] * len(forms))[i]
        rows.append({
            "cik": cik,
            "ticker": ticker,
            "accession": accession,
            "filing_date": filing_date,
            "items": page.get("items", [""] * len(forms))[i],
            "doc_url": ARCHIVES_URL.format(cik=cik, accession=accession, doc=doc) if doc else "",
        })
    return rows


def _list_company_8k(cik: int, ticker: str, known: set[str], full_history: bool) -> list[dict]:
    resp = sec_get(SUBMISSIONS_URL.format(name=f"CIK{cik:010d}.json"))
    if resp.status_code != 200:
        return []
    data = resp.json()
    recent = data.get("filings", {}).get("recent", {})
    rows = _page_to_rows(cik, ticker, recent, known)
    if full_history:
        for extra in data.get("filings", {}).get("files", []):
            resp = sec_get(SUBMISSIONS_URL.format(name=extra["name"]))
            if resp.status_code == 200:
                rows += _page_to_rows(cik, ticker, resp.json(), known)
    return rows


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
    return text[:_TEXT_CHARS]


def _download_text(row: dict) -> str:
    if not row["doc_url"]:
        return ""
    try:
        resp = sec_get(row["doc_url"])
        if resp.status_code != 200:
            return ""
        return _extract_text(resp.text)
    except Exception:
        return ""


def update_8k_filings(universe: pd.DataFrame, log=print, progress=None) -> pd.DataFrame | None:
    """Añade los 8-K nuevos de cada empresa del universo (incremental)."""
    ensure_dirs()
    existing = load_filings()
    known: set[str] = set(existing["accession"]) if existing is not None else set()
    # el recorrido de páginas históricas se decide POR EMPRESA: una CIK sin
    # filings previos necesita su histórico completo aunque otras ya lo tengan
    known_ciks: set[int] = (
        set(existing["cik"].astype(int)) if existing is not None and not existing.empty else set()
    )

    targets = universe.dropna(subset=["cik"])[["cik", "ticker"]].drop_duplicates("cik")
    new_rows: list[dict] = []
    for n, row in enumerate(targets.itertuples(), 1):
        try:
            full_history = int(row.cik) not in known_ciks
            new_rows += _list_company_8k(int(row.cik), row.ticker, known, full_history)
        except Exception as exc:
            log(f"  8-K: fallo listando {row.ticker}: {exc}")
        if n % 100 == 0:
            log(f"  8-K: listados {n}/{len(targets)} ({len(new_rows)} nuevos)")
            if progress:
                progress.update("Listando 8-K por empresa", n, len(targets))

    if not new_rows:
        log("  8-K: sin filings nuevos")
        return existing

    # Descarga de texto en paralelo: el rate limiter compartido garantiza <=8 req/s
    # (límite SEC), pero solapar la latencia de red lleva el throughput real cerca
    # de ese tope (~3-4x vs secuencial). Se persiste por lotes: visibilidad +
    # resiliencia (un corte no obliga a re-descargar lo ya hecho).
    total = len(new_rows)
    log(f"  8-K: descargando texto de {total} filings nuevos (paralelo)...")
    accumulated = existing
    done = 0
    for batch_start in range(0, total, _SAVE_BATCH):
        batch = new_rows[batch_start : batch_start + _SAVE_BATCH]
        with ThreadPoolExecutor(max_workers=_TEXT_WORKERS) as pool:
            texts = list(pool.map(_download_text, batch))
        for row, text in zip(batch, texts):
            row["text"] = text
        done += len(batch)
        accumulated = _persist_batch(accumulated, batch)
        log(f"  8-K: texto {done}/{total} (guardado parcial: {len(accumulated):,} filings)")
        if progress:
            progress.update("Descargando texto de 8-K", done, total)

    log(f"  8-K: total {len(accumulated):,} filings de {accumulated['ticker'].nunique()} empresas")
    return accumulated


def _persist_batch(existing: pd.DataFrame | None, batch: list[dict]) -> pd.DataFrame:
    new_df = pd.DataFrame(batch)
    new_df["filing_date"] = pd.to_datetime(new_df["filing_date"])
    for col in ("sent_pos", "sent_neg", "sent_neu", "sent_score"):
        new_df[col] = np.nan
    out = pd.concat([existing, new_df], ignore_index=True) if existing is not None else new_df
    out = out.drop_duplicates("accession").sort_values(["ticker", "filing_date"]).reset_index(drop=True)
    out.to_parquet(filings_path(), index=False)
    return out

"""Sentimiento de reportes 8-K con FinBERT + features diarias con lag PIT.

Dos pasos desacoplados:
1. `process_pending_filings`: pasa FinBERT (ProsusAI/finbert) por los filings
   sin puntuar, en GPU si hay CUDA. sent_score = P(pos) - P(neg) en [-1, 1].
2. `build_sentiment_daily`: agrega por ticker a frecuencia diaria con un
   REZAGO OBLIGATORIO de 1 día hábil: un 8-K publicado hoy solo es visible
   para el modelo mañana (simula la reacción real del mercado).

Features (5): filings_8k_30d, sent_mean_30d, sent_last, days_since_8k, sent_trend.
"""
import numpy as np
import pandas as pd

from screener.config import ensure_dirs
from screener.features import SENTIMENT_FEATURES
from screener.ingest.edgar_8k import filings_path, load_filings

_BATCH = 32
_MAX_DAYS_SINCE = 90.0


def _load_finbert():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    model.to(device).eval()
    return tokenizer, model, device


def process_pending_filings(log=print) -> None:
    """Puntúa con FinBERT los filings que aún no tienen sentimiento."""
    import torch

    filings = load_filings()
    if filings is None or filings.empty:
        log("  sentimiento: no hay filings descargados")
        return
    pending = filings[filings["sent_score"].isna() & (filings["text"].str.len() > 50)]
    if pending.empty:
        log("  sentimiento: nada pendiente")
        return

    tokenizer, model, device = _load_finbert()
    log(f"  sentimiento: procesando {len(pending):,} filings en {device}")
    # orden de labels de ProsusAI/finbert: positive, negative, neutral
    label_index = {v.lower(): k for k, v in model.config.id2label.items()}
    i_pos, i_neg, i_neu = label_index["positive"], label_index["negative"], label_index["neutral"]

    texts = pending["text"].tolist()
    indices = pending.index.to_numpy()
    results = np.zeros((len(texts), 3))
    with torch.no_grad():
        for start in range(0, len(texts), _BATCH):
            batch = texts[start : start + _BATCH]
            enc = tokenizer(
                batch, truncation=True, max_length=512, padding=True, return_tensors="pt"
            ).to(device)
            probs = torch.softmax(model(**enc).logits, dim=-1).cpu().numpy()
            results[start : start + len(batch), 0] = probs[:, i_pos]
            results[start : start + len(batch), 1] = probs[:, i_neg]
            results[start : start + len(batch), 2] = probs[:, i_neu]
            if (start // _BATCH) % 20 == 0 and start > 0:
                log(f"  sentimiento: {start}/{len(texts)}")

    filings.loc[indices, "sent_pos"] = results[:, 0]
    filings.loc[indices, "sent_neg"] = results[:, 1]
    filings.loc[indices, "sent_neu"] = results[:, 2]
    filings.loc[indices, "sent_score"] = results[:, 0] - results[:, 1]
    filings.to_parquet(filings_path(), index=False)
    log(f"  sentimiento: {len(pending):,} filings puntuados")

    build_sentiment_daily(log=log)


def aggregate_daily(scored: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """Agrega filings puntuados a features diarias por ticker.

    REZAGO PIT: el filing de hoy es visible a partir del siguiente día hábil.
    Función pura (testeable): `scored` requiere ticker, filing_date, sent_score.
    """
    scored = scored.copy()
    scored["effective_date"] = scored["filing_date"] + pd.offsets.BDay(1)

    frames = []
    for ticker, g in scored.groupby("ticker"):
        daily_scores = g.groupby("effective_date")["sent_score"].mean()
        count_events = g.groupby("effective_date").size().astype(float)
        idx = pd.bdate_range(daily_scores.index.min(), end)

        scores = daily_scores.reindex(idx)
        counts = count_events.reindex(idx).fillna(0)

        out = pd.DataFrame(index=idx)
        out["filings_8k_30d"] = counts.rolling("30D").sum()
        out["sent_mean_30d"] = scores.rolling("30D").mean()
        out["sent_last"] = scores.ffill()
        last_date = pd.Series(scores.dropna().index, index=scores.dropna().index).reindex(idx).ffill()
        out["days_since_8k"] = (idx - last_date).dt.days.clip(upper=_MAX_DAYS_SINCE)
        out["sent_trend"] = out["sent_mean_30d"] - scores.rolling("90D").mean()
        out["ticker"] = ticker
        frames.append(out.reset_index().rename(columns={"index": "date"}))

    daily = pd.concat(frames, ignore_index=True)
    return daily[["ticker", "date"] + SENTIMENT_FEATURES]


def build_sentiment_daily(log=print) -> pd.DataFrame | None:
    """Construye y persiste las features diarias desde los filings puntuados."""
    from screener.features.builder import sentiment_daily_path

    ensure_dirs()
    filings = load_filings()
    if filings is None or filings.empty:
        return None
    scored = filings.dropna(subset=["sent_score"])
    if scored.empty:
        return None
    daily = aggregate_daily(scored, pd.Timestamp.today().normalize())
    daily.to_parquet(sentiment_daily_path(), index=False)
    log(f"  sentimiento: features diarias de {daily['ticker'].nunique()} tickers")
    return daily

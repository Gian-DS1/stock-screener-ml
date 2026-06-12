"""Titulares de noticias en vivo (SOLO inferencia/contexto del dashboard).

No hay histórico gratuito profundo de titulares, así que NUNCA entran al
entrenamiento: se muestran en el detalle del ticker con su sentimiento FinBERT
como contexto cualitativo. Fuente: Finnhub (si hay key) con yfinance de respaldo.
"""
import time
from datetime import date, timedelta

import requests

from screener.config import settings

_FINNHUB_URL = "https://finnhub.io/api/v1/company-news"
_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 3600  # 1 hora


def fetch_recent_news(yf_ticker: str, days: int = 14, limit: int = 15) -> list[dict]:
    cached = _CACHE.get(yf_ticker)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    items = _from_finnhub(yf_ticker, days) if settings.finnhub_api_key else _from_yfinance(yf_ticker)
    items = sorted(items, key=lambda x: x["date"], reverse=True)[:limit]
    _score_items(items)
    _CACHE[yf_ticker] = (time.time(), items)
    return items


def _from_finnhub(ticker: str, days: int) -> list[dict]:
    try:
        resp = requests.get(
            _FINNHUB_URL,
            params={
                "symbol": ticker,
                "from": (date.today() - timedelta(days=days)).isoformat(),
                "to": date.today().isoformat(),
                "token": settings.finnhub_api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        return [
            {
                "date": date.fromtimestamp(item["datetime"]).isoformat(),
                "headline": item.get("headline", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
            }
            for item in resp.json()
            if item.get("headline")
        ]
    except Exception:
        return []


def _from_yfinance(ticker: str) -> list[dict]:
    try:
        import yfinance as yf

        items = []
        for item in yf.Ticker(ticker).news or []:
            content = item.get("content", item)
            title = content.get("title", "")
            if not title:
                continue
            pub = str(content.get("pubDate", content.get("displayTime", "")))[:10]
            items.append({
                "date": pub,
                "headline": title,
                "source": (content.get("provider") or {}).get("displayName", "yahoo"),
                "url": ((content.get("canonicalUrl") or {}).get("url", "")),
            })
        return items
    except Exception:
        return []


def _score_items(items: list[dict]) -> None:
    """Sentimiento FinBERT de titulares; si torch no está disponible, se omite."""
    headlines = [i["headline"] for i in items]
    if not headlines:
        return
    try:
        import torch

        from screener.features.sentiment import _load_finbert

        tokenizer, model, device = _load_finbert()
        label_index = {v.lower(): k for k, v in model.config.id2label.items()}
        with torch.no_grad():
            enc = tokenizer(
                headlines, truncation=True, max_length=64, padding=True, return_tensors="pt"
            ).to(device)
            probs = torch.softmax(model(**enc).logits, dim=-1).cpu().numpy()
        for item, p in zip(items, probs):
            item["sentiment"] = round(float(p[label_index["positive"]] - p[label_index["negative"]]), 3)
    except Exception:
        for item in items:
            item["sentiment"] = None

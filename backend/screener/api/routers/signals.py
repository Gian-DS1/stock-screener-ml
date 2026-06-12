"""Señales del screener y datos de detalle por ticker."""
import json
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from screener.db import Signal, get_session
from screener.ingest.news import fetch_recent_news
from screener.ingest.prices import load_prices
from screener.universe import load_universe

router = APIRouter(tags=["signals"])


def _serialize(s: Signal) -> dict:
    return {
        "id": s.id,
        "date": s.date.isoformat(),
        "ticker": s.ticker,
        "company": s.company,
        "sector": s.sector,
        "probability": s.probability,
        "quality_score": s.quality_score,
        "combined_score": s.combined_score,
        "price": s.price,
        "sma200": s.sma200,
        "pct_vs_sma200": s.pct_vs_sma200,
        "status": s.status,
        "shap": json.loads(s.shap_json) if s.shap_json else [],
        "quality_breakdown": json.loads(s.quality_breakdown_json) if s.quality_breakdown_json else {},
    }


@router.get("/signals")
def list_signals(days: int = 30, status: str = "") -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    with get_session() as session:
        query = select(Signal).where(Signal.date >= cutoff)
        if status:
            query = query.where(Signal.status == status)
        query = query.order_by(Signal.date.desc(), Signal.combined_score.desc())
        return [_serialize(s) for s in session.execute(query).scalars().all()]


class StatusUpdate(BaseModel):
    status: str  # new | dismissed | bought


@router.post("/signals/{signal_id}/status")
def update_signal_status(signal_id: int, body: StatusUpdate) -> dict:
    if body.status not in ("new", "dismissed", "bought"):
        raise HTTPException(422, "status inválido")
    with get_session() as session:
        signal = session.get(Signal, signal_id)
        if signal is None:
            raise HTTPException(404, "señal no encontrada")
        signal.status = body.status
        return {"ok": True}


def _yf_ticker(ticker: str) -> str:
    uni = load_universe()
    row = uni[uni["ticker"] == ticker]
    if row.empty:
        return ticker.replace(".", "-")
    return row.iloc[0]["yf_ticker"]


@router.get("/tickers/{ticker}/chart")
def ticker_chart(ticker: str, days: int = 500) -> dict:
    prices = load_prices(_yf_ticker(ticker))
    if prices is None or prices.empty:
        raise HTTPException(404, f"sin precios para {ticker}")
    df = prices.sort_values("date").set_index("date")
    sma200 = df["close"].rolling(200).mean()
    tail = df.tail(days)
    return {
        "dates": [d.date().isoformat() for d in tail.index],
        "close": [round(float(v), 2) for v in tail["close"]],
        "sma200": [None if pd.isna(v) else round(float(v), 2) for v in sma200.reindex(tail.index)],
    }


@router.get("/tickers/{ticker}/news")
def ticker_news(ticker: str) -> list[dict]:
    return fetch_recent_news(_yf_ticker(ticker))

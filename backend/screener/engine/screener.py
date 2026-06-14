"""Motor del screener: convierte predicciones en señales accionables.

Una probabilidad alta es condición NECESARIA pero no suficiente. Filtros de
entrada (todos obligatorios):
1. probabilidad >= umbral óptimo del modelo activo
2. quality score >= gate (calidad + descuento de largo plazo)
3. SMA headroom: precio < SMA200 * 1.05 (la "correa del perro": si ya corre
   5% por delante de su media de 200, el retroceso es inminente -> no comprar)
4. liquidez: volumen medio en dólares (20d) >= mínimo
5. cooldown: sin señal del mismo ticker en los últimos 22 días hábiles,
   y sin posición abierta o cerrada recientemente en ese ticker
6. datos frescos: la fila de inferencia no puede tener más de 5 días hábiles
"""
import json
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import select

from screener.config import settings
from screener.db import Alert, Favorite, Position, Signal, get_session, init_db
from screener.features.builder import build_inference_frame, latest_path
from screener.models.explain import explain_rows
from screener.models.quality import quality_score
from screener.models.registry import load_active_artifact


def _cooldown_blocked_tickers(session, as_of: date) -> set[str]:
    cutoff = (pd.Timestamp(as_of) - pd.offsets.BDay(settings.cooldown_days)).date()
    blocked: set[str] = set()
    recent_signals = session.execute(
        select(Signal.ticker).where(Signal.date >= cutoff)
    ).scalars().all()
    blocked.update(recent_signals)
    open_positions = session.execute(
        select(Position.ticker).where(Position.status == "open")
    ).scalars().all()
    blocked.update(open_positions)
    recently_closed = session.execute(
        select(Position.ticker).where(Position.status == "closed", Position.closed_at >= cutoff)
    ).scalars().all()
    blocked.update(recently_closed)
    return blocked


def generate_signals(log=print) -> list[dict]:
    init_db()
    artifact = load_active_artifact()
    features = artifact["feature_names"]
    threshold = artifact["threshold"]

    latest = build_inference_frame(log=log)
    latest["date"] = pd.to_datetime(latest["date"])

    probs = artifact["model"].predict_proba(latest[features].to_numpy(dtype=float))[:, 1]
    latest["probability"] = probs
    q_score, q_breakdown = quality_score(latest)
    latest["quality_score"] = q_score

    freshness_cutoff = pd.Timestamp.today().normalize() - pd.offsets.BDay(5)
    passes = (
        (latest["probability"] >= threshold)
        & (latest["quality_score"] >= settings.quality_gate)
        & latest["sma200"].notna()
        & (latest["close"] < latest["sma200"] * settings.sma_headroom)
        & (latest["dollar_volume_20d"] >= settings.min_dollar_volume)
        & (latest["date"] >= freshness_cutoff)
    )
    candidates = latest[passes].copy()
    log(
        f"  screener: {len(latest)} tickers | prob>=umbral: {(latest['probability'] >= threshold).sum()} "
        f"| tras filtros: {len(candidates)}"
    )
    if candidates.empty:
        return []

    candidates["combined_score"] = candidates["probability"] * candidates["quality_score"] / 100
    candidates = candidates.sort_values("combined_score", ascending=False)
    explanations = explain_rows(artifact, candidates, top_k=8)
    breakdown_rows = q_breakdown.loc[candidates.index]

    created: list[dict] = []
    with get_session() as session:
        blocked = _cooldown_blocked_tickers(session, date.today())
        favorites = set(session.execute(select(Favorite.ticker)).scalars().all())
        for (idx, row), shap_top in zip(candidates.iterrows(), explanations):
            if row["ticker"] in blocked:
                continue
            signal_date = row["date"].date()
            exists = session.execute(
                select(Signal.id).where(Signal.date == signal_date, Signal.ticker == row["ticker"])
            ).scalar()
            if exists:
                continue
            signal = Signal(
                date=signal_date,
                ticker=row["ticker"],
                company=row.get("company"),
                sector=row.get("sector"),
                probability=round(float(row["probability"]), 4),
                quality_score=round(float(row["quality_score"]), 1),
                combined_score=round(float(row["combined_score"]), 4),
                price=float(row["close"]),
                sma200=float(row["sma200"]),
                pct_vs_sma200=float(row["close"] / row["sma200"] - 1),
                shap_json=json.dumps(shap_top),
                quality_breakdown_json=json.dumps(
                    {k: round(float(v), 2) for k, v in breakdown_rows.loc[idx].items()}
                ),
            )
            session.add(signal)
            is_fav = row["ticker"] in favorites
            session.add(Alert(
                type="FAVORITA_SENAL" if is_fav else "NUEVA_SENAL",
                ticker=row["ticker"],
                message=(
                    (f"⭐ Tu favorita {row['ticker']} disparó señal de compra "
                     if is_fav else f"Nueva oportunidad: {row['ticker']} ")
                    + f"(prob {row['probability']:.0%}, calidad {row['quality_score']:.0f}, "
                    f"{row['close'] / row['sma200'] - 1:+.1%} vs SMA200)"
                ),
                severity="warning" if is_fav else "info",
            ))
            created.append({"ticker": row["ticker"], "probability": float(row["probability"])})

    log(f"  screener: {len(created)} señales nuevas emitidas")
    return created


def _watchlist_reasons(row, threshold: float) -> list[str]:
    """Por qué una empresa de calidad NO disparó señal (en lenguaje simple)."""
    reasons: list[str] = []
    if row["probability"] < threshold:
        reasons.append(
            f"El modelo aún no ve momento: probabilidad {row['probability']:.0%} "
            f"(necesita ≥ {threshold:.0%})"
        )
    if pd.notna(row["sma200"]) and row["close"] >= row["sma200"] * settings.sma_headroom:
        reasons.append(
            f"No está en descuento: cotiza {row['close'] / row['sma200'] - 1:+.0%} "
            f"sobre su media de 200 días"
        )
    if pd.notna(row.get("dollar_volume_20d")) and row["dollar_volume_20d"] < settings.min_dollar_volume:
        reasons.append("Liquidez por debajo del mínimo")
    if row["quality_score"] < settings.quality_gate:
        reasons.append(
            f"Calidad {row['quality_score']:.0f} por debajo del mínimo ({settings.quality_gate:.0f})"
        )
    return reasons or ["No cumple alguno de los filtros de entrada"]


def build_watchlist(limit: int = 80, log=print) -> list[dict]:
    """Empresas de mayor calidad que NO dispararon señal (en observación).

    Lee la matriz de inferencia ya construida (rápido), puntúa todo el universo
    y devuelve las mejores por calidad que no pasaron los filtros de entrada,
    anotando el motivo. Es lo que captura a líderes como las MAG 7 cuando
    cotizan caros (sin descuento) pero siguen siendo negocios excelentes.
    """
    init_db()
    artifact = load_active_artifact()
    features = artifact["feature_names"]
    threshold = artifact["threshold"]

    if not latest_path().exists():
        build_inference_frame(log=log)
    latest = pd.read_parquet(latest_path())
    latest["date"] = pd.to_datetime(latest["date"])

    latest["probability"] = artifact["model"].predict_proba(
        latest[features].to_numpy(dtype=float)
    )[:, 1]
    q_score, q_breakdown = quality_score(latest)
    latest["quality_score"] = q_score
    latest["combined_score"] = latest["probability"] * latest["quality_score"] / 100

    fired = (
        (latest["probability"] >= threshold)
        & (latest["quality_score"] >= settings.quality_gate)
        & latest["sma200"].notna()
        & (latest["close"] < latest["sma200"] * settings.sma_headroom)
        & (latest["dollar_volume_20d"] >= settings.min_dollar_volume)
    )
    watch = latest[~fired].sort_values("quality_score", ascending=False).head(limit).copy()
    if watch.empty:
        return []

    explanations = explain_rows(artifact, watch, top_k=8)
    breakdown_rows = q_breakdown.loc[watch.index]

    out: list[dict] = []
    for (idx, row), shap_top in zip(watch.iterrows(), explanations):
        sma200 = float(row["sma200"]) if pd.notna(row["sma200"]) else None
        out.append({
            "id": 0,  # no persistido: ítem de observación, no señal
            "date": row["date"].date().isoformat(),
            "ticker": row["ticker"],
            "company": row.get("company"),
            "sector": row.get("sector"),
            "probability": round(float(row["probability"]), 4),
            "quality_score": round(float(row["quality_score"]), 1),
            "combined_score": round(float(row["combined_score"]), 4),
            "price": float(row["close"]),
            "sma200": sma200,
            "pct_vs_sma200": (float(row["close"] / row["sma200"] - 1) if sma200 else None),
            "status": "watch",
            "shap": shap_top,
            "quality_breakdown": {k: round(float(v), 2) for k, v in breakdown_rows.loc[idx].items()},
            "reasons": _watchlist_reasons(row, threshold),
        })
    return out

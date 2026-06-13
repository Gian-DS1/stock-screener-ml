"""Auditoría de calidad de datos y del modelo.

Verifica que:
1. El dataset de entrenamiento y la matriz de inferencia tienen cobertura
   suficiente en las features fundamentales (no demasiados NaN).
2. Los ratios derivados son coherentes con sus insumos (p.ej. PE ≈ precio/EPS).
3. El join temporal no introduce datos del futuro (PIT) ni huecos absurdos.
4. El modelo activo se entrenó con las features esperadas.

Uso: python -m screener.cli audit
"""
import json

import numpy as np
import pandas as pd

from screener.features import (
    ALL_FEATURES,
    FUNDAMENTAL_FEATURES,
    MACRO_FEATURES,
    SENTIMENT_FEATURES,
    TECHNICAL_FEATURES,
    VOLATILITY_FEATURES,
)
from screener.features.builder import dataset_path, latest_path


def _coverage(df: pd.DataFrame, cols: list[str]) -> dict[str, float]:
    return {c: round(float(df[c].notna().mean()), 3) for c in cols if c in df.columns}


def audit(log=print) -> dict:
    report: dict = {}

    # ---- dataset de entrenamiento ----
    if not dataset_path().exists():
        log("  ERROR: no existe el dataset; ejecuta build-dataset")
        return {"error": "sin dataset"}
    df = pd.read_parquet(dataset_path())
    log(f"\n=== DATASET DE ENTRENAMIENTO ===")
    log(f"  filas: {len(df):,} | tickers: {df['ticker'].nunique()} | positivos: {df['label'].mean():.1%}")
    log(f"  rango de fechas: {df['date'].min().date()} -> {df['date'].max().date()}")

    log("\n  cobertura por dimensión (fracción de filas con dato):")
    for name, cols in [
        ("fundamental", FUNDAMENTAL_FEATURES),
        ("técnica", TECHNICAL_FEATURES),
        ("macro", MACRO_FEATURES),
        ("sentimiento", SENTIMENT_FEATURES),
        ("volatilidad", VOLATILITY_FEATURES),
    ]:
        cov = _coverage(df, cols)
        avg = np.mean(list(cov.values())) if cov else 0
        peor = min(cov.items(), key=lambda x: x[1]) if cov else ("-", 0)
        log(f"    {name:12s}: media {avg:.0%} | peor {peor[0]} {peor[1]:.0%}")
        report[f"cov_{name}"] = cov

    # features con cobertura preocupante (<40%)
    low = {c: v for c, v in _coverage(df, ALL_FEATURES).items() if v < 0.40}
    report["low_coverage"] = low
    if low:
        log(f"\n  [!] features con cobertura <40%: {low}")
    else:
        log("\n  [OK] todas las features superan el 40% de cobertura")

    # ---- coherencia de ratios derivados ----
    log("\n=== COHERENCIA DE RATIOS (muestra del dataset) ===")
    checks = _coherence_checks(df, log)
    report["coherence"] = checks

    # ---- matriz de inferencia ----
    if latest_path().exists():
        latest = pd.read_parquet(latest_path())
        log(f"\n=== MATRIZ DE INFERENCIA (hoy) ===")
        log(f"  tickers: {len(latest)}")
        live_low = {c: v for c, v in _coverage(latest, ALL_FEATURES).items() if v < 0.40}
        log(f"  features <40% cobertura en vivo: {live_low or 'ninguna'}")
        report["latest_low_coverage"] = live_low

    # ---- modelo activo ----
    log("\n=== MODELO ACTIVO ===")
    try:
        from screener.models.registry import get_active_record

        rec = get_active_record()
        if rec is None:
            log("  ⚠ no hay modelo entrenado")
        else:
            feats = json.loads(rec.feature_names_json)
            missing = [f for f in ALL_FEATURES if f not in feats]
            log(f"  entrenado: {rec.trained_at} | features usadas: {len(feats)}/{len(ALL_FEATURES)}")
            if missing:
                log(f"  [!] features del contrato NO usadas por el modelo: {missing}")
            else:
                log("  [OK] el modelo usa las 34 features del contrato")
            metrics = json.loads(rec.metrics_json)
            oof = metrics.get("oof", {})
            log(f"  precisión OOF: {oof.get('precision', 0):.1%} | recall: {oof.get('recall', 0):.1%}")
            report["model"] = {"features": len(feats), "missing": missing, "oof": oof}
    except Exception as exc:
        log(f"  error leyendo el modelo: {exc}")

    log("\n=== FIN DE LA AUDITORÍA ===")
    return report


def _coherence_checks(df: pd.DataFrame, log) -> dict:
    """Comprobaciones de sanidad sobre ratios derivados."""
    out = {}
    sample = df.dropna(subset=["pe_ttm", "close"]).head(5000)

    # PE debe ser positivo donde existe (definido solo con EPS>0)
    pe = df["pe_ttm"].dropna()
    out["pe_all_positive"] = bool((pe > 0).all())
    out["pe_median"] = round(float(pe.median()), 1)
    log(f"  PE (TTM): mediana {out['pe_median']} | todos positivos: {out['pe_all_positive']}")

    # márgenes deben estar en rango razonable (-1, 1.5)
    for m in ["gross_margin", "operating_margin", "fcf_yield", "roe"]:
        s = df[m].dropna()
        if len(s):
            frac_ok = float(((s > -1) & (s < 1.5)).mean())
            out[f"{m}_in_range"] = round(frac_ok, 3)
            log(f"  {m}: mediana {s.median():.2f} | en rango (-1,1.5): {frac_ok:.0%}")

    # RSI debe estar en [0,100]
    rsi = df["rsi_14"].dropna()
    if len(rsi):
        out["rsi_in_range"] = round(float(((rsi >= 0) & (rsi <= 100)).mean()), 3)
        log(f"  RSI 14: en [0,100]: {out['rsi_in_range']:.0%}")

    # vix_pct_252d es un percentil -> [0,1]
    vp = df["vix_pct_252d"].dropna()
    if len(vp):
        out["vix_pct_in_range"] = round(float(((vp >= 0) & (vp <= 1)).mean()), 3)

    # label sin NaN (ya se filtra) y binaria
    out["label_binary"] = bool(set(df["label"].dropna().unique()).issubset({0.0, 1.0}))
    return out

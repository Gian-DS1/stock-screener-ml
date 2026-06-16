"""Monitoreo de degradación silenciosa del modelo.

- Deriva de DATOS: la matriz de inferencia es una sección transversal de UN día.
  Las features de mercado (macro + VIX) valen lo mismo para todas las empresas
  ese día, así que compararlas por KS contra el panel multi-anual de
  entrenamiento da deriva ~siempre (KS≈1) por construcción: es un artefacto, no
  deriva real. Por eso:
    * El share de deriva se mide SOLO sobre features por-empresa (sección
      transversal), donde KS sí compara peras con peras.
    * Las de mercado se evalúan como NOVEDAD DE RÉGIMEN: ¿el valor de hoy cae
      fuera del rango visto en entrenamiento? El modelo estaría extrapolando en
      sus inputs más importantes. Se reporta aparte (no infla el share).
- Deriva de PREDICCIONES: KS de las probabilidades actuales vs las OOF del
  entrenamiento. Un cambio estructural del mercado mueve esta distribución
  antes de que las pérdidas lo hagan evidente.

Resultados en drift_reports + alerta en el dashboard si hay deriva.
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from screener.features import MACRO_FEATURES, VOLATILITY_FEATURES

_DRIFT_SHARE_THRESHOLD = 0.30  # fracción de features con deriva que dispara la alarma
_KS_PVALUE = 0.01
_KS_MIN_STAT = 0.1  # con N grande el p-value es hipersensible: exigir efecto mínimo

# Features iguales para todas las empresas en un día dado (macro + VIX). En la
# foto de inferencia son una constante: no admiten KS distribucional, se evalúan
# por rango/novedad de régimen.
MARKET_WIDE_FEATURES = set(MACRO_FEATURES) | set(VOLATILITY_FEATURES)


def _ks_column_drift(reference: pd.DataFrame, current: pd.DataFrame, columns) -> tuple[float, dict, int]:
    per_column: dict[str, dict] = {}
    drifted = 0
    evaluated = 0
    for col in columns:
        ref = reference[col].dropna().to_numpy()
        cur = current[col].dropna().to_numpy()
        if len(ref) < 30 or len(cur) < 30:
            continue
        stat, pvalue = ks_2samp(ref, cur)
        is_drift = bool(pvalue < _KS_PVALUE and stat > _KS_MIN_STAT)
        per_column[col] = {"ks": round(float(stat), 4), "p": float(pvalue), "drift": is_drift}
        evaluated += 1
        drifted += is_drift
    share = drifted / evaluated if evaluated else 0.0
    return share, per_column, evaluated


def _market_wide_novelty(reference: pd.DataFrame, current: pd.DataFrame, columns) -> dict:
    """Para features de mercado (constantes en la foto de hoy): ¿el valor de hoy
    está fuera del rango visto en entrenamiento? Si sí, el modelo extrapola."""
    out: dict[str, dict] = {}
    for col in columns:
        ref = reference[col].dropna().to_numpy()
        cur = current[col].dropna().to_numpy()
        if len(ref) == 0 or len(cur) == 0:
            continue
        value = float(np.median(cur))  # robusto: deberían ser todos iguales
        lo, hi = float(np.min(ref)), float(np.max(ref))
        out[col] = {
            "value": value,
            "ref_min": lo,
            "ref_max": hi,
            "out_of_range": bool(value < lo or value > hi),
        }
    return out


def recent_cross_section(dataset: pd.DataFrame, n_dates: int) -> pd.DataFrame:
    """Ventana reciente: filas de las últimas `n_dates` fechas-snapshot. La
    deriva se mide contra el régimen RECIENTE de entrenamiento, no contra los
    años en bloque (que harían que cualquier día normal parezca derivado)."""
    last_dates = sorted(pd.to_datetime(dataset["date"]).unique())[-n_dates:]
    return dataset[pd.to_datetime(dataset["date"]).isin(last_dates)]


def compute_data_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    market_wide: set[str] | None = None,
    market_wide_reference: pd.DataFrame | None = None,
) -> tuple[float, dict]:
    """Deriva de datos honesta: KS solo sobre features por-empresa (contra la
    ventana reciente `reference`); las de mercado se reportan como novedad de
    régimen contra el rango COMPLETO de entrenamiento (`market_wide_reference`,
    si se pasa) sin inflar el share."""
    market_wide = MARKET_WIDE_FEATURES if market_wide is None else set(market_wide)
    range_ref = reference if market_wide_reference is None else market_wide_reference
    cols = list(reference.columns)
    cross_sectional = [c for c in cols if c not in market_wide]
    wide = [c for c in cols if c in market_wide]

    share, per_column, evaluated = _ks_column_drift(reference, current, cross_sectional)
    novelty = _market_wide_novelty(range_ref, current, wide)

    detail = {
        "method": "ks-cross-sectional",
        "per_column": per_column,
        "evaluated": evaluated,
        "market_wide": novelty,
    }
    return share, detail


_RECENT_WINDOW_DATES = 60  # fechas-snapshot recientes que forman la referencia


def run_drift_checks(log=print) -> dict:
    from screener.db import Alert, DriftReport, get_session, init_db
    from screener.features.builder import dataset_path, latest_path
    from screener.models.registry import load_active_artifact

    init_db()
    artifact = load_active_artifact()
    features = artifact["feature_names"]
    # Rango de entrenamiento COMPLETO para la novedad de mercado (¿extrapola?).
    full_reference = artifact["reference_features"][features]

    # Referencia transversal = VENTANA RECIENTE del dataset (no los años en
    # bloque). Si el dataset no está en disco, cae a la huella completa.
    if dataset_path().exists():
        dataset = pd.read_parquet(dataset_path())
        recent = recent_cross_section(dataset, _RECENT_WINDOW_DATES)[features]
        log(f"  referencia drift: ventana reciente de {_RECENT_WINDOW_DATES} fechas ({len(recent):,} filas)")
    else:
        recent = full_reference
        log("  referencia drift: huella completa (dataset.parquet no encontrado)")

    if not latest_path().exists():
        raise FileNotFoundError("No existe la matriz de inferencia: ejecuta `score` primero")
    current = pd.read_parquet(latest_path())[features]

    # --- deriva de datos (solo features por-empresa cuentan al share) ---
    data_share, detail = compute_data_drift(
        recent, current, market_wide_reference=full_reference
    )
    data_drifted = data_share > _DRIFT_SHARE_THRESHOLD
    log(f"  drift datos: {data_share:.0%} de features por-empresa derivadas "
        f"(de {detail['evaluated']}) -> {'DERIVA' if data_drifted else 'estable'}")

    # novedad de régimen en features de mercado: no infla el share, pero se avisa
    novel = [c for c, v in detail["market_wide"].items() if v["out_of_range"]]
    if novel:
        log(f"  aviso: macro/VIX fuera del rango de entrenamiento: {', '.join(novel)}")

    # --- deriva de predicciones ---
    probs = artifact["model"].predict_proba(current.to_numpy(dtype=float))[:, 1]
    oof = np.asarray(artifact["oof_probs"])
    stat, pvalue = ks_2samp(oof, probs)
    pred_drifted = bool(pvalue < _KS_PVALUE and stat > 0.15)
    log(f"  drift predicciones: KS={stat:.3f} p={pvalue:.4f} -> {'DERIVA' if pred_drifted else 'estable'}")

    with get_session() as session:
        session.add(DriftReport(
            kind="data", drifted=data_drifted, metric=float(data_share),
            detail_json=json.dumps(detail)[:8000],
        ))
        session.add(DriftReport(
            kind="prediction", drifted=pred_drifted, metric=float(stat),
            detail_json=json.dumps({"ks": float(stat), "p": float(pvalue)}),
        ))
        # Graduado: la deriva de PREDICCIONES es la degradación accionable
        # (el output del modelo se aleja de lo aprendido) -> reentrenar. La de
        # DATOS es esperable por el horizonte de 6 meses del label y no se
        # arregla reentrenando hasta que maduren datos nuevos -> solo aviso.
        if pred_drifted:
            session.add(Alert(
                type="DRIFT",
                message=(
                    "Deriva en las PREDICCIONES del modelo: su output se alejó de lo aprendido. "
                    "Reentrena el modelo y reajusta el umbral antes de confiar en nuevas señales."
                ),
                severity="warning",
            ))
        elif data_drifted or novel:
            parts = []
            if data_drifted:
                parts.append(f"inputs de mercado movidos ({data_share:.0%} de features por-empresa)")
            if novel:
                parts.append(f"macro/VIX fuera del rango de entrenamiento: {', '.join(novel)}")
            session.add(Alert(
                type="REGIMEN",
                message=(
                    f"Aviso ({' · '.join(parts)}). Esperable por el horizonte de 6 meses del label; "
                    f"las predicciones siguen estables, así que reentrenar no ayuda hasta que maduren "
                    f"datos nuevos. Revisa las señales con el contexto habitual."
                ),
                severity="info",
            ))

    return {"data_share": data_share, "prediction_ks": float(stat), "market_novelty": novel}

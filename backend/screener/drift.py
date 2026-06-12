"""Monitoreo de degradación silenciosa del modelo.

- Deriva de DATOS: distribución actual de cada feature vs la huella del
  dataset de entrenamiento (evidently si está disponible; si no, KS test por
  columna con scipy). Drift global si > 30% de las features derivan.
- Deriva de PREDICCIONES: KS de las probabilidades actuales vs las OOF del
  entrenamiento. Un cambio estructural del mercado mueve esta distribución
  antes de que las pérdidas lo hagan evidente.

Resultados en drift_reports + alerta en el dashboard si hay deriva.
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from screener.db import Alert, DriftReport, get_session, init_db
from screener.features.builder import latest_path
from screener.models.registry import load_active_artifact

_DRIFT_SHARE_THRESHOLD = 0.30  # fracción de features con deriva que dispara la alarma
_KS_PVALUE = 0.01
_KS_MIN_STAT = 0.1  # con N grande el p-value es hipersensible: exigir efecto mínimo


def _ks_column_drift(reference: pd.DataFrame, current: pd.DataFrame) -> tuple[float, dict]:
    per_column: dict[str, dict] = {}
    drifted = 0
    evaluated = 0
    for col in reference.columns:
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
    return share, per_column


def _evidently_drift(reference: pd.DataFrame, current: pd.DataFrame) -> tuple[float, dict] | None:
    """Intenta evidently; su API cambia entre versiones, por eso el fallback."""
    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset

        result = Report([DataDriftPreset()]).run(current_data=current, reference_data=reference)
        payload = json.loads(result.json())
        for metric in payload.get("metrics", []):
            metric_id = str(metric.get("metric_id", metric.get("id", "")))
            if "DriftedColumns" in metric_id:
                value = metric.get("value", {})
                share = float(value.get("share", value.get("count", 0)))
                return share, {"engine": "evidently", "metric_id": metric_id}
        return None
    except Exception:
        return None


def run_drift_checks(log=print) -> dict:
    init_db()
    artifact = load_active_artifact()
    features = artifact["feature_names"]
    reference = artifact["reference_features"][features]

    if not latest_path().exists():
        raise FileNotFoundError("No existe la matriz de inferencia: ejecuta `score` primero")
    current = pd.read_parquet(latest_path())[features]

    # --- deriva de datos ---
    evidently_result = _evidently_drift(reference, current)
    if evidently_result is not None:
        data_share, detail = evidently_result
    else:
        data_share, detail = _ks_column_drift(reference, current)
    data_drifted = data_share > _DRIFT_SHARE_THRESHOLD
    log(f"  drift datos: {data_share:.0%} de features derivadas -> {'DERIVA' if data_drifted else 'estable'}")

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
        if data_drifted or pred_drifted:
            which = " y ".join(
                k for k, v in [("datos", data_drifted), ("predicciones", pred_drifted)] if v
            )
            session.add(Alert(
                type="DRIFT",
                message=(
                    f"Deriva detectada en {which}. El mercado se alejó de las condiciones de "
                    f"entrenamiento: reentrena el modelo antes de confiar en nuevas señales."
                ),
                severity="warning",
            ))

    return {"data_share": data_share, "prediction_ks": float(stat)}

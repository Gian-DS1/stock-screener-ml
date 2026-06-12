"""Modelo táctico: clasificador de probabilidad de alcanzar el retorno objetivo.

- HistGradientBoostingClassifier: maneja NaN nativamente (la ausencia de un
  reporte es información, no se imputa).
- Validación cruzada temporal expanding-window con un hueco (gap) igual al
  horizonte de predicción entre train y validación: el modelo nunca ve filas
  cuya etiqueta se solape con el periodo de validación.
- Umbral de decisión: máxima Precisión sujeta a Recall >= recall_floor sobre
  las predicciones out-of-fold agrupadas (filosofía francotirador).
"""
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, precision_recall_curve

from screener.config import settings
from screener.features import ALL_FEATURES
from screener.features.builder import dataset_path

# El horizonte está en días HÁBILES; el gap del CV se aplica en días naturales
_CALENDAR_PER_TRADING = 7 / 5


def _make_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=400,
        learning_rate=0.06,
        max_leaf_nodes=31,
        min_samples_leaf=50,
        l2_regularization=1.0,
        # early stopping interno usa un split ALEATORIO -> fuga temporal. Nunca.
        early_stopping=False,
        random_state=7,
    )


def optimize_threshold(
    y_true: np.ndarray, probs: np.ndarray, recall_floor: float
) -> tuple[float, float, float]:
    """Devuelve (umbral, precisión, recall) maximizando precisión con recall >= floor.

    A igual precisión se prefiere el umbral más alto (más selectivo).
    """
    precision, recall, thresholds = precision_recall_curve(y_true, probs)
    precision, recall = precision[:-1], recall[:-1]  # alineadas con thresholds
    ok = recall >= recall_floor
    if not ok.any():
        raise ValueError(f"Ningún umbral alcanza recall >= {recall_floor}")
    best_prec = precision[ok].max()
    candidates = ok & (precision >= best_prec - 1e-12)
    idx = np.where(candidates)[0][-1]  # thresholds crecientes: el último es el más alto
    return float(thresholds[idx]), float(precision[idx]), float(recall[idx])


def _expanding_folds(dates: pd.Series, n_folds: int, gap: pd.Timedelta):
    unique_dates = np.sort(dates.unique())
    n = len(unique_dates)
    first_val = int(n * 0.4)  # el 40% inicial es solo base de entrenamiento
    edges = np.linspace(first_val, n, n_folds + 1, dtype=int)
    for i in range(n_folds):
        val_dates = unique_dates[edges[i] : edges[i + 1]]
        if len(val_dates) == 0:
            continue
        train_mask = dates < (val_dates[0] - gap)
        val_mask = dates.isin(val_dates)
        if train_mask.sum() == 0 or val_mask.sum() == 0:
            continue
        yield train_mask.to_numpy(), val_mask.to_numpy(), val_dates


def train_tactical_model(log=print) -> dict:
    path = dataset_path()
    if not path.exists():
        raise FileNotFoundError("No existe el dataset: ejecuta `build-dataset` primero")
    df = pd.read_parquet(path).dropna(subset=["label"]).sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    gap = pd.Timedelta(days=int(settings.prediction_horizon_days * _CALENDAR_PER_TRADING) + 7)

    # Solo features con datos en la ventana de entrenamiento más pequeña del CV:
    # una columna sin valores (p.ej. macro sin API key, sentimiento sin backfill)
    # rompe el binning de HGB y no aporta nada. El artefacto registra las usadas.
    unique_dates = np.sort(df["date"].unique())
    base_cutoff = unique_dates[int(len(unique_dates) * 0.4)] - gap
    base = df[df["date"] < base_cutoff]
    features = [f for f in ALL_FEATURES if base[f].dropna().nunique() >= 2]
    dropped = [f for f in ALL_FEATURES if f not in features]
    if dropped:
        log(f"  aviso: {len(dropped)} features sin datos quedan fuera: {dropped}")

    X = df[features].to_numpy(dtype=float)
    y = df["label"].to_numpy(dtype=int)
    base_rate = float(y.mean())
    log(f"  entrenamiento: {len(df):,} filas | {len(features)} features | base rate: {base_rate:.1%}")
    oof_probs = np.full(len(df), np.nan)
    fold_stats = []
    for k, (train_mask, val_mask, val_dates) in enumerate(
        _expanding_folds(df["date"], settings.cv_folds, gap)
    ):
        model = _make_model()
        model.fit(X[train_mask], y[train_mask])
        probs = model.predict_proba(X[val_mask])[:, 1]
        oof_probs[val_mask] = probs
        ap = float(average_precision_score(y[val_mask], probs)) if y[val_mask].any() else None
        fold_stats.append({
            "fold": k,
            "n_train": int(train_mask.sum()),
            "n_val": int(val_mask.sum()),
            "val_start": str(pd.Timestamp(val_dates[0]).date()),
            "val_end": str(pd.Timestamp(val_dates[-1]).date()),
            "avg_precision": ap,
            "val_base_rate": float(y[val_mask].mean()),
        })
        log(f"  fold {k}: train={train_mask.sum():,} val={val_mask.sum():,} AP={ap and round(ap, 3)}")

    oof_mask = ~np.isnan(oof_probs)
    threshold, oof_precision, oof_recall = optimize_threshold(
        y[oof_mask], oof_probs[oof_mask], settings.recall_floor
    )
    n_signals = int((oof_probs[oof_mask] >= threshold).sum())
    log(
        f"  OOF: umbral={threshold:.3f} precisión={oof_precision:.1%} "
        f"recall={oof_recall:.1%} señales={n_signals} (base rate {base_rate:.1%})"
    )

    # métricas por fold al umbral global (estabilidad temporal de la precisión)
    for stat, (train_mask, val_mask, _) in zip(
        fold_stats, _expanding_folds(df["date"], settings.cv_folds, gap)
    ):
        probs = oof_probs[val_mask]
        pred = probs >= threshold
        tp = int(((pred) & (y[val_mask] == 1)).sum())
        stat["precision_at_thr"] = tp / int(pred.sum()) if pred.sum() else None
        stat["recall_at_thr"] = tp / int(y[val_mask].sum()) if y[val_mask].sum() else None
        stat["signals_at_thr"] = int(pred.sum())

    # modelo final: todo el histórico etiquetado
    final_model = _make_model()
    final_model.fit(X, y)

    # importancias globales: media |SHAP| sobre una muestra del entrenamiento
    importances = _shap_importances(final_model, df[features], features)

    metrics = {
        "folds": fold_stats,
        "oof": {
            "threshold": threshold,
            "precision": oof_precision,
            "recall": oof_recall,
            "n_oof": int(oof_mask.sum()),
            "n_signals": n_signals,
            "base_rate": base_rate,
        },
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_path = settings.models_dir / f"tactical_{stamp}.joblib"
    artifact = {
        "model": final_model,
        "feature_names": features,
        "threshold": threshold,
        "horizon_days": settings.prediction_horizon_days,
        "min_return": settings.min_return_target,
        "trained_at": stamp,
        "metrics": metrics,
        # huellas para el monitoreo de drift
        "reference_features": df[features].sample(min(len(df), 20_000), random_state=7),
        "oof_probs": oof_probs[oof_mask],
        "importances": importances,
    }
    joblib.dump(artifact, model_path)

    from screener.models.registry import register_model

    record = register_model(
        model_path=str(model_path),
        threshold=threshold,
        n_samples=len(df),
        metrics_json=json.dumps(metrics),
        importances_json=json.dumps(importances),
    )
    return record


def _shap_importances(
    model, X_df: pd.DataFrame, feature_names: list[str], sample: int = 2000
) -> dict[str, float]:
    try:
        import shap

        Xs = X_df.sample(min(len(X_df), sample), random_state=7)
        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(Xs.to_numpy(dtype=float))
        if isinstance(values, list):  # clasificadores binarios antiguos: [neg, pos]
            values = values[1]
        mean_abs = np.abs(values).mean(axis=0)
        return {f: float(v) for f, v in zip(feature_names, mean_abs)}
    except Exception:
        return {}

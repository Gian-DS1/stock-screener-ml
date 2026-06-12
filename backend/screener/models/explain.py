"""Explicación por señal: qué features empujan la probabilidad (SHAP).

Los valores se calculan en log-odds (salida cruda del árbol); el signo y la
magnitud relativa son lo que el dashboard muestra como "por qué dispara".
"""
import numpy as np
import pandas as pd


def explain_rows(artifact: dict, X: pd.DataFrame, top_k: int = 8) -> list[list[dict]]:
    """Para cada fila devuelve los top_k features por |contribución SHAP|."""
    import shap

    feature_names = artifact["feature_names"]
    explainer = shap.TreeExplainer(artifact["model"])
    values = explainer.shap_values(X[feature_names].to_numpy(dtype=float))
    if isinstance(values, list):
        values = values[1]

    explanations = []
    for i in range(len(X)):
        row = values[i]
        order = np.argsort(np.abs(row))[::-1][:top_k]
        explanations.append([
            {
                "feature": feature_names[j],
                "shap": float(row[j]),
                "value": _safe(X.iloc[i][feature_names[j]]),
            }
            for j in order
        ])
    return explanations


def _safe(v) -> float | None:
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except (TypeError, ValueError):
        return None

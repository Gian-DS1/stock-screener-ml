"""Generación de etiquetas: ¿el retorno máximo en la ventana futura supera el objetivo?

Implementación O(N) con reverse-rolling-max (la "cinta rebobinada"): se invierte
la serie desplazada, se aplica un rolling max y se vuelve a invertir, lo que
equivale a calcular max(close[t+1 .. t+H]) para cada t sin bucles O(N·H).
"""
import numpy as np
import pandas as pd


def label_future_max_return(close: pd.Series, horizon: int, min_return: float) -> pd.Series:
    """1.0 si max(close[t+1..t+horizon]) / close[t] - 1 >= min_return, 0.0 si no.

    NaN cuando no existe ventana futura completa (cola de la serie): esas filas
    no se pueden etiquetar y deben excluirse del entrenamiento.
    """
    fwd = close.shift(-1)  # fwd[t] = close[t+1]
    future_max = (
        fwd.iloc[::-1]
        .rolling(window=horizon, min_periods=horizon)
        .max()
        .iloc[::-1]
    )  # future_max[t] = max(close[t+1 .. t+horizon])
    future_return = future_max / close - 1
    # tolerancia relativa: 115/100-1 produce 0.1499...91 y debe contar como 0.15
    labels = (future_return >= min_return - 1e-9).astype(float)
    labels[future_return.isna()] = np.nan
    return labels

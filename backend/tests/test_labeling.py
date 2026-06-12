"""El labeling vectorizado debe ser EXACTAMENTE equivalente a la definición
de fuerza bruta: label[t] = 1 si max(close[t+1..t+H])/close[t] - 1 >= target.
"""
import numpy as np
import pandas as pd
import pytest

from screener.labeling import label_future_max_return


def brute_force(close: pd.Series, horizon: int, min_return: float) -> pd.Series:
    values = close.to_numpy()
    out = np.full(len(values), np.nan)
    for t in range(len(values)):
        window = values[t + 1 : t + 1 + horizon]
        if len(window) < horizon:
            continue  # sin ventana completa no hay etiqueta
        # misma tolerancia FP que la implementación (semántica: >= matemático)
        out[t] = float(window.max() / values[t] - 1 >= min_return - 1e-9)
    return pd.Series(out, index=close.index)


@pytest.mark.parametrize("seed", [0, 1, 7])
@pytest.mark.parametrize("horizon", [5, 20, 120])
def test_equivalencia_con_fuerza_bruta(seed: int, horizon: int):
    rng = np.random.default_rng(seed)
    n = 600
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, n))))
    fast = label_future_max_return(close, horizon=horizon, min_return=0.15)
    slow = brute_force(close, horizon=horizon, min_return=0.15)
    pd.testing.assert_series_equal(fast, slow, check_names=False)


def test_cola_sin_ventana_completa_es_nan():
    close = pd.Series([100.0] * 50)
    labels = label_future_max_return(close, horizon=20, min_return=0.10)
    assert labels.iloc[-20:].isna().all()
    assert labels.iloc[:-20].notna().all()


def test_umbral_exacto_cuenta_como_positivo():
    # close[0]=100 y el máximo futuro es 115 -> retorno exactamente 0.15
    close = pd.Series([100.0, 110.0, 115.0, 90.0, 90.0])
    labels = label_future_max_return(close, horizon=3, min_return=0.15)
    assert labels.iloc[0] == 1.0


def test_sin_subida_suficiente_es_cero():
    close = pd.Series([100.0, 104.0, 103.0, 102.0, 101.0])
    labels = label_future_max_return(close, horizon=3, min_return=0.15)
    assert labels.iloc[0] == 0.0

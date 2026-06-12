"""Comportamientos críticos de los modelos: el umbral respeta el recall mínimo
maximizando precisión, y el quality score es monótono y acotado.
"""
import numpy as np
import pandas as pd

from screener.models.quality import quality_score
from screener.models.tactical import optimize_threshold


def test_umbral_respeta_recall_minimo():
    rng = np.random.default_rng(42)
    n = 5000
    y = rng.binomial(1, 0.3, n)
    # probabilidades correlacionadas con y, con ruido
    probs = np.clip(0.25 * y + rng.beta(2, 3, n), 0, 1)
    thr, prec, rec = optimize_threshold(y, probs, recall_floor=0.25)
    assert rec >= 0.25
    # cualquier umbral más alto que el elegido debe violar el recall o no mejorar precisión
    higher = probs >= (thr + 0.05)
    if higher.sum() > 0:
        rec_higher = (y[higher] == 1).sum() / (y == 1).sum()
        prec_higher = (y[higher] == 1).mean()
        assert rec_higher < 0.25 or prec_higher <= prec + 1e-9


def test_umbral_maximiza_precision_caso_trivial():
    # señal perfecta: el umbral óptimo separa exactamente
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    probs = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])
    thr, prec, rec = optimize_threshold(y, probs, recall_floor=0.25)
    assert prec == 1.0
    assert rec >= 0.25


def _row(**overrides):
    base = {
        "roic": 0.15, "fcf_margin": 0.12, "gross_margin": 0.45,
        "operating_margin": 0.20, "revenue_growth_yoy": 0.10,
        "ey_pct_5y": 0.6, "fcfy_pct_5y": 0.6, "peg_ttm": 1.5,
        "net_debt_ebitda": 1.0, "interest_coverage": 8.0,
        "shares_change_yoy": -0.01,
    }
    base.update(overrides)
    return base


def test_quality_score_acotado_y_monotono():
    df = pd.DataFrame([
        _row(),                                        # empresa decente
        _row(roic=0.30, fcf_margin=0.25, ey_pct_5y=0.95, fcfy_pct_5y=0.95,
             net_debt_ebitda=-0.5, shares_change_yoy=-0.03, peg_ttm=0.8),  # excelente y barata
        _row(roic=-0.05, fcf_margin=-0.1, revenue_growth_yoy=-0.2,
             ey_pct_5y=0.05, fcfy_pct_5y=0.05, net_debt_ebitda=6.0,
             interest_coverage=0.5, shares_change_yoy=0.08, peg_ttm=np.nan),  # mala y cara
    ])
    scores, breakdown = quality_score(df)
    assert ((scores >= 0) & (scores <= 100)).all()
    assert scores.iloc[1] > scores.iloc[0] > scores.iloc[2]
    assert scores.iloc[1] > 80
    assert scores.iloc[2] < 25
    # el desglose suma el total
    np.testing.assert_allclose(breakdown.sum(axis=1), scores, atol=1e-6)


def test_quality_score_nan_da_credito_parcial():
    completo = pd.DataFrame([_row()])
    con_nan = pd.DataFrame([_row(gross_margin=np.nan, interest_coverage=np.nan)])
    s_full, _ = quality_score(completo)
    s_nan, _ = quality_score(con_nan)
    # con NaN no colapsa a 0: recibe crédito parcial neutro
    assert s_nan.iloc[0] > 0.5 * s_full.iloc[0]

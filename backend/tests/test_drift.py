"""Deriva de datos: la foto de inferencia es una sección transversal de UN día,
así que las features de mercado (macro + VIX) son una constante para todas las
empresas. Compararlas por KS contra el panel multi-anual de entrenamiento da
deriva ~siempre (KS≈1) y es un artefacto, no deriva real. El chequeo debe:

- medir KS de deriva SOLO sobre features por-empresa (sección transversal),
- evaluar las de mercado como novedad de régimen: ¿el valor de hoy cae fuera
  del rango visto en entrenamiento?
"""
import numpy as np
import pandas as pd

from screener.drift import compute_data_drift, recent_cross_section

CROSS_SECTIONAL = ["roe", "pe_ttm"]
MARKET_WIDE = {"vix_level", "fed_funds"}


def _reference(rng) -> pd.DataFrame:
    n = 400
    return pd.DataFrame({
        "roe": rng.normal(0.15, 0.05, n),
        "pe_ttm": rng.normal(20, 5, n),
        # de mercado: rango ancho simulando 7 años de regímenes
        "vix_level": rng.uniform(10, 40, n),
        "fed_funds": rng.uniform(0, 5, n),
    })


def test_features_de_mercado_constantes_no_cuentan_como_deriva():
    """Aunque las features de mercado sean una constante en la foto de hoy
    (KS≈1 contra el panel), NO deben contar como deriva: el share se mide solo
    sobre las por-empresa, que aquí no derivaron."""
    rng = np.random.default_rng(7)
    reference = _reference(rng)
    current = pd.DataFrame({
        "roe": rng.normal(0.15, 0.05, 200),       # misma distribución -> sin deriva
        "pe_ttm": rng.normal(20, 5, 200),
        "vix_level": np.full(200, 18.0),          # constante, dentro del rango
        "fed_funds": np.full(200, 2.0),           # constante, dentro del rango
    })

    share, detail = compute_data_drift(reference, current, market_wide=MARKET_WIDE)

    # las de mercado NO entran al KS transversal
    assert set(detail["per_column"]).issubset(set(CROSS_SECTIONAL))
    assert detail["evaluated"] == len(CROSS_SECTIONAL)
    # sin deriva real por-empresa -> share bajo, no dispara
    assert share <= 0.30


def test_mercado_fuera_de_rango_se_marca_como_novedad():
    rng = np.random.default_rng(1)
    reference = _reference(rng)
    current = pd.DataFrame({
        "roe": rng.normal(0.15, 0.05, 200),
        "pe_ttm": rng.normal(20, 5, 200),
        "vix_level": np.full(200, 80.0),   # MUY por encima del máx de entrenamiento (~40)
        "fed_funds": np.full(200, 2.0),    # dentro del rango
    })

    _, detail = compute_data_drift(reference, current, market_wide=MARKET_WIDE)

    assert detail["market_wide"]["vix_level"]["out_of_range"] is True
    assert detail["market_wide"]["fed_funds"]["out_of_range"] is False


def test_recent_cross_section_toma_solo_las_ultimas_n_fechas():
    """La referencia de deriva debe ser una VENTANA RECIENTE: solo las últimas
    n fechas-snapshot del dataset, no los 7 años en bloque."""
    dates = pd.to_datetime(
        ["2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01", "2025-05-01"]
    )
    df = pd.DataFrame({
        "date": np.repeat(dates, 3),
        "roe": np.arange(15.0),
    })
    recent = recent_cross_section(df, n_dates=2)
    assert sorted(recent["date"].unique()) == list(pd.to_datetime(["2025-04-01", "2025-05-01"]))
    assert len(recent) == 6  # 2 fechas x 3 filas


def test_novedad_de_mercado_usa_referencia_de_rango_separada():
    """El share transversal se mide contra la ventana reciente, pero la novedad
    de mercado (¿extrapola el modelo?) se evalúa contra el rango COMPLETO de
    entrenamiento, que se pasa aparte."""
    rng = np.random.default_rng(5)
    recent_ref = pd.DataFrame({
        "roe": rng.normal(0.15, 0.05, 200),
        "pe_ttm": rng.normal(20, 5, 200),
        "vix_level": rng.uniform(12, 16, 200),   # rango reciente estrecho
        "fed_funds": rng.uniform(4, 5, 200),
    })
    full_ref = pd.DataFrame({
        "roe": rng.normal(0.15, 0.05, 400),
        "pe_ttm": rng.normal(20, 5, 400),
        "vix_level": rng.uniform(10, 80, 400),   # rango de entrenamiento ANCHO
        "fed_funds": rng.uniform(0, 5, 400),
    })
    current = pd.DataFrame({
        "roe": rng.normal(0.15, 0.05, 200),
        "pe_ttm": rng.normal(20, 5, 200),
        "vix_level": np.full(200, 30.0),  # fuera del reciente, DENTRO del entrenamiento
        "fed_funds": np.full(200, 4.5),
    })

    _, detail = compute_data_drift(
        recent_ref, current, market_wide=MARKET_WIDE, market_wide_reference=full_ref
    )
    # 30 está dentro del rango de entrenamiento (10-80): NO es novedad/extrapolación
    assert detail["market_wide"]["vix_level"]["out_of_range"] is False
    assert detail["market_wide"]["vix_level"]["ref_max"] >= 70  # usó el rango ancho


def test_deriva_real_por_empresa_si_se_detecta():
    rng = np.random.default_rng(3)
    reference = _reference(rng)
    current = pd.DataFrame({
        "roe": rng.normal(0.45, 0.05, 200),   # desplazada -> deriva genuina
        "pe_ttm": rng.normal(60, 5, 200),     # desplazada -> deriva genuina
        "vix_level": np.full(200, 18.0),
        "fed_funds": np.full(200, 2.0),
    })

    share, _ = compute_data_drift(reference, current, market_wide=MARKET_WIDE)

    assert share > 0.30

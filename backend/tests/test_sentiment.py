"""El rezago PIT del sentimiento: un 8-K publicado el día D no puede ser
visible para el modelo hasta el siguiente día hábil.
"""
import pandas as pd

from screener.features.sentiment import aggregate_daily


def _scored(filing_date: str, score: float) -> pd.DataFrame:
    return pd.DataFrame([
        {"ticker": "TEST", "filing_date": pd.Timestamp(filing_date), "sent_score": score}
    ])


def test_lag_de_un_dia_habil():
    # filing un lunes -> visible el martes
    daily = aggregate_daily(_scored("2024-01-08", 0.8), end=pd.Timestamp("2024-01-12"))
    daily = daily.set_index("date")
    assert pd.Timestamp("2024-01-08") not in daily.index  # el lunes no existe aún
    assert daily.loc[pd.Timestamp("2024-01-09"), "sent_last"] == 0.8


def test_lag_viernes_salta_al_lunes():
    # filing un viernes -> visible el lunes siguiente (no el sábado)
    daily = aggregate_daily(_scored("2024-01-05", -0.5), end=pd.Timestamp("2024-01-12"))
    daily = daily.set_index("date")
    assert daily.index.min() == pd.Timestamp("2024-01-08")
    assert daily.loc[pd.Timestamp("2024-01-08"), "sent_last"] == -0.5


def test_days_since_crece_y_se_capa():
    daily = aggregate_daily(_scored("2024-01-05", 0.1), end=pd.Timestamp("2024-08-01"))
    daily = daily.set_index("date")
    assert daily.loc[pd.Timestamp("2024-01-08"), "days_since_8k"] == 0
    assert daily.loc[pd.Timestamp("2024-01-15"), "days_since_8k"] == 7
    assert daily["days_since_8k"].max() == 90  # capado

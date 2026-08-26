"""El rezago PIT del sentimiento: un 8-K publicado el día D no puede ser
visible para el modelo hasta el siguiente día hábil.

También: el extra `sentiment` (torch + transformers) es opcional y su ausencia
no puede tumbar el pipeline diario.
"""
import builtins

import pandas as pd

from screener.features import sentiment as sentiment_mod
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


def test_sin_torch_el_paso_se_omite_sin_romper(monkeypatch, capsys):
    """Sin el extra `sentiment` instalado, process_pending_filings no revienta."""
    filings = pd.DataFrame([
        {
            "ticker": "TEST",
            "filing_date": pd.Timestamp("2024-01-08"),
            "sent_score": float("nan"),
            "text": "x" * 100,
        }
    ])
    monkeypatch.setattr(sentiment_mod, "load_filings", lambda: filings)
    monkeypatch.setattr(sentiment_mod, "build_sentiment_daily", lambda log=print: None)

    real_import = builtins.__import__

    def sin_torch(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("No module named 'torch'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sin_torch)

    sentiment_mod.process_pending_filings()  # no debe lanzar

    assert "omitido" in capsys.readouterr().out

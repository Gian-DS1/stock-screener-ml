"""Jerarquía de las reglas de salida: la primera condición que se cumple manda.

Orden: 1) Stop Loss -12%  2) Trailing -8% desde pico (activo tras +5%)
       3) Límite de tiempo 120 días hábiles  4) TP parcial +15% (una sola vez)
"""
import pandas as pd

from screener.engine.portfolio import check_exit_rules


def _closes(*prices: float) -> pd.Series:
    idx = pd.bdate_range("2024-01-02", periods=len(prices))
    return pd.Series(prices, index=idx)


def test_stop_loss_dispara_a_menos_12():
    state = check_exit_rules(entry_price=100.0, closes=_closes(95, 90, 88), partial_tp_done=False)
    assert state["triggered"][0][0] == "STOP_LOSS"


def test_stop_loss_exactamente_en_el_limite():
    state = check_exit_rules(100.0, _closes(95, 88.0), False)
    assert state["triggered"][0][0] == "STOP_LOSS"  # 88 = 100*(1-0.12)


def test_stop_tiene_prioridad_sobre_trailing():
    # sube a 110 (trailing activo), luego colapsa a 85: cruza ambos umbrales,
    # pero el stop loss es jerárquicamente primero
    state = check_exit_rules(100.0, _closes(105, 110, 85), False)
    assert state["triggered"][0][0] == "STOP_LOSS"


def test_trailing_requiere_activacion_de_5pct():
    # pico en 104 (<105): trailing NO activo aunque caiga 8% desde el pico
    state = check_exit_rules(100.0, _closes(104, 95.6), False)
    types = [t for t, _ in state["triggered"]]
    assert "TRAILING" not in types


def test_trailing_dispara_tras_activarse():
    # pico 110 (>=105): cae a 101.2 = 110*0.92 -> trailing
    state = check_exit_rules(100.0, _closes(105, 110, 101.2), False)
    assert state["triggered"][0][0] == "TRAILING"


def test_limite_de_tiempo_a_los_120_dias_habiles():
    closes = pd.Series(
        [100.0] * 121, index=pd.bdate_range("2024-01-02", periods=121)
    )
    state = check_exit_rules(100.0, closes, False)
    assert state["triggered"][0][0] == "TIME_LIMIT"
    # con 119 días aún no
    state = check_exit_rules(100.0, closes.iloc[:119], False)
    assert state["triggered"] == []


def test_tp_parcial_a_mas_15_solo_una_vez():
    state = check_exit_rules(100.0, _closes(110, 116), False)
    assert state["triggered"][0][0] == "TP_PARCIAL"
    # ya ejecutado -> no se repite
    state = check_exit_rules(100.0, _closes(110, 116), True)
    assert state["triggered"] == []


def test_tp_parcial_no_dispara_si_hay_salida_total():
    # +15% histórico pero hoy cruzó el trailing: la salida total manda
    state = check_exit_rules(100.0, _closes(116, 106.7), False)
    assert state["triggered"][0][0] == "TRAILING"
    types = [t for t, _ in state["triggered"]]
    assert "TP_PARCIAL" not in types


def test_sin_condiciones_no_hay_disparo():
    state = check_exit_rules(100.0, _closes(101, 103, 99), False)
    assert state["triggered"] == []
    assert state["peak_price"] == 103
    assert state["days_held"] == 3
    assert state["last_price"] == 99

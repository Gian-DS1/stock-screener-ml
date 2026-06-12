"""Garantías Point-In-Time: ningún dato puede ser visible antes de su
fecha real de publicación (filed / realtime_start).
"""
import pandas as pd

from screener.features.fundamental import build_snapshots
from screener.features.macro import build_macro_daily


def _facts_row(concept, start, end, value, filed, ticker="TEST", form="10-Q"):
    return {
        "cik": 1, "ticker": ticker, "concept": concept, "tag": concept,
        "start": pd.Timestamp(start) if start else pd.NaT,
        "end": pd.Timestamp(end), "value": float(value),
        "filed": pd.Timestamp(filed), "form": form, "fy": 2020, "fp": "Q1",
    }


def _quarters(concept, quarters, values, filed_dates):
    """quarters: lista de (start, end)."""
    return [
        _facts_row(concept, s, e, v, f)
        for (s, e), v, f in zip(quarters, values, filed_dates)
    ]


QUARTERS_2020 = [
    ("2020-01-01", "2020-03-31"),
    ("2020-04-01", "2020-06-30"),
    ("2020-07-01", "2020-09-30"),
]
FY_2020 = ("2020-01-01", "2020-12-31")
FILED = ["2020-05-10", "2020-08-10", "2020-11-10"]
FY_FILED = "2021-02-20"


def _base_facts() -> pd.DataFrame:
    rows = []
    # Trimestres Q1-Q3 directos + FY anual (Q4 se deriva: FY - Q1 - Q2 - Q3)
    rows += _quarters("revenue", QUARTERS_2020, [100, 110, 120], FILED)
    rows.append(_facts_row("revenue", *FY_2020, 460, FY_FILED, form="10-K"))
    # Concepto de stock (instantáneo, sin start)
    rows.append(_facts_row("equity", None, "2020-03-31", 1000, "2020-05-10"))
    rows.append(_facts_row("equity", None, "2020-06-30", 1100, "2020-08-10"))
    return pd.DataFrame(rows)


def test_snapshot_no_visible_antes_de_filed():
    snaps = build_snapshots(_base_facts())
    snaps = snaps[snaps["ticker"] == "TEST"]
    # Todo snapshot debe estar disponible solo desde el máximo `filed` de los
    # datos que lo componen: nunca antes.
    assert (snaps["available_from"] >= pd.Timestamp("2020-05-10")).all()
    # El snapshot que ya incluye Q2 (filed 2020-08-10) no puede estar antes
    q2_snapshots = snaps[snaps["period_end"] >= pd.Timestamp("2020-06-30")]
    assert (q2_snapshots["available_from"] >= pd.Timestamp("2020-08-10")).all()


def test_q4_derivado_de_anual():
    snaps = build_snapshots(_base_facts())
    # Q4 = 460 - (100+110+120) = 130 -> TTM al cierre de FY = 460
    fy_snap = snaps[snaps["period_end"] == pd.Timestamp("2020-12-31")]
    assert len(fy_snap) == 1
    assert fy_snap.iloc[0]["revenue_ttm"] == 460
    # y disponible solo desde el filing del 10-K
    assert fy_snap.iloc[0]["available_from"] == pd.Timestamp(FY_FILED)


def test_ttm_es_suma_de_4_trimestres():
    rows = []
    quarters = [
        ("2020-01-01", "2020-03-31"), ("2020-04-01", "2020-06-30"),
        ("2020-07-01", "2020-09-30"), ("2020-10-01", "2020-12-31"),
        ("2021-01-01", "2021-03-31"),
    ]
    values = [100, 110, 120, 130, 140]
    filed = ["2020-05-10", "2020-08-10", "2020-11-10", "2021-02-20", "2021-05-10"]
    rows += _quarters("revenue", quarters, values, filed)
    snaps = build_snapshots(pd.DataFrame(rows))
    ttm_q1_2021 = snaps[snaps["period_end"] == pd.Timestamp("2021-03-31")]
    assert ttm_q1_2021.iloc[0]["revenue_ttm"] == 110 + 120 + 130 + 140


def test_quarterly_derivado_de_ytd():
    """OCF/capex se reportan como YTD acumulado (Q1=3m, 6m, 9m, FY): los
    trimestres Q2-Q4 deben derivarse por diferencias de ventanas con el mismo
    inicio de año fiscal."""
    rows = [
        # Año 2020 completo en formato YTD acumulado
        _facts_row("ocf", "2020-01-01", "2020-03-31", 50, "2020-05-10"),    # Q1 = 50
        _facts_row("ocf", "2020-01-01", "2020-06-30", 120, "2020-08-10"),   # Q2 = 70
        _facts_row("ocf", "2020-01-01", "2020-09-30", 200, "2020-11-10"),   # Q3 = 80
        _facts_row("ocf", "2020-01-01", "2020-12-31", 290, "2021-02-20", form="10-K"),  # Q4 = 90
        # Q1 del año siguiente
        _facts_row("ocf", "2021-01-01", "2021-03-31", 60, "2021-05-10"),
    ]
    snaps = build_snapshots(pd.DataFrame(rows))
    ttm = snaps[snaps["period_end"] == pd.Timestamp("2021-03-31")]
    # TTM Q1-2021 = Q2+Q3+Q4 de 2020 + Q1 2021 = 70+80+90+60 = 300
    assert len(ttm) == 1
    assert ttm.iloc[0]["ocf_ttm"] == 300
    # disponible solo cuando se conoce el último componente (10-Q de mayo 2021)
    assert ttm.iloc[0]["available_from"] == pd.Timestamp("2021-05-10")


def test_macro_respeta_realtime_start():
    macro = pd.DataFrame({
        "series": ["unemployment"] * 2,
        "date": pd.to_datetime(["2020-03-01", "2020-04-01"]),  # mes observado
        "realtime_start": pd.to_datetime(["2020-04-03", "2020-05-08"]),  # publicación
        "value": [4.4, 14.7],
    })
    daily = build_macro_daily(macro, pd.date_range("2020-04-01", "2020-05-15"))
    # El dato de abril (14.7) se publicó el 8 de mayo: antes debe verse el de marzo
    assert daily.loc[pd.Timestamp("2020-05-07"), "unemployment"] == 4.4
    assert daily.loc[pd.Timestamp("2020-05-08"), "unemployment"] == 14.7
    # Antes de la primera publicación no hay dato
    assert pd.isna(daily.loc[pd.Timestamp("2020-04-02"), "unemployment"])

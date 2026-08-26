"""El universo depende de tablas de Wikipedia que cambian de forma y de sitio.

Estos tests fijan la parte que sí controlamos: qué columna se toma como sector
del NASDAQ-100 (la tabla clasifica por ICB, no por GICS) y que el merge nunca
pise un sector GICS existente con uno ICB.
"""
import pandas as pd

from screener.universe import _ndx_sector_column


def test_prefiere_icb_industry_sobre_icb_subsector():
    """'ICB Subsector' contiene la palabra "Sector" pero es mucho más fino."""
    cols = ["Ticker", "Company", "ICB Industry[1]", "ICB Subsector[1]"]

    assert _ndx_sector_column(cols) == "ICB Industry[1]"


def test_prefiere_gics_cuando_la_tabla_lo_trae():
    cols = ["Ticker", "Company", "GICS Sector", "GICS Sub-Industry"]

    assert _ndx_sector_column(cols) == "GICS Sector"


def test_sin_columna_de_sector_devuelve_none():
    assert _ndx_sector_column(["Ticker", "Company", "Date added"]) is None


def test_el_sector_gics_del_sp500_gana_sobre_el_icb_del_ndx():
    """Reproduce el fillna del merge: ICB solo rellena huecos."""
    sp500 = pd.DataFrame({"ticker": ["AAPL", "ALNY"], "sector": ["Information Technology", None]})
    ndx = pd.DataFrame({"ticker": ["AAPL", "ALNY"], "sector_ndx": ["Technology", "Health Care"]})

    merged = sp500.merge(ndx, on="ticker")
    merged["sector"] = merged["sector"].fillna(merged.pop("sector_ndx"))

    assert merged.set_index("ticker")["sector"].to_dict() == {
        "AAPL": "Information Technology",  # GICS intacto
        "ALNY": "Health Care",             # hueco relleno con ICB
    }

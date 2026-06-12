"""Features macro diarias con alineación PIT por fecha de publicación.

Cada serie se expande a diario tomando el último valor cuyo `realtime_start`
(fecha de publicación según ALFRED) sea <= a la fecha. El CPI se transforma a
inflación interanual usando primeras publicaciones, manteniendo como fecha de
disponibilidad la publicación del dato más reciente del cociente.
"""
import pandas as pd


def build_macro_daily(macro: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    out = pd.DataFrame(index=dates)
    if macro is None or macro.empty:
        return out
    for name, df in macro.groupby("series"):
        df = df.sort_values("date").reset_index(drop=True)
        if name == "cpi":
            df = df.copy()
            df["value"] = df["value"] / df["value"].shift(12) - 1
            df = df.dropna(subset=["value"])
            name = "cpi_yoy"
        s = df.sort_values("realtime_start").set_index("realtime_start")["value"]
        s = s.groupby(level=0).last()
        full_index = dates.union(s.index)
        out[name] = s.reindex(full_index).ffill().loc[dates]
    return out

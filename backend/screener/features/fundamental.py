"""Snapshots fundamentales TTM con disponibilidad Point-In-Time.

A partir de los hechos XBRL (long) se construye, por ticker y periodo fiscal,
una fila ancha con métricas TTM y de balance. Cada fila lleva `available_from`:
la fecha máxima de `filed` de los datos que la componen — el snapshot solo
existe para el modelo a partir de ese día.

Detalles clave:
- Flujos (revenue, net income, ...): TTM = suma de los últimos 4 trimestres.
  Q4 casi nunca se reporta como trimestre aislado: se deriva como FY - (Q1+Q2+Q3),
  con disponibilidad la del 10-K.
- Stocks (assets, equity, deuda, ...): último valor instantáneo reportado.
- Crecimientos YoY: TTM actual vs TTM de 4 trimestres atrás.
"""
import numpy as np
import pandas as pd

FLOW_CONCEPTS = [
    "revenue",
    "net_income",
    "eps_diluted",
    "gross_profit",
    "operating_income",
    "ocf",
    "capex",
    "dep_amort",
    "interest_expense",
]
STOCK_CONCEPTS = [
    "assets",
    "equity",
    "cash",
    "lt_debt",
    "st_debt",
    "shares_outstanding",
    "shares_diluted",
]

_QTR_MIN, _QTR_MAX = 60, 120     # duración en días de un trimestre fiscal
_FY_MIN, _FY_MAX = 330, 400      # duración de un año fiscal
_TTM_SPAN_MAX = 380              # los 4 trimestres deben cubrir ~1 año


def _quarterly_series(df: pd.DataFrame) -> pd.DataFrame:
    """Serie trimestral de un concepto de flujo.

    Tres rutas, en orden de preferencia para cada cierre de trimestre:
    1. Trimestres directos (duración ~3 meses), típicos del income statement.
    2. Diferencias de ventanas YTD con el mismo inicio de año fiscal
       (6m-3m, 9m-6m, 12m-9m), típico del cash flow statement.
    3. Q4 = FY - (Q1+Q2+Q3) cuando solo existe el anual del 10-K.
    """
    dur = (df["end"] - df["start"]).dt.days
    quarters = df[dur.between(_QTR_MIN, _QTR_MAX)][["start", "end", "value", "filed"]]
    annuals = df[dur.between(_FY_MIN, _FY_MAX)]

    # Ruta 2: dentro de cada año fiscal (mismo `start`), las ventanas acumuladas
    # ordenadas por fin se restan entre sí; si el tramo dura ~1 trimestre, es un Q.
    derived_ytd = []
    cumulative = df[dur.between(_QTR_MIN, _FY_MAX)].sort_values("end")
    for _, group in cumulative.groupby("start"):
        if len(group) < 2:
            continue
        prev = None
        for row in group.itertuples():
            if prev is not None:
                gap = (row.end - prev.end).days
                if _QTR_MIN <= gap <= _QTR_MAX:
                    derived_ytd.append({
                        "start": prev.end + pd.Timedelta(days=1),
                        "end": row.end,
                        "value": row.value - prev.value,
                        "filed": max(row.filed, prev.filed),
                    })
            prev = row

    # Ruta 3: cierre de año sin trimestre directo ni YTD intermedio
    derived_q4 = []
    known_ends = set(quarters["end"]) | {d["end"] for d in derived_ytd}
    for a in annuals.itertuples():
        if a.end in known_ends:
            continue
        inside = quarters[(quarters["start"] >= a.start) & (quarters["end"] < a.end)]
        if len(inside) != 3:
            continue
        derived_q4.append({
            "start": inside["end"].max() + pd.Timedelta(days=1),
            "end": a.end,
            "value": a.value - inside["value"].sum(),
            "filed": max(a.filed, inside["filed"].max()),
        })

    out = pd.concat(
        [quarters, pd.DataFrame(derived_ytd), pd.DataFrame(derived_q4)], ignore_index=True
    )
    return out.sort_values("end").drop_duplicates("end", keep="first").reset_index(drop=True)


def _ttm(quarterly: pd.DataFrame) -> pd.DataFrame:
    """TTM por suma móvil de 4 trimestres consecutivos (ventana <= ~380 días)."""
    if len(quarterly) < 4:
        return pd.DataFrame(columns=["period_end", "value", "available_from"])
    q = quarterly.reset_index(drop=True)
    span_ok = (q["end"] - q["end"].shift(3)).dt.days <= _TTM_SPAN_MAX
    ttm_value = q["value"].rolling(4).sum()
    # rolling().max() no soporta datetimes: máximo de los 4 `filed` vía shifts
    available = pd.concat([q["filed"].shift(k) for k in range(4)], axis=1).max(axis=1)
    out = pd.DataFrame({
        "period_end": q["end"],
        "value": ttm_value,
        "available_from": available,
    })[span_ok.fillna(False) & ttm_value.notna()]
    return out.reset_index(drop=True)


def _stock_series(df: pd.DataFrame) -> pd.DataFrame:
    """Niveles instantáneos: un valor por period_end, disponible desde su filed."""
    out = df[["end", "value", "filed"]].rename(
        columns={"end": "period_end", "filed": "available_from"}
    )
    return out.sort_values("period_end").drop_duplicates("period_end").reset_index(drop=True)


def _yoy(metric: pd.DataFrame) -> pd.DataFrame:
    """Crecimiento vs el valor de 4 periodos atrás (~1 año fiscal)."""
    m = metric.reset_index(drop=True)
    base = m["value"].shift(4)
    span_ok = (m["period_end"] - m["period_end"].shift(4)).dt.days.between(330, 400)
    growth = np.where(base.abs() > 0, m["value"] / base - 1, np.nan)
    out = pd.DataFrame({
        "period_end": m["period_end"],
        "value": growth,
        "available_from": m["available_from"],
    })[span_ok.fillna(False)]
    return out.dropna(subset=["value"]).reset_index(drop=True)


def build_snapshots(facts: pd.DataFrame) -> pd.DataFrame:
    """Tabla ancha por (ticker, period_end) con available_from PIT por fila."""
    all_rows = []
    for ticker, tf in facts.groupby("ticker"):
        metrics: dict[str, pd.DataFrame] = {}
        for concept, cf in tf.groupby("concept"):
            if concept in FLOW_CONCEPTS:
                q = _quarterly_series(cf)
                metrics[f"{concept}_ttm" if concept != "eps_diluted" else "eps_ttm"] = _ttm(q)
            elif concept in STOCK_CONCEPTS:
                metrics[concept] = _stock_series(cf)

        for src, name in [
            ("revenue_ttm", "revenue_ttm_yoy"),
            ("eps_ttm", "eps_ttm_yoy"),
            ("shares_outstanding", "shares_change_yoy"),
        ]:
            if src in metrics and not metrics[src].empty:
                metrics[name] = _yoy(metrics[src])

        frames = []
        for name, m in metrics.items():
            if m.empty:
                continue
            frames.append(m.assign(metric=name))
        if not frames:
            continue
        long = pd.concat(frames, ignore_index=True)
        wide_vals = long.pivot_table(index="period_end", columns="metric", values="value")
        avail = long.groupby("period_end")["available_from"].max()
        wide = wide_vals.join(avail).reset_index()
        wide["ticker"] = ticker
        all_rows.append(wide)

    if not all_rows:
        return pd.DataFrame(columns=["ticker", "period_end", "available_from"])
    snaps = pd.concat(all_rows, ignore_index=True)
    return snaps.sort_values(["ticker", "available_from", "period_end"]).reset_index(drop=True)


def snapshots_to_daily(snaps: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Expande los snapshots de UN ticker a frecuencia diaria PIT.

    Cada columna toma su último valor publicado hasta la fecha (ffill por
    columna sobre el índice available_from), de modo que métricas con cadencias
    distintas no se bloquean entre sí.
    """
    s = snaps.drop(columns=["ticker", "period_end"]).set_index("available_from").sort_index()
    s = s.groupby(level=0).last()
    full_index = dates.union(s.index)
    daily = s.reindex(full_index).ffill().loc[dates]
    return daily

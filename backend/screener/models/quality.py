"""Score de calidad de largo plazo (0-100), basado en reglas transparentes.

Sin entrenamiento -> sin overfitting. Actúa como gate del screener: la señal
táctica solo cuenta si la empresa es de calidad y cotiza con descuento.

Composición:
- Calidad del negocio (40 pts): ROIC, margen FCF, margen bruto, margen
  operativo, crecimiento de ingresos.
- Descuento de valoración (40 pts): percentil del earnings/FCF yield dentro
  de su propia historia de 5 años (alto = barata vs sí misma), PEG.
- Solidez financiera (20 pts): deuda neta/EBITDA, cobertura de intereses,
  recompras vs dilución.

Política de NaN: crédito neutro del 50% del componente (no se castiga a un
banco por no reportar gross profit), excepto el PEG, cuyo NaN casi siempre
significa crecimiento <= 0 y puntúa 0.
"""
import numpy as np
import pandas as pd

# (columna, puntos, peor_valor, mejor_valor, crédito_si_NaN)
_COMPONENTS: list[tuple[str, float, float, float, float]] = [
    # --- calidad del negocio (40) ---
    ("roic", 12.0, 0.0, 0.20, 0.5),
    ("fcf_margin", 8.0, 0.0, 0.15, 0.5),
    ("gross_margin", 6.0, 0.0, 0.50, 0.5),
    ("operating_margin", 6.0, 0.0, 0.25, 0.5),
    ("revenue_growth_yoy", 8.0, 0.0, 0.15, 0.5),
    # --- descuento de valoración (40) ---
    ("ey_pct_5y", 16.0, 0.0, 1.0, 0.5),
    ("fcfy_pct_5y", 16.0, 0.0, 1.0, 0.5),
    ("peg_ttm", 8.0, 3.0, 1.0, 0.0),  # invertido: PEG bajo es mejor
    # --- solidez financiera (20) ---
    ("net_debt_ebitda", 8.0, 4.0, 0.0, 0.5),  # invertido
    ("interest_coverage", 6.0, 1.0, 10.0, 0.5),
    ("shares_change_yoy", 6.0, 0.05, -0.02, 0.5),  # invertido: recompras > dilución
]

QUALITY_INPUT_COLUMNS = [c[0] for c in _COMPONENTS]


def _linear(x: pd.Series, worst: float, best: float, points: float, nan_credit: float) -> pd.Series:
    if best > worst:
        frac = (x - worst) / (best - worst)
    else:  # métrica invertida
        frac = (worst - x) / (worst - best)
    frac = frac.clip(0.0, 1.0) * points
    return frac.fillna(points * nan_credit)


def quality_score(df: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """Devuelve (score 0-100, desglose por componente) para cada fila."""
    breakdown = pd.DataFrame(index=df.index)
    for col, points, worst, best, nan_credit in _COMPONENTS:
        x = df[col] if col in df.columns else pd.Series(np.nan, index=df.index)
        breakdown[col] = _linear(x, worst, best, points, nan_credit)
    return breakdown.sum(axis=1), breakdown

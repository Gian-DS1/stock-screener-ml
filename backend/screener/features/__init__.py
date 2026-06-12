"""Registro central del espacio de características (34 features, 5 dimensiones).

El orden y los nombres son el contrato entre builder, entrenamiento, scoring,
SHAP y drift: cualquier cambio aquí implica reentrenar.
"""

FUNDAMENTAL_FEATURES = [
    "pe_ttm",
    "peg_ttm",
    "fcf_yield",
    "revenue_growth_yoy",
    "gross_margin",
    "operating_margin",
    "roe",
    "debt_to_equity",
]

TECHNICAL_FEATURES = [
    "macd_hist_norm",
    "rsi_14",
    "williams_r_14",
    "price_vs_sma50",
    "price_vs_sma200",
    "sma50_vs_sma200",
    "ret_21d",
    "ret_63d",
    "ret_126d",
    "vol_21d",
    "volume_ratio",
]

MACRO_FEATURES = [
    "fed_funds",
    "cpi_yoy",
    "unemployment",
    "treasury_10y",
    "yield_curve_10y2y",
    "consumer_sentiment",
]

SENTIMENT_FEATURES = [
    "filings_8k_30d",
    "sent_mean_30d",
    "sent_last",
    "days_since_8k",
    "sent_trend",
]

VOLATILITY_FEATURES = [
    "vix_level",
    "vix_change_5d",
    "vix_vs_sma50",
    "vix_pct_252d",
]

ALL_FEATURES = (
    FUNDAMENTAL_FEATURES
    + TECHNICAL_FEATURES
    + MACRO_FEATURES
    + SENTIMENT_FEATURES
    + VOLATILITY_FEATURES
)

# Columnas auxiliares que viajan con el dataset pero NO entran al modelo:
# insumos del quality score, filtros del screener y contexto del backtest.
AUX_COLUMNS = [
    "close",
    "sma200",
    "dollar_volume_20d",
    "earnings_yield",
    "fcf_margin",
    "roic",
    "interest_coverage",
    "net_debt_ebitda",
    "shares_change_yoy",
    "ey_pct_5y",
    "fcfy_pct_5y",
]

assert len(ALL_FEATURES) == 34, f"El contrato es 34 features, hay {len(ALL_FEATURES)}"

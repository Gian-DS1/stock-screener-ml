export const fmtUsd = (v: number | null | undefined, digits = 2): string =>
  v == null ? '—' : v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: digits })

export const fmtPct = (v: number | null | undefined, digits = 1): string =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`

export const fmtSignedPct = (v: number | null | undefined, digits = 1): string =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`

export const fmtNum = (v: number | null | undefined, digits = 2): string =>
  v == null ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: digits })

export const fmtDate = (iso: string | null | undefined): string => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('es', { day: '2-digit', month: 'short', year: '2-digit' })
}

export const fmtDateTime = (iso: string | null | undefined): string => {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return d.toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/** Etiquetas legibles de las features del modelo (para SHAP y desgloses). */
export const FEATURE_LABELS: Record<string, string> = {
  pe_ttm: 'P/E (TTM)',
  peg_ttm: 'PEG (TTM)',
  fcf_yield: 'FCF yield',
  revenue_growth_yoy: 'Crec. ingresos YoY',
  gross_margin: 'Margen bruto',
  operating_margin: 'Margen operativo',
  roe: 'ROE',
  debt_to_equity: 'Deuda/Equity',
  macd_hist_norm: 'MACD (hist.)',
  rsi_14: 'RSI 14',
  williams_r_14: 'Williams %R',
  price_vs_sma50: 'Precio vs SMA50',
  price_vs_sma200: 'Precio vs SMA200',
  sma50_vs_sma200: 'SMA50 vs SMA200',
  ret_21d: 'Retorno 1m',
  ret_63d: 'Retorno 3m',
  ret_126d: 'Retorno 6m',
  vol_21d: 'Volatilidad 21d',
  volume_ratio: 'Ratio de volumen',
  fed_funds: 'Tasa FED',
  cpi_yoy: 'Inflación YoY',
  unemployment: 'Desempleo',
  treasury_10y: 'Tesoro 10a',
  yield_curve_10y2y: 'Curva 10a-2a',
  consumer_sentiment: 'Confianza consumidor',
  filings_8k_30d: '8-K últimos 30d',
  sent_mean_30d: 'Sentimiento 30d',
  sent_last: 'Último sentimiento',
  days_since_8k: 'Días sin 8-K',
  sent_trend: 'Tendencia sentimiento',
  vix_level: 'VIX',
  vix_change_5d: 'VIX cambio 5d',
  vix_vs_sma50: 'VIX vs SMA50',
  vix_pct_252d: 'VIX percentil 1a',
  // componentes del quality score
  roic: 'ROIC',
  fcf_margin: 'Margen FCF',
  ey_pct_5y: 'Earnings yield vs 5a',
  fcfy_pct_5y: 'FCF yield vs 5a',
  net_debt_ebitda: 'Deuda neta/EBITDA',
  interest_coverage: 'Cobertura intereses',
  shares_change_yoy: 'Dilución/recompras',
}

export const featureLabel = (f: string): string => FEATURE_LABELS[f] ?? f

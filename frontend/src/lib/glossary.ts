// Explicaciones en lenguaje llano de cada métrica, para personas sin formación
// financiera. `better` indica qué dirección suele ser favorable.

export type Better = 'higher' | 'lower' | 'context'

export interface MetricInfo {
  tip: string
  better: Better
}

export const BETTER_LABEL: Record<Better, string> = {
  higher: 'Cuanto más alto, mejor',
  lower: 'Cuanto más bajo, mejor',
  context: 'Depende del contexto',
}

export const GLOSSARY: Record<string, MetricInfo> = {
  // --- valoración / contexto del header ---
  price: { tip: 'Precio actual de una acción de la empresa.', better: 'context' },
  pct_vs_sma200: {
    tip: 'Qué tan lejos está el precio de hoy respecto a su promedio de los últimos 200 días. Negativo significa que cotiza POR DEBAJO de su promedio: está “en descuento”, que es lo que buscamos.',
    better: 'lower',
  },

  // --- fundamentales (negocio) ---
  pe_ttm: {
    tip: 'Precio / beneficio: cuántos años de ganancias actuales costaría comprar la empresa. Un PE bajo sugiere que está barata; uno muy alto, que el mercado paga caro por ella.',
    better: 'lower',
  },
  peg_ttm: {
    tip: 'El PE ajustado por el crecimiento de las ganancias. Cerca o por debajo de 1 indica que pagas un precio razonable por el crecimiento que ofrece.',
    better: 'lower',
  },
  fcf_yield: {
    tip: 'Caja libre que genera la empresa en un año dividida por su valor en bolsa. Es como el “interés” que produce el negocio. Más alto = genera más efectivo por cada dólar invertido.',
    better: 'higher',
  },
  earnings_yield: {
    tip: 'Las ganancias anuales como porcentaje del precio (lo inverso del PE). Más alto significa que la acción está más barata respecto a lo que gana.',
    better: 'higher',
  },
  revenue_growth_yoy: {
    tip: 'Cuánto crecieron las ventas frente al año anterior. Positivo y alto indica un negocio en expansión.',
    better: 'higher',
  },
  gross_margin: {
    tip: 'De cada dólar vendido, cuánto queda tras el costo directo del producto. Margen alto = producto rentable y con poder de fijar precios.',
    better: 'higher',
  },
  operating_margin: {
    tip: 'De cada dólar vendido, cuánto queda como ganancia tras los gastos de operar el negocio. Más alto = empresa más eficiente.',
    better: 'higher',
  },
  fcf_margin: {
    tip: 'Qué porcentaje de las ventas se convierte en efectivo libre. Alto significa que el negocio realmente genera caja, no solo ganancias contables.',
    better: 'higher',
  },
  roe: {
    tip: 'Rentabilidad sobre el capital de los accionistas: cuánto gana la empresa por cada dólar que han puesto los dueños. Más alto = usa bien su capital.',
    better: 'higher',
  },
  roic: {
    tip: 'Rentabilidad sobre TODO el capital invertido (de dueños y deuda). Es una de las mejores señales de un buen negocio: por encima de ~10-15% suele indicar calidad.',
    better: 'higher',
  },
  debt_to_equity: {
    tip: 'Cuánta deuda tiene la empresa frente al capital de los accionistas. Más bajo = menos riesgo financiero.',
    better: 'lower',
  },
  net_debt_ebitda: {
    tip: 'Cuántos años de ganancias operativas necesitaría la empresa para pagar su deuda neta. Bajo (o negativo, si tiene más caja que deuda) = balance sólido.',
    better: 'lower',
  },
  interest_coverage: {
    tip: 'Cuántas veces cubre la empresa los intereses de su deuda con sus ganancias. Más alto = paga su deuda con holgura.',
    better: 'higher',
  },
  shares_change_yoy: {
    tip: 'Cambio en el número de acciones frente al año anterior. Negativo es bueno: la empresa recompra acciones (cada accionista posee más); positivo significa dilución.',
    better: 'lower',
  },
  ey_pct_5y: {
    tip: 'Qué tan barata está hoy la acción (por sus ganancias) comparada con su propia historia de 5 años. Cerca de 100% = de lo más barata que ha estado.',
    better: 'higher',
  },
  fcfy_pct_5y: {
    tip: 'Lo mismo pero por la caja que genera: qué tan atractiva está hoy frente a su historia de 5 años. Cerca de 100% = rara oportunidad de descuento.',
    better: 'higher',
  },

  // --- técnicas (momento del precio) ---
  rsi_14: {
    tip: 'Mide si la acción está “sobrecomprada” (cerca de 70) o “sobrevendida” (cerca de 30) en las últimas 2 semanas. Valores bajos pueden indicar un rebote próximo.',
    better: 'context',
  },
  williams_r_14: {
    tip: 'Similar al RSI: indica si el precio está cerca de su máximo o mínimo reciente. Sirve para detectar excesos de corto plazo.',
    better: 'context',
  },
  macd_hist_norm: {
    tip: 'Indicador de impulso: positivo sugiere que la tendencia de corto plazo gana fuerza al alza; negativo, lo contrario.',
    better: 'context',
  },
  price_vs_sma50: {
    tip: 'Distancia del precio frente a su promedio de 50 días (tendencia de medio plazo).',
    better: 'context',
  },
  price_vs_sma200: {
    tip: 'Distancia del precio frente a su promedio de 200 días (tendencia de largo plazo). Por debajo = posible descuento.',
    better: 'context',
  },
  sma50_vs_sma200: {
    tip: 'Compara la tendencia de medio plazo con la de largo plazo. Positivo suele indicar tendencia alcista saludable.',
    better: 'context',
  },
  ret_21d: { tip: 'Cuánto ha rendido la acción en el último mes aproximadamente.', better: 'context' },
  ret_63d: { tip: 'Rendimiento de los últimos 3 meses.', better: 'context' },
  ret_126d: { tip: 'Rendimiento de los últimos 6 meses.', better: 'context' },
  vol_21d: {
    tip: 'Cuánto oscila el precio (volatilidad). Más alta = movimientos más bruscos y, por tanto, más riesgo.',
    better: 'lower',
  },
  volume_ratio: {
    tip: 'Compara el volumen negociado reciente con el habitual. Un repunte puede indicar interés creciente en la acción.',
    better: 'context',
  },

  // --- macro (entorno económico) ---
  fed_funds: { tip: 'Tasa de interés de referencia de la Reserva Federal de EE. UU. Tasas altas suelen presionar a la baja a las acciones.', better: 'context' },
  cpi_yoy: { tip: 'Inflación anual. Una inflación alta erosiona el poder adquisitivo y suele endurecer la política monetaria.', better: 'context' },
  unemployment: { tip: 'Tasa de desempleo en EE. UU. Refleja la salud del ciclo económico.', better: 'context' },
  treasury_10y: { tip: 'Rendimiento del bono del Tesoro a 10 años: la “tasa libre de riesgo” de referencia para valorar acciones.', better: 'context' },
  yield_curve_10y2y: { tip: 'Diferencia entre tasas a 10 y 2 años. Cuando es negativa (curva invertida) suele anticipar desaceleración económica.', better: 'context' },
  consumer_sentiment: { tip: 'Confianza de los consumidores. Más alta suele acompañar un mayor gasto y mejor entorno para las empresas.', better: 'higher' },

  // --- sentimiento (noticias / reportes) ---
  filings_8k_30d: { tip: 'Cuántos reportes oficiales (8-K) ha publicado la empresa en el último mes. Mucha actividad puede señalar eventos relevantes.', better: 'context' },
  sent_mean_30d: { tip: 'Tono promedio (positivo/negativo) de los reportes recientes, según un modelo de lenguaje. Positivo es favorable.', better: 'higher' },
  sent_last: { tip: 'Tono del reporte más reciente de la empresa.', better: 'higher' },
  days_since_8k: { tip: 'Días desde el último reporte oficial. Muchos días sin novedades = menos ruido informativo.', better: 'context' },
  sent_trend: { tip: 'Si el tono de las noticias está mejorando o empeorando frente a meses anteriores.', better: 'higher' },

  // --- volatilidad de mercado (VIX) ---
  vix_level: { tip: 'El “índice del miedo”: mide el nerviosismo del mercado. Alto = pánico; bajo = calma.', better: 'context' },
  vix_change_5d: { tip: 'Cuánto ha cambiado el miedo del mercado en la última semana.', better: 'context' },
  vix_vs_sma50: { tip: 'El nivel de miedo actual frente a su promedio reciente.', better: 'context' },
  vix_pct_252d: { tip: 'Qué tan alto está el miedo del mercado comparado con el último año (0 = el más calmado, 1 = el más tenso).', better: 'context' },
}

export const metricInfo = (key: string): MetricInfo | undefined => GLOSSARY[key]

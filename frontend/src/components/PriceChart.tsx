import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtUsd } from '../lib/format'

export type ChartPoint = { date: string; close: number; sma200: number | null }

/** Precio de cierre contra su SMA200.
 *
 * Vive en su propio módulo para poder cargarse con `lazy()`: recharts pesa más
 * que el resto de la app junta y solo se necesita al abrir el detalle de una
 * señal, así que no tiene por qué entrar en el bundle inicial.
 */
export default function PriceChart({ data }: { data: ChartPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
        <defs>
          <linearGradient id="close-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3ddc97" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#3ddc97" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" hide />
        <YAxis domain={['auto', 'auto']} hide />
        <Tooltip
          contentStyle={{
            background: '#11161d',
            border: '1px solid #1c242e',
            fontFamily: 'IBM Plex Mono',
            fontSize: 11,
          }}
          labelStyle={{ color: '#66788a' }}
          formatter={(v) => fmtUsd(Number(v))}
        />
        <Area type="monotone" dataKey="close" name="Cierre" stroke="#3ddc97" strokeWidth={1.5} fill="url(#close-fill)" dot={false} />
        <Line type="monotone" dataKey="sma200" name="SMA200" stroke="#ffb454" strokeWidth={1} strokeDasharray="4 3" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

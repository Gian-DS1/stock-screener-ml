import { useState } from 'react'
import { Area, AreaChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, ComposedChart } from 'recharts'
import { ExternalLink, X } from 'lucide-react'
import { useChart, useNews, useSignalStatus, type Signal } from '../lib/api'
import { featureLabel, fmtDate, fmtSignedPct, fmtUsd } from '../lib/format'
import { Button, Panel, Spinner, Tag } from './ui'
import AddPositionModal from './AddPositionModal'
import clsx from 'clsx'

export default function SignalDetail({ signal, onClose }: { signal: Signal; onClose: () => void }) {
  const { data: chart } = useChart(signal.ticker)
  const { data: news } = useNews(signal.ticker)
  const statusMutation = useSignalStatus()
  const [showBuy, setShowBuy] = useState(false)

  const chartData =
    chart?.dates.map((d, i) => ({ date: d, close: chart.close[i], sma200: chart.sma200[i] })) ?? []

  const maxShap = Math.max(...signal.shap.map((s) => Math.abs(s.shap)), 1e-9)

  return (
    <aside className="slide-in w-[380px] shrink-0">
      <Panel
        title={`${signal.ticker} · análisis`}
        className="sticky top-16"
        right={
          <button onClick={onClose} className="text-muted transition-colors hover:text-fg">
            <X className="size-4" />
          </button>
        }
      >
        <div className="max-h-[calc(100vh-9rem)] space-y-5 overflow-y-auto p-4">
          {/* cabecera */}
          <div>
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-lg font-semibold">{signal.ticker}</span>
              <span className="tnum text-lg">{fmtUsd(signal.price)}</span>
            </div>
            <div className="flex items-center justify-between text-xs text-muted">
              <span className="truncate">{signal.company}</span>
              <span className={clsx('tnum', (signal.pct_vs_sma200 ?? 0) <= 0 ? 'text-pos' : 'text-warn')}>
                {fmtSignedPct(signal.pct_vs_sma200)} vs SMA200
              </span>
            </div>
          </div>

          {/* gráfico */}
          <div className="h-44 border border-hairline bg-ink/40 p-1">
            {chartData.length === 0 ? (
              <Spinner />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
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
            )}
          </div>

          {/* por qué dispara: SHAP */}
          <div>
            <h3 className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
              Por qué dispara el modelo
            </h3>
            <div className="space-y-1.5">
              {signal.shap.map((item) => (
                <div key={item.feature} className="flex items-center gap-2 text-xs">
                  <span className="w-36 shrink-0 truncate text-muted" title={item.feature}>
                    {featureLabel(item.feature)}
                  </span>
                  <div className="relative h-2.5 flex-1">
                    <div className="absolute inset-y-0 left-1/2 w-px bg-edge" />
                    <div
                      className={clsx('absolute inset-y-0', item.shap >= 0 ? 'left-1/2 bg-pos/70' : 'right-1/2 bg-neg/70')}
                      style={{ width: `${(Math.abs(item.shap) / maxShap) * 48}%` }}
                    />
                  </div>
                  <span className={clsx('tnum w-12 shrink-0 text-right', item.shap >= 0 ? 'text-pos' : 'text-neg')}>
                    {item.shap >= 0 ? '+' : ''}{item.shap.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* desglose de calidad */}
          <div>
            <h3 className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
              Calidad {signal.quality_score.toFixed(0)}/100
            </h3>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {Object.entries(signal.quality_breakdown).map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-hairline/50 py-0.5">
                  <span className="truncate text-muted">{featureLabel(k)}</span>
                  <span className="tnum">{v.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* noticias */}
          <div>
            <h3 className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
              Noticias recientes
            </h3>
            {!news ? (
              <Spinner />
            ) : news.length === 0 ? (
              <p className="text-xs text-muted">Sin titulares disponibles.</p>
            ) : (
              <ul className="space-y-2">
                {news.slice(0, 6).map((n, i) => (
                  <li key={i} className="text-xs">
                    <a
                      href={n.url}
                      target="_blank"
                      rel="noreferrer"
                      className="group flex items-start gap-1.5 text-fg/90 hover:text-info"
                    >
                      {n.sentiment != null && (
                        <span
                          className={clsx(
                            'mt-1 size-1.5 shrink-0 rounded-full',
                            n.sentiment > 0.15 ? 'bg-pos' : n.sentiment < -0.15 ? 'bg-neg' : 'bg-faint',
                          )}
                        />
                      )}
                      <span className="leading-snug">{n.headline}</span>
                      <ExternalLink className="mt-0.5 size-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-60" />
                    </a>
                    <span className="ml-3 font-mono text-[10px] text-faint">
                      {n.source} · {fmtDate(n.date)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* acciones */}
          <div className="flex gap-2 border-t border-hairline pt-4">
            <Button tone="primary" className="flex-1" onClick={() => setShowBuy(true)}>
              Registrar posición
            </Button>
            {signal.status !== 'dismissed' ? (
              <Button onClick={() => statusMutation.mutate({ id: signal.id, status: 'dismissed' })}>
                Descartar
              </Button>
            ) : (
              <Button onClick={() => statusMutation.mutate({ id: signal.id, status: 'new' })}>
                Restaurar
              </Button>
            )}
          </div>
          {signal.status === 'bought' && (
            <div className="text-center"><Tag tone="info">ya registrada como comprada</Tag></div>
          )}
        </div>
      </Panel>

      {showBuy && (
        <AddPositionModal
          ticker={signal.ticker}
          defaultPrice={signal.price}
          signalId={signal.id}
          onClose={() => setShowBuy(false)}
        />
      )}
    </aside>
  )
}

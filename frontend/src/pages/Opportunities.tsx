import { useMemo, useState } from 'react'
import { useHealth, useSignals, type Signal } from '../lib/api'
import { fmtDate, fmtSignedPct, fmtUsd } from '../lib/format'
import { Empty, Panel, ProbBar, QualityGauge, Spinner, Tag } from '../components/ui'
import SignalDetail from '../components/SignalDetail'
import clsx from 'clsx'

export default function Opportunities() {
  const { data: signals, isLoading, error } = useSignals(45)
  const { data: health } = useHealth()
  const [selected, setSelected] = useState<Signal | null>(null)
  const [showDismissed, setShowDismissed] = useState(false)
  const threshold = health?.model?.threshold

  const visible = useMemo(() => {
    const list = (signals ?? []).filter((s) => showDismissed || s.status !== 'dismissed')
    return [...list].sort((a, b) => b.combined_score - a.combined_score)
  }, [signals, showDismissed])

  if (isLoading) return <Spinner label="buscando objetivos" />
  if (error) return <Empty>Error cargando señales: {String(error)}</Empty>

  return (
    <div className="flex gap-4">
      <Panel
        title={`Objetivos en la mira · ${visible.length}`}
        className="min-w-0 flex-1"
        dataTour="opp-table"
        right={
          <label className="flex cursor-pointer items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted">
            <input
              type="checkbox"
              checked={showDismissed}
              onChange={(e) => setShowDismissed(e.target.checked)}
              className="accent-[#3ddc97]"
            />
            ver descartadas
          </label>
        }
      >
        {visible.length === 0 ? (
          <Empty>
            Sin señales activas. El francotirador no dispara hasta que la probabilidad, la calidad
            y el precio estén alineados — eso es lo esperado la mayoría de los días.
          </Empty>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline font-mono text-[10px] uppercase tracking-[0.15em] text-faint">
                <th className="px-4 py-2 text-left">Ticker</th>
                <th className="px-2 py-2 text-left">Sector</th>
                <th className="px-2 py-2 text-left">Probabilidad</th>
                <th className="px-2 py-2 text-left">Calidad</th>
                <th className="px-2 py-2 text-right">Score</th>
                <th className="px-2 py-2 text-right">Precio</th>
                <th className="px-2 py-2 text-right">vs SMA200</th>
                <th className="px-2 py-2 text-right">Fecha</th>
                <th className="px-4 py-2 text-right">Estado</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((s, i) => (
                <tr
                  key={s.id}
                  onClick={() => setSelected(s)}
                  className={clsx(
                    'rise cursor-pointer border-b border-hairline/60 transition-colors hover:bg-panel-2',
                    selected?.id === s.id && 'bg-panel-2',
                    s.status === 'dismissed' && 'opacity-45',
                  )}
                  style={{ animationDelay: `${Math.min(i * 35, 400)}ms` }}
                >
                  <td className="px-4 py-2.5">
                    <div className="font-mono font-semibold text-fg">{s.ticker}</div>
                    <div className="max-w-[180px] truncate text-xs text-muted">{s.company}</div>
                  </td>
                  <td className="px-2 py-2.5 text-xs text-muted">{s.sector ?? '—'}</td>
                  <td className="px-2 py-2.5">
                    <div className="flex items-center gap-2">
                      <ProbBar value={s.probability} threshold={threshold} />
                      <span className="tnum text-xs text-pos">{(s.probability * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="px-2 py-2.5">
                    <QualityGauge score={s.quality_score} />
                  </td>
                  <td className="tnum px-2 py-2.5 text-right font-semibold text-fg">
                    {(s.combined_score * 100).toFixed(0)}
                  </td>
                  <td className="tnum px-2 py-2.5 text-right">{fmtUsd(s.price)}</td>
                  <td
                    className={clsx(
                      'tnum px-2 py-2.5 text-right',
                      (s.pct_vs_sma200 ?? 0) <= 0 ? 'text-pos' : 'text-warn',
                    )}
                  >
                    {fmtSignedPct(s.pct_vs_sma200)}
                  </td>
                  <td className="tnum px-2 py-2.5 text-right text-xs text-muted">{fmtDate(s.date)}</td>
                  <td className="px-4 py-2.5 text-right">
                    {s.status === 'new' && <Tag tone="pos">nueva</Tag>}
                    {s.status === 'bought' && <Tag tone="info">comprada</Tag>}
                    {s.status === 'dismissed' && <Tag>descartada</Tag>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {selected && <SignalDetail signal={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

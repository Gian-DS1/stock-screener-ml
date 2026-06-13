import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronsUpDown, Search } from 'lucide-react'
import { useHealth, useSignals, type Signal } from '../lib/api'
import { fmtDate, fmtSignedPct, fmtUsd } from '../lib/format'
import { Empty, Panel, ProbBar, QualityGauge, Spinner, Tag } from '../components/ui'
import SignalDetail from '../components/SignalDetail'
import clsx from 'clsx'

type SortKey =
  | 'ticker' | 'sector' | 'probability' | 'quality_score'
  | 'combined_score' | 'price' | 'pct_vs_sma200' | 'date'

const COLUMNS: { key: SortKey; label: string; align: 'left' | 'right' }[] = [
  { key: 'ticker', label: 'Ticker', align: 'left' },
  { key: 'sector', label: 'Sector', align: 'left' },
  { key: 'probability', label: 'Probabilidad', align: 'left' },
  { key: 'quality_score', label: 'Calidad', align: 'left' },
  { key: 'combined_score', label: 'Score', align: 'right' },
  { key: 'price', label: 'Precio', align: 'right' },
  { key: 'pct_vs_sma200', label: 'vs SMA200', align: 'right' },
  { key: 'date', label: 'Fecha', align: 'right' },
]

export default function Opportunities() {
  const { data: signals, isLoading, error } = useSignals(45)
  const { data: health } = useHealth()
  const [selected, setSelected] = useState<Signal | null>(null)
  const [showDismissed, setShowDismissed] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('combined_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [search, setSearch] = useState('')
  const [sector, setSector] = useState('')
  const [minProb, setMinProb] = useState(0)
  const [minQuality, setMinQuality] = useState(0)
  const threshold = health?.model?.threshold

  const sectors = useMemo(
    () => [...new Set((signals ?? []).map((s) => s.sector).filter(Boolean))].sort() as string[],
    [signals],
  )

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else {
      setSortKey(key)
      setSortDir(key === 'ticker' || key === 'sector' ? 'asc' : 'desc')
    }
  }

  const visible = useMemo(() => {
    const q = search.trim().toUpperCase()
    let list = (signals ?? []).filter((s) => showDismissed || s.status !== 'dismissed')
    if (q) list = list.filter((s) => s.ticker.includes(q) || (s.company ?? '').toUpperCase().includes(q))
    if (sector) list = list.filter((s) => s.sector === sector)
    if (minProb > 0) list = list.filter((s) => s.probability * 100 >= minProb)
    if (minQuality > 0) list = list.filter((s) => s.quality_score >= minQuality)

    const dir = sortDir === 'asc' ? 1 : -1
    return [...list].sort((a, b) => {
      const av = a[sortKey] as string | number | null
      const bv = b[sortKey] as string | number | null
      if (typeof av === 'string' || typeof bv === 'string')
        return dir * String(av ?? '').localeCompare(String(bv ?? ''))
      return dir * ((av ?? -Infinity) - (bv ?? -Infinity))
    })
  }, [signals, showDismissed, search, sector, minProb, minQuality, sortKey, sortDir])

  if (isLoading) return <Spinner label="buscando oportunidades" />
  if (error) return <Empty>Error cargando señales: {String(error)}</Empty>

  const total = (signals ?? []).filter((s) => showDismissed || s.status !== 'dismissed').length
  const num = 'w-16 border border-edge bg-ink px-2 py-1 font-mono text-xs text-fg outline-none focus:border-pos/50'

  return (
    <div className="flex gap-4">
      <Panel
        title={`Oportunidades · ${visible.length}${visible.length !== total ? ` / ${total}` : ''}`}
        className="min-w-0 flex-1"
        dataTour="opp-table"
        right={
          <label className="flex cursor-pointer items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted">
            <input type="checkbox" checked={showDismissed} onChange={(e) => setShowDismissed(e.target.checked)} className="accent-[#3ddc97]" />
            ver descartadas
          </label>
        }
      >
        {/* barra de filtros */}
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline px-4 py-2.5">
          <div className="flex items-center gap-1.5 border border-edge bg-ink px-2 py-1">
            <Search className="size-3.5 text-faint" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar ticker o empresa"
              className="w-44 bg-transparent text-xs text-fg outline-none placeholder:text-faint"
            />
          </div>
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            className="border border-edge bg-ink px-2 py-1 text-xs text-fg outline-none focus:border-pos/50"
          >
            <option value="">Todos los sectores</option>
            {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <label className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted">
            Prob ≥
            <input type="number" min={0} max={100} value={minProb || ''} onChange={(e) => setMinProb(Number(e.target.value) || 0)} className={num} placeholder="0" />%
          </label>
          <label className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted">
            Calidad ≥
            <input type="number" min={0} max={100} value={minQuality || ''} onChange={(e) => setMinQuality(Number(e.target.value) || 0)} className={num} placeholder="0" />
          </label>
          {(search || sector || minProb || minQuality) && (
            <button
              onClick={() => { setSearch(''); setSector(''); setMinProb(0); setMinQuality(0) }}
              className="font-mono text-[10px] uppercase tracking-wider text-faint hover:text-fg"
            >
              limpiar
            </button>
          )}
        </div>

        {visible.length === 0 ? (
          <Empty>
            {total === 0
              ? 'Sin señales activas. El sistema es selectivo: no genera una señal hasta que la probabilidad, la calidad y el precio están alineados — eso es lo esperado la mayoría de los días.'
              : 'Ninguna oportunidad coincide con los filtros. Prueba a relajarlos o pulsa “limpiar”.'}
          </Empty>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline font-mono text-[10px] uppercase tracking-[0.15em] text-faint">
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    onClick={() => toggleSort(c.key)}
                    className={clsx(
                      'cursor-pointer select-none px-2 py-2 transition-colors first:pl-4 hover:text-fg',
                      c.align === 'right' ? 'text-right' : 'text-left',
                    )}
                  >
                    <span className={clsx('inline-flex items-center gap-1', c.align === 'right' && 'flex-row-reverse')}>
                      {c.label}
                      {sortKey === c.key ? (
                        sortDir === 'desc' ? <ArrowDown className="size-3 text-pos" /> : <ArrowUp className="size-3 text-pos" />
                      ) : (
                        <ChevronsUpDown className="size-3 opacity-30" />
                      )}
                    </span>
                  </th>
                ))}
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
                  style={{ animationDelay: `${Math.min(i * 30, 350)}ms` }}
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
                  <td className="px-2 py-2.5"><QualityGauge score={s.quality_score} /></td>
                  <td className="tnum px-2 py-2.5 text-right font-semibold text-fg">{(s.combined_score * 100).toFixed(0)}</td>
                  <td className="tnum px-2 py-2.5 text-right">{fmtUsd(s.price)}</td>
                  <td className={clsx('tnum px-2 py-2.5 text-right', (s.pct_vs_sma200 ?? 0) <= 0 ? 'text-pos' : 'text-warn')}>
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

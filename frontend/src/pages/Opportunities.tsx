import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronsUpDown, Eye, Search, Target } from 'lucide-react'
import { useHealth, useSignals, useWatchlist, type Signal } from '../lib/api'
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

type Mode = 'signals' | 'watch'

export default function Opportunities() {
  const [mode, setMode] = useState<Mode>('signals')
  const { data: signals, isLoading: loadingSignals } = useSignals(45)
  const { data: watch, isLoading: loadingWatch } = useWatchlist(mode === 'watch')
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

  const isWatch = mode === 'watch'
  const isLoading = isWatch ? loadingWatch : loadingSignals
  const source = isWatch ? watch : signals
  const dismissedCount = (signals ?? []).filter((s) => s.status === 'dismissed').length

  const sectors = useMemo(
    () => [...new Set((source ?? []).map((s) => s.sector).filter(Boolean))].sort() as string[],
    [source],
  )

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else {
      setSortKey(key)
      setSortDir(key === 'ticker' || key === 'sector' ? 'asc' : 'desc')
    }
  }

  // en modo señales se ordena por defecto por score; en observación, por calidad
  const effectiveSortKey: SortKey = isWatch && sortKey === 'combined_score' ? 'quality_score' : sortKey

  const visible = useMemo(() => {
    const q = search.trim().toUpperCase()
    let list = (source ?? []).filter((s) => (isWatch ? true : showDismissed || s.status !== 'dismissed'))
    if (q) list = list.filter((s) => s.ticker.includes(q) || (s.company ?? '').toUpperCase().includes(q))
    if (sector) list = list.filter((s) => s.sector === sector)
    if (minProb > 0) list = list.filter((s) => s.probability * 100 >= minProb)
    if (minQuality > 0) list = list.filter((s) => s.quality_score >= minQuality)

    const dir = sortDir === 'asc' ? 1 : -1
    return [...list].sort((a, b) => {
      const av = a[effectiveSortKey] as string | number | null
      const bv = b[effectiveSortKey] as string | number | null
      if (typeof av === 'string' || typeof bv === 'string')
        return dir * String(av ?? '').localeCompare(String(bv ?? ''))
      return dir * ((av ?? -Infinity) - (bv ?? -Infinity))
    })
  }, [source, isWatch, showDismissed, search, sector, minProb, minQuality, effectiveSortKey, sortDir])

  const total = isWatch
    ? (source ?? []).length
    : (signals ?? []).filter((s) => showDismissed || s.status !== 'dismissed').length
  const num = 'w-16 border border-edge bg-ink px-2 py-1 font-mono text-xs text-fg outline-none focus:border-pos/50'

  return (
    <div className="flex gap-4">
      <Panel
        title={isWatch ? `En observación · ${visible.length}` : `Oportunidades · ${visible.length}${visible.length !== total ? ` / ${total}` : ''}`}
        className="min-w-0 flex-1"
        dataTour="opp-table"
        right={
          !isWatch && (
            <label className="flex cursor-pointer items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted">
              <input type="checkbox" checked={showDismissed} onChange={(e) => setShowDismissed(e.target.checked)} className="accent-[#3ddc97]" />
              ver descartadas{dismissedCount > 0 ? ` (${dismissedCount})` : ''}
            </label>
          )
        }
      >
        {/* selector de modo */}
        <div className="flex border-b border-hairline">
          <button
            onClick={() => setMode('signals')}
            className={clsx(
              'flex items-center gap-2 border-b-2 px-4 py-2.5 font-mono text-xs uppercase tracking-wider transition-colors',
              !isWatch ? 'border-pos text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            <Target className="size-3.5" /> Señales (compra)
          </button>
          <button
            onClick={() => setMode('watch')}
            className={clsx(
              'flex items-center gap-2 border-b-2 px-4 py-2.5 font-mono text-xs uppercase tracking-wider transition-colors',
              isWatch ? 'border-info text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            <Eye className="size-3.5" /> En observación
          </button>
        </div>

        {isWatch && (
          <p className="border-b border-hairline bg-info/[0.05] px-4 py-2 text-xs leading-snug text-muted">
            Empresas de alta calidad que <strong className="text-fg/90">aún no son compra</strong> —
            normalmente porque no están en descuento o el modelo no ve el momento. Aquí aparecen
            líderes como las MAG 7 cuando cotizan caros. Cada fila explica por qué no disparó.
          </p>
        )}

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

        {isLoading ? (
          <Spinner label={isWatch ? 'evaluando el universo' : 'buscando oportunidades'} />
        ) : visible.length === 0 ? (
          <Empty>
            {isWatch
              ? 'No hay empresas en observación con estos filtros.'
              : showDismissed && dismissedCount === 0
                ? 'No has descartado ninguna señal todavía. Cuando descartes una desde su detalle, aparecerá aquí.'
                : total === 0
                  ? 'Sin señales de compra activas. El sistema es selectivo: no genera una señal hasta que la probabilidad, la calidad y el precio están alineados — eso es lo esperado la mayoría de los días. Mira la pestaña “En observación” para ver empresas de calidad que aún no son compra.'
                  : 'Ninguna coincide con los filtros. Prueba a relajarlos o pulsa “limpiar”.'}
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
                      {effectiveSortKey === c.key ? (
                        sortDir === 'desc' ? <ArrowDown className="size-3 text-pos" /> : <ArrowUp className="size-3 text-pos" />
                      ) : (
                        <ChevronsUpDown className="size-3 opacity-30" />
                      )}
                    </span>
                  </th>
                ))}
                <th className="px-4 py-2 text-right">{isWatch ? 'Motivo' : 'Estado'}</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((s, i) => (
                <tr
                  key={`${s.ticker}-${s.id}`}
                  onClick={() => setSelected(s)}
                  className={clsx(
                    'rise cursor-pointer border-b border-hairline/60 transition-colors hover:bg-panel-2',
                    selected?.ticker === s.ticker && 'bg-panel-2',
                    s.status === 'dismissed' && 'opacity-45',
                  )}
                  style={{ animationDelay: `${Math.min(i * 25, 300)}ms` }}
                >
                  <td className="px-4 py-2.5">
                    <div className="font-mono font-semibold text-fg">{s.ticker}</div>
                    <div className="max-w-[180px] truncate text-xs text-muted">{s.company}</div>
                  </td>
                  <td className="px-2 py-2.5 text-xs text-muted">{s.sector ?? '—'}</td>
                  <td className="px-2 py-2.5">
                    <div className="flex items-center gap-2">
                      <ProbBar value={s.probability} threshold={threshold} />
                      <span className={clsx('tnum text-xs', isWatch ? 'text-muted' : 'text-pos')}>
                        {(s.probability * 100).toFixed(0)}%
                      </span>
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
                    {isWatch ? (
                      <span className="text-xs text-faint" title={s.reasons?.join(' · ')}>
                        {(s.reasons?.[0] ?? '').includes('descuento') ? 'sin descuento' : 'sin momento'}
                      </span>
                    ) : (
                      <>
                        {s.status === 'new' && <Tag tone="pos">nueva</Tag>}
                        {s.status === 'bought' && <Tag tone="info">comprada</Tag>}
                        {s.status === 'dismissed' && <Tag>descartada</Tag>}
                      </>
                    )}
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

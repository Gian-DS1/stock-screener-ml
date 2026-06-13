import { useState } from 'react'
import clsx from 'clsx'
import { Bell, BellOff, Plus, Trash2 } from 'lucide-react'
import {
  useAlertMutation,
  useAlerts,
  usePortfolio,
  usePortfolioMutation,
  type Position,
} from '../lib/api'
import { fmtDate, fmtDateTime, fmtSignedPct, fmtUsd } from '../lib/format'
import { Button, Empty, Panel, Spinner, Stat, Tag } from '../components/ui'
import AddPositionModal from '../components/AddPositionModal'

const ALERT_TONE: Record<string, 'pos' | 'neg' | 'warn' | 'info' | 'muted'> = {
  STOP_LOSS: 'neg',
  TRAILING: 'warn',
  TIME_LIMIT: 'warn',
  TP_PARCIAL: 'pos',
  NUEVA_SENAL: 'info',
  DRIFT: 'warn',
  UNIVERSO: 'info',
}

function RuleRow({ label, value, hit, hint }: { label: string; value: string; hit?: boolean; hint?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-hairline/50 py-1 text-xs" title={hint}>
      <span className={clsx(hit ? 'font-semibold text-neg' : 'text-muted')}>{label}</span>
      <span className={clsx('tnum', hit ? 'font-semibold text-neg' : 'text-fg')}>{value}</span>
    </div>
  )
}

function PositionCard({ p, onClose, onDelete }: { p: Position; onClose: (p: Position) => void; onDelete: (p: Position) => void }) {
  const r = p.rules
  const ret = r?.return_pct ?? 0
  return (
    <div className="rise border border-edge bg-panel-2/60 p-4">
      <div className="mb-3 flex items-start justify-between">
        <div>
          <span className="font-mono text-base font-semibold">{p.ticker}</span>
          <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-faint">
            desde {fmtDate(p.opened_at)}
          </span>
        </div>
        <div className="text-right">
          <div className={clsx('tnum text-lg font-semibold', ret >= 0 ? 'text-pos' : 'text-neg')}>
            {fmtSignedPct(ret)}
          </div>
          <div className="tnum text-xs text-muted">{fmtUsd(p.pnl)} P&L</div>
        </div>
      </div>

      <div className="mb-3 grid grid-cols-3 gap-2">
        <Stat label="Entrada" value={fmtUsd(p.entry_price)} />
        <Stat label="Último" value={fmtUsd(p.last_price)} />
        <Stat label="Valor" value={fmtUsd(p.market_value, 0)} />
      </div>

      {r && (
        <div className="mb-3">
          <RuleRow
            label={`Stop loss (-12%)`}
            value={fmtUsd(r.stop_loss_price)}
            hit={(p.last_price ?? p.entry_price) <= r.stop_loss_price}
            hint="venta total si el precio cae 12% bajo la entrada"
          />
          <RuleRow
            label={r.trailing_active ? 'Trailing stop (activo)' : 'Trailing (se activa en +5%)'}
            value={r.trailing_stop_price ? fmtUsd(r.trailing_stop_price) : `pico ${fmtUsd(r.peak_price)}`}
            hit={!!r.trailing_stop_price && (p.last_price ?? Infinity) <= r.trailing_stop_price}
            hint="tras subir 5%, vende si retrocede 8% desde el pico"
          />
          <RuleRow
            label="Límite de tiempo"
            value={`${r.days_left} días restantes`}
            hit={r.days_left === 0}
            hint="120 días hábiles máximo: el capital estancado tiene costo de oportunidad"
          />
          <RuleRow
            label={r.partial_tp_done ? 'TP parcial ejecutado' : 'Take profit parcial (+15%)'}
            value={r.partial_tp_done ? '✓ free roll' : fmtUsd(r.take_profit_price)}
            hint="al +15%, vende 33% y deja correr el resto protegido"
          />
        </div>
      )}

      <div className="flex gap-2">
        <Button className="flex-1" onClick={() => onClose(p)}>Cerrar / vender</Button>
        <Button tone="ghost" onClick={() => onDelete(p)} className="px-2">
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

function CloseModal({ p, onDone }: { p: Position; onDone: () => void }) {
  const { close } = usePortfolioMutation()
  const [price, setPrice] = useState(p.last_price?.toFixed(2) ?? '')
  const [shares, setShares] = useState('')
  const field =
    'w-full border border-edge bg-ink px-2.5 py-1.5 font-mono text-sm text-fg outline-none focus:border-pos/50'
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-sm" onClick={onDone}>
      <div className="w-[340px] border border-edge bg-panel p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-4 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-muted">
          Cerrar {p.ticker}
        </h2>
        <div className="space-y-3">
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-faint">Precio de venta</span>
            <input className={field} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-faint">
              Títulos (vacío = todos los {p.shares})
            </span>
            <input className={field} inputMode="decimal" value={shares} onChange={(e) => setShares(e.target.value)} placeholder={`${p.shares}`} />
          </label>
          <Button
            tone="danger"
            className="w-full"
            disabled={close.isPending}
            onClick={async () => {
              const close_price = parseFloat(price)
              if (!(close_price > 0)) return
              await close.mutateAsync({
                id: p.id,
                close_price,
                ...(shares ? { shares: parseFloat(shares) } : {}),
              })
              onDone()
            }}
          >
            Confirmar venta
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function Portfolio() {
  const { data, isLoading } = usePortfolio('all')
  const { data: alerts } = useAlerts()
  const { markRead, markAll } = useAlertMutation()
  const { remove } = usePortfolioMutation()
  const [showAdd, setShowAdd] = useState(false)
  const [closing, setClosing] = useState<Position | null>(null)

  if (isLoading || !data) return <Spinner label="cargando portafolio" />

  const open = data.positions.filter((p) => p.status === 'open')
  const closed = data.positions.filter((p) => p.status === 'closed')
  const unread = (alerts ?? []).filter((a) => !a.read)

  return (
    <div className="grid grid-cols-[1fr_360px] gap-4">
      <div className="space-y-4">
        <Panel
          dataTour="portfolio-posiciones"
          title={`Posiciones abiertas · ${open.length}/${data.max_positions}`}
          right={
            <Button tone="primary" onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 py-1">
              <Plus className="size-3.5" /> Posición
            </Button>
          }
        >
          {data.warnings.length > 0 && (
            <div className="border-b border-hairline bg-warn/5 px-4 py-2">
              {data.warnings.map((w, i) => (
                <p key={i} className="text-xs text-warn">⚠ {w}</p>
              ))}
            </div>
          )}
          {open.length === 0 ? (
            <Empty>
              Sin posiciones abiertas. Cuando compres algo de la página de oportunidades,
              regístralo aquí y el sistema vigilará tus reglas de salida cada día.
            </Empty>
          ) : (
            <div className="grid grid-cols-1 gap-3 p-4 xl:grid-cols-2">
              {open.map((p) => (
                <PositionCard
                  key={p.id}
                  p={p}
                  onClose={setClosing}
                  onDelete={(pos) => {
                    if (confirm(`¿Eliminar el registro de ${pos.ticker}? (no afecta tu broker)`))
                      remove.mutate(pos.id)
                  }}
                />
              ))}
            </div>
          )}
        </Panel>

        {closed.length > 0 && (
          <Panel title={`Historial cerrado · ${closed.length}`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline font-mono text-[10px] uppercase tracking-[0.15em] text-faint">
                  <th className="px-4 py-2 text-left">Ticker</th>
                  <th className="px-2 py-2 text-right">Entrada</th>
                  <th className="px-2 py-2 text-right">Salida</th>
                  <th className="px-2 py-2 text-right">Retorno</th>
                  <th className="px-4 py-2 text-right">Cerrada</th>
                </tr>
              </thead>
              <tbody>
                {closed.map((p) => {
                  const ret = p.close_price ? p.close_price / p.entry_price - 1 : null
                  return (
                    <tr key={p.id} className="border-b border-hairline/60">
                      <td className="px-4 py-2 font-mono font-medium">{p.ticker}</td>
                      <td className="tnum px-2 py-2 text-right">{fmtUsd(p.entry_price)}</td>
                      <td className="tnum px-2 py-2 text-right">{fmtUsd(p.close_price)}</td>
                      <td className={clsx('tnum px-2 py-2 text-right', (ret ?? 0) >= 0 ? 'text-pos' : 'text-neg')}>
                        {fmtSignedPct(ret)}
                      </td>
                      <td className="tnum px-4 py-2 text-right text-xs text-muted">{fmtDate(p.closed_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </Panel>
        )}
      </div>

      <Panel
        dataTour="portfolio-alertas"
        title={`Alertas ${unread.length > 0 ? `· ${unread.length} sin leer` : ''}`}
        className="self-start"
        right={
          unread.length > 0 && (
            <button
              onClick={() => markAll.mutate()}
              className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-muted hover:text-fg"
            >
              <BellOff className="size-3" /> marcar todas
            </button>
          )
        }
      >
        {(alerts ?? []).length === 0 ? (
          <Empty>Sin alertas. Te avisaré aquí cuándo vender según tus reglas.</Empty>
        ) : (
          <ul className="max-h-[70vh] divide-y divide-hairline/60 overflow-y-auto">
            {(alerts ?? []).map((a) => (
              <li
                key={a.id}
                onClick={() => !a.read && markRead.mutate(a.id)}
                className={clsx('cursor-pointer px-4 py-3 transition-colors hover:bg-panel-2', a.read && 'opacity-45')}
              >
                <div className="mb-1 flex items-center gap-2">
                  <Tag tone={ALERT_TONE[a.type] ?? 'muted'}>{a.type.replace('_', ' ')}</Tag>
                  {!a.read && <Bell className="size-3 text-warn" />}
                  <span className="ml-auto font-mono text-[10px] text-faint">{fmtDateTime(a.created_at)}</span>
                </div>
                <p className="text-xs leading-snug text-fg/90">{a.message}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {showAdd && <AddPositionModal onClose={() => setShowAdd(false)} />}
      {closing && <CloseModal p={closing} onDone={() => setClosing(null)} />}
    </div>
  )
}

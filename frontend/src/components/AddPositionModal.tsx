import { useState } from 'react'
import { X } from 'lucide-react'
import { usePortfolioMutation, useSignalStatus } from '../lib/api'
import { Button } from './ui'

export default function AddPositionModal({
  ticker,
  defaultPrice,
  signalId,
  onClose,
}: {
  ticker?: string
  defaultPrice?: number
  signalId?: number
  onClose: () => void
}) {
  const { create } = usePortfolioMutation()
  const signalStatus = useSignalStatus()
  const [form, setForm] = useState({
    ticker: ticker ?? '',
    opened_at: new Date().toISOString().slice(0, 10),
    entry_price: defaultPrice?.toFixed(2) ?? '',
    shares: '',
  })
  const [error, setError] = useState('')

  const submit = async () => {
    const entry_price = parseFloat(form.entry_price)
    const shares = parseFloat(form.shares)
    if (!form.ticker || !(entry_price > 0) || !(shares > 0)) {
      setError('Completa ticker, precio y cantidad (positivos)')
      return
    }
    try {
      await create.mutateAsync({
        ticker: form.ticker.toUpperCase(),
        opened_at: form.opened_at,
        entry_price,
        shares,
      })
      if (signalId) signalStatus.mutate({ id: signalId, status: 'bought' })
      onClose()
    } catch (e) {
      setError(String(e))
    }
  }

  const field =
    'w-full border border-edge bg-ink px-2.5 py-1.5 font-mono text-sm text-fg outline-none focus:border-pos/50'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-[360px] border border-edge bg-panel p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-muted">
            Registrar posición real
          </h2>
          <button onClick={onClose} className="text-muted hover:text-fg">
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-3">
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-faint">Ticker</span>
            <input
              className={field}
              value={form.ticker}
              onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
              placeholder="AAPL"
            />
          </label>
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-faint">Fecha de compra</span>
            <input
              type="date"
              className={field}
              value={form.opened_at}
              onChange={(e) => setForm({ ...form, opened_at: e.target.value })}
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-faint">Precio</span>
              <input
                className={field}
                inputMode="decimal"
                value={form.entry_price}
                onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
                placeholder="0.00"
              />
            </label>
            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-faint">Títulos</span>
              <input
                className={field}
                inputMode="decimal"
                value={form.shares}
                onChange={(e) => setForm({ ...form, shares: e.target.value })}
                placeholder="0"
              />
            </label>
          </div>

          {error && <p className="text-xs text-neg">{error}</p>}

          <div className="flex gap-2 pt-1">
            <Button tone="primary" className="flex-1" onClick={submit} disabled={create.isPending}>
              Guardar
            </Button>
            <Button onClick={onClose}>Cancelar</Button>
          </div>
          <p className="text-[11px] leading-snug text-faint">
            El sistema no ejecuta órdenes: registra lo que compraste para vigilar tus reglas de
            salida y avisarte cuándo actuar.
          </p>
        </div>
      </div>
    </div>
  )
}

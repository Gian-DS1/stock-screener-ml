import { useEffect, useRef, useState } from 'react'
import { Activity, Clock } from 'lucide-react'
import { usePipelineStatus } from '../lib/api'

function fmtDur(totalSec: number): string {
  if (totalSec < 60) return '< 1 min'
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}

/** Barra de progreso global del pipeline (0–100 %) con tiempo restante en cuenta
 *  regresiva (horas y minutos). Visible solo mientras hay un run activo; lee el
 *  estado de la tabla `runs`, así que refleja ejecuciones del dashboard, el CLI
 *  o la tarea programada. */
export default function PipelineProgress() {
  const { data } = usePipelineStatus()
  const run = data?.running
  const lake = data?.data_lake
  const pct = Math.max(0, Math.min(100, run?.pct ?? 0))

  const [now, setNow] = useState(() => Date.now())
  const deadlineRef = useRef<number | null>(null)

  // Recalcula el "momento estimado de fin" cuando llega nuevo progreso del poll.
  useEffect(() => {
    if (!run) {
      deadlineRef.current = null
      return
    }
    const started = new Date(run.started_at + 'Z').getTime()
    const elapsed = Date.now() - started
    if (pct >= 3 && pct < 100 && elapsed > 3000) {
      const remainingMs = (elapsed * (100 - pct)) / pct
      deadlineRef.current = Date.now() + remainingMs
    } else if (pct >= 100) {
      deadlineRef.current = Date.now()
    }
  }, [run, pct])

  // Tic cada segundo: hace que la cuenta atrás baje de forma fluida entre polls.
  useEffect(() => {
    if (!run) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [run])

  if (!run) return null

  const started = new Date(run.started_at + 'Z').getTime()
  const elapsedSec = Math.max(0, Math.floor((now - started) / 1000))
  const remainingSec =
    deadlineRef.current !== null ? Math.max(0, Math.floor((deadlineRef.current - now) / 1000)) : null

  return (
    <div className="border-b border-warn/30 bg-warn/[0.07]">
      <div className="mx-auto flex max-w-[1480px] flex-col gap-1.5 px-4 py-2.5">
        <div className="flex items-center gap-3 font-mono text-xs">
          <Activity className="size-4 shrink-0 animate-pulse text-warn" />
          <span className="font-semibold uppercase tracking-wider text-warn">{run.kind}</span>
          <span className="text-fg/90">{run.phase ?? 'en curso'}</span>
          <span className="tnum font-semibold text-warn">{pct.toFixed(0)}%</span>

          <span className="ml-auto flex items-center gap-3 text-faint">
            {lake?.filings_8k != null && (
              <span className="tnum" title="8-K en el data lake (crece en vivo)">
                8-K: {lake.filings_8k.toLocaleString()}
              </span>
            )}
            <span className="tnum">transcurrido {fmtDur(elapsedSec)}</span>
            <span className="tnum flex items-center gap-1 text-warn">
              <Clock className="size-3" />
              {remainingSec !== null ? `${fmtDur(remainingSec)} restantes` : 'calculando…'}
            </span>
          </span>
        </div>

        <div className="h-1.5 w-full overflow-hidden bg-panel-2">
          <div
            className="h-full bg-warn transition-[width] duration-700 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  )
}

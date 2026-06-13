import { Activity } from 'lucide-react'
import { usePipelineStatus } from '../lib/api'

/** Barra de progreso en vivo del pipeline. Visible solo cuando hay un run activo.
 *  Lee el estado de la tabla `runs`, así que muestra ejecuciones lanzadas desde
 *  el dashboard, el CLI o la tarea programada de Windows. */
export default function PipelineProgress() {
  const { data } = usePipelineStatus()
  const run = data?.running
  const lake = data?.data_lake
  if (!run) return null

  const elapsed = Math.round((Date.now() - new Date(run.started_at + 'Z').getTime()) / 60000)
  const hasBar = run.total != null && run.total > 0

  return (
    <div className="border-b border-warn/30 bg-warn/[0.07]">
      <div className="mx-auto flex max-w-[1480px] flex-col gap-1.5 px-4 py-2.5">
        <div className="flex items-center gap-3 font-mono text-xs">
          <Activity className="size-4 shrink-0 animate-pulse text-warn" />
          <span className="font-semibold uppercase tracking-wider text-warn">{run.kind}</span>
          <span className="text-fg/90">{run.phase ?? 'en curso'}</span>
          {hasBar && (
            <span className="tnum text-muted">
              {run.current?.toLocaleString()} / {run.total?.toLocaleString()}
            </span>
          )}
          <span className="ml-auto flex items-center gap-3 text-faint">
            {lake?.filings_8k != null && (
              <span className="tnum" title="8-K en el data lake (crece en vivo)">
                8-K: {lake.filings_8k.toLocaleString()}
                {lake.filings_8k_scored != null && lake.filings_8k_scored > 0 &&
                  ` · ${lake.filings_8k_scored.toLocaleString()} con sentimiento`}
              </span>
            )}
            <span className="tnum">{elapsed} min</span>
          </span>
        </div>

        <div className="h-1.5 w-full overflow-hidden bg-panel-2">
          {hasBar ? (
            <div
              className="h-full bg-warn transition-[width] duration-500 ease-out"
              style={{ width: `${run.pct ?? 0}%` }}
            />
          ) : (
            // fase sin total conocido: barra indeterminada
            <div className="indeterminate h-full w-1/3 bg-warn/70" />
          )}
        </div>
        {hasBar && (
          <span className="tnum self-end font-mono text-[10px] text-faint">{run.pct}%</span>
        )}
      </div>
    </div>
  )
}

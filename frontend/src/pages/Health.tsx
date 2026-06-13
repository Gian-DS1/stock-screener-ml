import clsx from 'clsx'
import { Activity, Brain, Database } from 'lucide-react'
import { useHealth, usePipelineStatus, usePipelineTrigger } from '../lib/api'
import { featureLabel, fmtDateTime, fmtPct } from '../lib/format'
import { Button, Empty, Panel, Spinner, Stat, Tag } from '../components/ui'

function DriftLight({ label, report }: {
  label: string
  report?: { created_at: string; drifted: boolean; metric: number }
}) {
  const color = !report ? 'bg-faint' : report.drifted ? 'bg-neg' : 'bg-pos'
  const text = !report ? 'sin datos' : report.drifted ? 'DERIVA DETECTADA' : 'estable'
  return (
    <div className="flex items-center gap-3 border border-edge bg-panel-2/60 px-4 py-3">
      <span className={clsx('size-3 rounded-full', color, report?.drifted && 'pulse-dot')} />
      <div className="min-w-0">
        <div className="font-mono text-xs font-medium uppercase tracking-wider">{label}</div>
        <div className={clsx('text-xs', report?.drifted ? 'text-neg' : 'text-muted')}>
          {text}
          {report && (
            <span className="tnum ml-2 text-faint">
              métrica {report.metric.toFixed(3)} · {fmtDateTime(report.created_at)}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Health() {
  const { data, isLoading } = useHealth()
  const { data: status } = usePipelineStatus()
  const trigger = usePipelineTrigger()
  const running = status?.running?.kind ?? null

  if (isLoading || !data) return <Spinner label="leyendo diagnósticos" />
  const m = data.model

  const importances = Object.entries(m?.importances ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
  const maxImp = importances[0]?.[1] ?? 1

  return (
    <div className="space-y-4">
      {/* fila superior: modelo + drift */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel dataTour="salud-modelo" title="Modelo táctico activo" className="lg:col-span-2">
          {!m ? (
            <Empty>No hay modelo entrenado todavía. Lanza un entrenamiento para empezar.</Empty>
          ) : (
            <div className="space-y-4 p-4">
              <div className="grid grid-cols-3 gap-4 md:grid-cols-6">
                <Stat label="Entrenado" value={fmtDateTime(m.trained_at)} />
                <Stat label="Muestras" value={m.n_samples.toLocaleString()} />
                <Stat label="Features" value={m.n_features} />
                <Stat label="Umbral" value={m.threshold.toFixed(3)} tone="text-warn" />
                <Stat
                  label="Precisión OOF"
                  value={fmtPct(m.metrics.oof.precision)}
                  tone="text-pos"
                />
                <Stat label="Recall OOF" value={fmtPct(m.metrics.oof.recall)} />
              </div>
              <p className="border-l-2 border-pos/40 pl-3 text-xs leading-relaxed text-muted">
                Objetivo: ≥{fmtPct(m.min_return, 0)} de retorno máximo en {m.horizon_days} días
                hábiles. Base rate {fmtPct(m.metrics.oof.base_rate)} → el modelo selecciona con{' '}
                {fmtPct(m.metrics.oof.precision)} de acierto (modo selectivo:{' '}
                {m.metrics.oof.n_signals.toLocaleString()} señales de{' '}
                {m.metrics.oof.n_oof.toLocaleString()} oportunidades evaluadas).
              </p>

              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-hairline font-mono text-[10px] uppercase tracking-[0.15em] text-faint">
                    <th className="py-1.5 text-left">Fold</th>
                    <th className="py-1.5 text-left">Validación</th>
                    <th className="py-1.5 text-right">Train</th>
                    <th className="py-1.5 text-right">AP</th>
                    <th className="py-1.5 text-right">Precisión@umbral</th>
                    <th className="py-1.5 text-right">Señales</th>
                  </tr>
                </thead>
                <tbody>
                  {m.metrics.folds.map((f) => (
                    <tr key={f.fold} className="border-b border-hairline/50">
                      <td className="tnum py-1.5">{f.fold}</td>
                      <td className="tnum py-1.5 text-muted">{f.val_start} → {f.val_end}</td>
                      <td className="tnum py-1.5 text-right">{f.n_train.toLocaleString()}</td>
                      <td className="tnum py-1.5 text-right">{f.avg_precision?.toFixed(3) ?? '—'}</td>
                      <td className="tnum py-1.5 text-right">
                        {f.precision_at_thr != null ? fmtPct(f.precision_at_thr) : '—'}
                      </td>
                      <td className="tnum py-1.5 text-right">{f.signals_at_thr}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel dataTour="salud-drift" title="Deriva (drift)">
            <div className="space-y-3 p-4">
              <DriftLight label="Datos (34 features)" report={data.drift.data} />
              <DriftLight label="Predicciones (KS)" report={data.drift.prediction} />
              <p className="text-[11px] leading-snug text-faint">
                Si el mercado cambia de régimen, las distribuciones se alejan de las huellas de
                entrenamiento y conviene reentrenar antes de confiar en las señales.
              </p>
            </div>
          </Panel>

          <Panel title="Acciones">
            <div className="flex flex-col gap-2 p-4">
              <Button
                tone="primary"
                disabled={!!running}
                onClick={() => trigger.mutate('run-daily')}
                className="flex items-center justify-center gap-2"
              >
                <Database className="size-3.5" /> Actualizar datos + señales
              </Button>
              <Button
                disabled={!!running}
                onClick={() => trigger.mutate('build-dataset')}
                className="flex items-center justify-center gap-2"
              >
                <Activity className="size-3.5" /> Reconstruir dataset
              </Button>
              <Button
                disabled={!!running}
                onClick={() => {
                  if (confirm('¿Reentrenar el modelo? Tomará varios minutos.'))
                    trigger.mutate('train')
                }}
                className="flex items-center justify-center gap-2"
              >
                <Brain className="size-3.5" /> Reentrenar modelo
              </Button>
              {running && (
                <p className="text-center font-mono text-[10px] uppercase tracking-wider text-warn">
                  ejecutando: {running}…
                </p>
              )}
            </div>
          </Panel>
        </div>
      </div>

      {/* fila inferior: importancias + runs */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Importancia de features (media |SHAP|)">
          {importances.length === 0 ? (
            <Empty>Disponible tras el primer entrenamiento.</Empty>
          ) : (
            <div className="space-y-1.5 p-4">
              {importances.map(([f, v]) => (
                <div key={f} className="flex items-center gap-2 text-xs">
                  <span className="w-44 shrink-0 truncate text-muted">{featureLabel(f)}</span>
                  <div className="h-2.5 flex-1 bg-panel-2">
                    <div className="h-full bg-info/60" style={{ width: `${(v / maxImp) * 100}%` }} />
                  </div>
                  <span className="tnum w-12 shrink-0 text-right text-faint">{v.toFixed(3)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Ejecuciones del pipeline">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-hairline font-mono text-[10px] uppercase tracking-[0.15em] text-faint">
                <th className="px-4 py-2 text-left">Tipo</th>
                <th className="px-2 py-2 text-left">Estado</th>
                <th className="px-2 py-2 text-right">Inicio</th>
                <th className="px-4 py-2 text-right">Fin</th>
              </tr>
            </thead>
            <tbody>
              {data.runs.map((r) => (
                <tr key={r.id} className="border-b border-hairline/50" title={r.detail}>
                  <td className="px-4 py-1.5 font-mono">{r.kind}</td>
                  <td className="px-2 py-1.5">
                    <Tag tone={r.status === 'success' ? 'pos' : r.status === 'error' ? 'neg' : 'warn'}>
                      {r.status}
                    </Tag>
                  </td>
                  <td className="tnum px-2 py-1.5 text-right text-muted">{fmtDateTime(r.started_at)}</td>
                  <td className="tnum px-4 py-1.5 text-right text-muted">{fmtDateTime(r.finished_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  )
}

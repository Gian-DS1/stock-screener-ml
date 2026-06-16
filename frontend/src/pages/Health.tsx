import clsx from 'clsx'
import { Activity, Brain, Database } from 'lucide-react'
import { useHealth, usePipelineStatus, usePipelineTrigger } from '../lib/api'
import { featureLabel, fmtDateTime, fmtPct } from '../lib/format'
import { Button, Empty, Panel, Spinner, Stat, Tag } from '../components/ui'

function DriftLight({ label, report, soft = false }: {
  label: string
  report?: { created_at: string; drifted: boolean; metric: number }
  // soft: deriva informativa (ámbar), no degradación accionable. Se usa para la
  // deriva de DATOS, que es esperable por el horizonte de 6 meses del label.
  soft?: boolean
}) {
  const driftBg = soft ? 'bg-warn' : 'bg-neg'
  const driftText = soft ? 'text-warn' : 'text-neg'
  const color = !report ? 'bg-faint' : report.drifted ? driftBg : 'bg-pos'
  const text = !report
    ? 'sin datos'
    : report.drifted
      ? (soft ? 'DERIVA LEVE (INFORMATIVA)' : 'DERIVA DETECTADA')
      : 'estable'
  return (
    <div className="flex items-center gap-3 border border-edge bg-panel-2/60 px-4 py-3">
      <span className={clsx('size-3 rounded-full', color, report?.drifted && 'pulse-dot')} />
      <div className="min-w-0">
        <div className="font-mono text-xs font-medium uppercase tracking-wider">{label}</div>
        <div className={clsx('text-xs', report?.drifted ? driftText : 'text-muted')}>
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

  // recomendación explícita: qué botón pulsar según el estado actual.
  // La degradación ACCIONABLE es la deriva de PREDICCIONES (el output del
  // modelo se aleja de lo aprendido). La deriva de DATOS es esperable por el
  // horizonte de 6 meses del label y no se arregla reentrenando hasta que
  // maduren datos nuevos: se muestra como aviso, no como rojo.
  const predDrift = !!data.drift.prediction?.drifted
  const dataDrift = !!data.drift.data?.drifted
  const reco = !m
    ? { tone: 'warn' as const, btn: 'Reentrenar modelo',
        text: 'Aún no hay modelo entrenado. Pulsa “Reentrenar modelo” para crearlo por primera vez.' }
    : predDrift
      ? { tone: 'neg' as const, btn: 'Reentrenar modelo',
          text: 'Las PREDICCIONES del modelo se alejaron de lo que aprendió: degradación real del output. Pulsa “Reentrenar modelo” para recuperar la calibración antes de confiar en nuevas señales.' }
      : dataDrift
        ? { tone: 'warn' as const, btn: 'Actualizar datos + señales',
            text: 'Los inputs de mercado se movieron respecto al entrenamiento reciente. Es esperable: el modelo se entrena con datos cuyo retorno a 120 días ya maduró (~6 meses atrás), así que reentrenar hoy no cambia nada hasta que maduren datos nuevos. Las predicciones siguen estables: sigue tu rutina diaria con normalidad.' }
        : { tone: 'pos' as const, btn: 'Actualizar datos + señales',
            text: 'El modelo está sano. Para tu rutina diaria solo necesitas “Actualizar datos + señales”. No hace falta reentrenar.' }
  const recoTone = { neg: 'border-neg/40 bg-neg/[0.07] text-neg', warn: 'border-warn/40 bg-warn/[0.07] text-warn', pos: 'border-pos/40 bg-pos/[0.07] text-pos' }[reco.tone]

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
              <DriftLight label="Datos (34 features)" report={data.drift.data} soft />
              <DriftLight label="Predicciones (KS)" report={data.drift.prediction} />
              {/* recomendación explícita de qué hacer */}
              <div className={clsx('border p-3', recoTone)}>
                <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.15em]">
                  ¿Qué debo hacer?
                </p>
                <p className="text-xs leading-snug text-fg/90">{reco.text}</p>
              </div>
            </div>
          </Panel>

          <Panel title="Acciones">
            <div className="flex flex-col gap-3 p-4">
              <div>
                <Button
                  tone="primary"
                  disabled={!!running}
                  onClick={() => trigger.mutate('run-daily')}
                  className={clsx('flex w-full items-center justify-center gap-2', reco.btn === 'Actualizar datos + señales' && 'ring-2 ring-pos/50')}
                >
                  <Database className="size-3.5" /> Actualizar datos + señales
                </Button>
                <p className="mt-1 text-[11px] leading-snug text-faint">
                  <strong className="text-muted">Tu rutina diaria.</strong> Descarga lo nuevo del mercado y
                  recalcula las señales. Rápido. Úsalo una vez al día.
                </p>
              </div>
              <div>
                <Button
                  disabled={!!running}
                  onClick={() => trigger.mutate('build-dataset')}
                  className="flex w-full items-center justify-center gap-2"
                >
                  <Activity className="size-3.5" /> Reconstruir dataset
                </Button>
                <p className="mt-1 text-[11px] leading-snug text-faint">
                  Solo si cambió algo de fondo (nuevas variables, mucho histórico nuevo). Después
                  conviene reentrenar. Casi nunca lo necesitas.
                </p>
              </div>
              <div>
                <Button
                  disabled={!!running}
                  onClick={() => {
                    if (confirm('¿Reentrenar el modelo? Tomará varios minutos.'))
                      trigger.mutate('train')
                  }}
                  className={clsx('flex w-full items-center justify-center gap-2', reco.btn === 'Reentrenar modelo' && 'ring-2 ring-neg/50')}
                >
                  <Brain className="size-3.5" /> Reentrenar modelo
                </Button>
                <p className="mt-1 text-[11px] leading-snug text-faint">
                  <strong className="text-muted">Cuando hay deriva</strong> (semáforo rojo arriba) o cada
                  pocos meses. Vuelve a aprender con datos recientes. Tarda varios minutos.
                </p>
              </div>
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

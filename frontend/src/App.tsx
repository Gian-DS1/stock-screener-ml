import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import clsx from 'clsx'
import { Bell, Crosshair, RefreshCw } from 'lucide-react'
import { useAlerts, usePipelineStatus, usePipelineTrigger } from './lib/api'
import Opportunities from './pages/Opportunities'
import Portfolio from './pages/Portfolio'
import Health from './pages/Health'

const TABS = [
  { to: '/oportunidades', label: 'Oportunidades' },
  { to: '/portafolio', label: 'Portafolio' },
  { to: '/salud', label: 'Salud del modelo' },
]

export default function App() {
  const { data: status } = usePipelineStatus()
  const { data: alerts } = useAlerts(true)
  const trigger = usePipelineTrigger()
  const running = status?.running ?? null
  const unread = alerts?.length ?? 0

  return (
    <div className="mx-auto flex min-h-screen max-w-[1480px] flex-col px-4 pb-10">
      <header className="sticky top-0 z-30 -mx-4 mb-5 border-b border-edge bg-ink/90 px-4 backdrop-blur">
        <div className="flex h-14 items-center gap-6">
          <div className="flex items-center gap-2.5">
            <Crosshair className="size-5 text-pos" strokeWidth={1.75} />
            <h1 className="font-mono text-sm font-semibold uppercase tracking-[0.25em]">
              Sniper<span className="text-pos">Screener</span>
            </h1>
          </div>

          <nav className="flex h-full items-stretch gap-1">
            {TABS.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center border-b-2 px-3 font-mono text-xs uppercase tracking-wider transition-colors',
                    isActive
                      ? 'border-pos text-fg'
                      : 'border-transparent text-muted hover:text-fg',
                  )
                }
              >
                {t.label}
                {t.to === '/portafolio' && unread > 0 && (
                  <span className="ml-2 flex items-center gap-1 text-warn">
                    <Bell className="size-3" />
                    <span className="tnum">{unread}</span>
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {running ? (
              <span className="flex items-center gap-2 font-mono text-xs text-warn">
                <span className="pulse-dot size-2 rounded-full bg-warn" />
                ejecutando: {running}
              </span>
            ) : (
              <span className="flex items-center gap-2 font-mono text-xs text-muted">
                <span className="size-2 rounded-full bg-pos" />
                en reposo
              </span>
            )}
            <button
              onClick={() => trigger.mutate('run-daily')}
              disabled={!!running}
              title="Actualizar datos y señales ahora"
              className="flex items-center gap-2 border border-edge bg-panel px-3 py-1.5 font-mono text-xs uppercase tracking-wider text-fg transition-colors hover:border-pos/50 disabled:opacity-40"
            >
              <RefreshCw className={clsx('size-3.5', running && 'animate-spin')} />
              Actualizar
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Navigate to="/oportunidades" replace />} />
          <Route path="/oportunidades" element={<Opportunities />} />
          <Route path="/portafolio" element={<Portfolio />} />
          <Route path="/salud" element={<Health />} />
        </Routes>
      </main>

      <footer className="mt-8 border-t border-hairline pt-3 font-mono text-[10px] uppercase tracking-widest text-faint">
        uso personal · las señales no son consejo financiero · el sistema nunca opera solo
      </footer>
    </div>
  )
}

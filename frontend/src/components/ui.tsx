import clsx from 'clsx'
import type { ReactNode } from 'react'

export function Panel({
  title,
  right,
  children,
  className,
  dataTour,
}: {
  title?: string
  right?: ReactNode
  children: ReactNode
  className?: string
  dataTour?: string
}) {
  return (
    <section data-tour={dataTour} className={clsx('border border-edge bg-panel/80 backdrop-blur-sm', className)}>
      {title && (
        <header className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            {title}
          </h2>
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

export function Tag({
  tone = 'muted',
  children,
}: {
  tone?: 'pos' | 'neg' | 'warn' | 'info' | 'muted'
  children: ReactNode
}) {
  const tones = {
    pos: 'text-pos border-pos/30 bg-pos/10',
    neg: 'text-neg border-neg/30 bg-neg/10',
    warn: 'text-warn border-warn/30 bg-warn/10',
    info: 'text-info border-info/30 bg-info/10',
    muted: 'text-muted border-edge bg-panel-2',
  }
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 border px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider',
        tones[tone],
      )}
    >
      {children}
    </span>
  )
}

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-faint">{label}</span>
      <span className={clsx('tnum text-sm', tone)}>{value}</span>
    </div>
  )
}

/** Barra horizontal de probabilidad con marca del umbral. */
export function ProbBar({ value, threshold }: { value: number; threshold?: number }) {
  return (
    <div className="relative h-1.5 w-20 bg-panel-2">
      <div
        className="absolute inset-y-0 left-0 bg-pos/80"
        style={{ width: `${Math.min(value * 100, 100)}%` }}
      />
      {threshold != null && (
        <div
          className="absolute -inset-y-0.5 w-px bg-warn"
          style={{ left: `${threshold * 100}%` }}
          title={`umbral ${(threshold * 100).toFixed(0)}%`}
        />
      )}
    </div>
  )
}

/** Calidad como cargador segmentado (10 segmentos). */
export function QualityGauge({ score }: { score: number }) {
  const filled = Math.round(score / 10)
  const tone = score >= 75 ? 'bg-pos' : score >= 60 ? 'bg-info' : score >= 40 ? 'bg-warn' : 'bg-neg'
  return (
    <div className="flex items-center gap-1.5" title={`calidad ${score.toFixed(0)}/100`}>
      <div className="flex gap-[2px]">
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className={clsx('h-3 w-[3px]', i < filled ? tone : 'bg-edge')}
          />
        ))}
      </div>
      <span className="tnum text-xs text-muted">{score.toFixed(0)}</span>
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 p-10 text-muted">
      <span className="size-3 animate-spin border border-muted border-t-pos" />
      <span className="font-mono text-xs uppercase tracking-widest">{label ?? 'cargando'}</span>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 p-12 text-center">
      <svg viewBox="0 0 32 32" className="size-8 stroke-faint" fill="none" strokeWidth="1.5">
        <circle cx="16" cy="16" r="10" />
        <line x1="16" y1="1" x2="16" y2="9" />
        <line x1="16" y1="23" x2="16" y2="31" />
        <line x1="1" y1="16" x2="9" y2="16" />
        <line x1="23" y1="16" x2="31" y2="16" />
      </svg>
      <p className="max-w-sm text-sm text-muted">{children}</p>
    </div>
  )
}

export function Button({
  onClick,
  disabled,
  tone = 'default',
  children,
  className,
}: {
  onClick?: () => void
  disabled?: boolean
  tone?: 'default' | 'primary' | 'danger' | 'ghost'
  children: ReactNode
  className?: string
}) {
  const tones = {
    default: 'border-edge bg-panel-2 text-fg hover:border-muted',
    primary: 'border-pos/40 bg-pos/10 text-pos hover:bg-pos/20',
    danger: 'border-neg/40 bg-neg/10 text-neg hover:bg-neg/20',
    ghost: 'border-transparent text-muted hover:text-fg',
  }
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'border px-3 py-1.5 font-mono text-xs font-medium uppercase tracking-wider transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-40',
        tones[tone],
        className,
      )}
    >
      {children}
    </button>
  )
}

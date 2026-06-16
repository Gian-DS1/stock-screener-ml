import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Info } from 'lucide-react'
import { BETTER_LABEL, metricInfo } from '../lib/glossary'

const BETTER_TONE: Record<string, string> = {
  higher: 'text-pos',
  lower: 'text-pos',
  context: 'text-muted',
}

const W = 260
const EST_H = 96

/** Icono "i" que muestra la explicación llana de una métrica al pasar el cursor
 *  o tocar. El tooltip se renderiza en un portal al <body> para no verse
 *  afectado por contenedores con `transform` (que rompen `position: fixed`). */
export default function InfoTip({ metric }: { metric: string }) {
  const info = metricInfo(metric)
  const ref = useRef<HTMLButtonElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  if (!info) return null

  const show = () => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    const left = Math.min(Math.max(r.left + r.width / 2 - W / 2, 8), window.innerWidth - W - 8)
    // por defecto debajo del icono; si no cabe, lo coloca encima
    const top = r.bottom + 6 + EST_H > window.innerHeight ? r.top - EST_H - 6 : r.bottom + 6
    setPos({ top: Math.max(8, top), left })
  }
  const hide = () => setPos(null)

  return (
    <>
      <button
        ref={ref}
        type="button"
        onMouseEnter={show}
        onMouseLeave={hide}
        onClick={(e) => {
          e.stopPropagation()
          if (pos) hide()
          else show()
        }}
        aria-label={`Qué significa: ${metric}`}
        className="inline-flex shrink-0 text-faint transition-colors hover:text-info"
      >
        <Info className="size-3.5" />
      </button>
      {pos &&
        createPortal(
          <div
            className="fixed z-[120] w-[260px] border border-edge bg-panel-2 p-3 shadow-xl"
            style={{ top: pos.top, left: pos.left }}
            role="tooltip"
          >
            <p className="text-xs leading-relaxed text-fg/90">{info.tip}</p>
            <p className={`mt-1.5 font-mono text-[10px] uppercase tracking-wider ${BETTER_TONE[info.better]}`}>
              {BETTER_LABEL[info.better]}
            </p>
          </div>,
          document.body,
        )}
    </>
  )
}

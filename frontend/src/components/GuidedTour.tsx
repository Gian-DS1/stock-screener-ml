import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CandlestickChart, Check, X } from 'lucide-react'

type Placement = 'top' | 'bottom' | 'left' | 'right' | 'center'

interface Step {
  target?: string          // valor de data-tour; ausente = tarjeta centrada
  title: string
  body: string
  route?: string           // navegar a esta ruta antes del paso
  action?: 'open-detail'   // interacción previa (abrir el panel de detalle)
  placement?: Placement
}

const STEPS: Step[] = [
  {
    title: 'Bienvenido a Stock Screener',
    body: 'Este sistema busca pocas oportunidades de altísima calidad: empresas en descuento con potencial de crecimiento. Te muestro en 30 segundos cómo se usa.',
    route: '/oportunidades',
    placement: 'center',
  },
  {
    target: 'actualizar',
    title: 'Actualizar datos y señales',
    body: 'Una vez al día, pulsa aquí. Descarga lo nuevo del mercado, recalcula las señales y revisa tus posiciones. Verás una barra de progreso mientras corre.',
    placement: 'bottom',
  },
  {
    target: 'opp-table',
    title: 'Las oportunidades del día',
    body: 'Cada fila es una señal, ordenadas por score (probabilidad × calidad). Cuanto más arriba, mejor candidata. Veamos una en detalle.',
    route: '/oportunidades',
    placement: 'top',
  },
  {
    target: 'detalle-shap',
    title: 'Por qué dispara el modelo',
    body: 'Al abrir una señal ves esto: las variables que más empujan la decisión (SHAP). Verde la apoya, rojo va en contra. El modelo es transparente, no una caja negra.',
    route: '/oportunidades',
    action: 'open-detail',
    placement: 'left',
  },
  {
    target: 'detalle-calidad',
    title: 'Calidad y descuento',
    body: 'El score de calidad (0–100) combina solidez del negocio y lo barata que está la acción frente a su propia historia. Una señal solo cuenta si supera 60.',
    route: '/oportunidades',
    placement: 'left',
  },
  {
    target: 'detalle-registrar',
    title: 'Registrar tu compra',
    body: 'Si compras en tu broker, regístralo aquí. El sistema nunca opera por ti: solo vigila y avisa. Tú ejecutas las órdenes.',
    route: '/oportunidades',
    placement: 'left',
  },
  {
    target: 'portfolio-posiciones',
    title: 'Tus posiciones y reglas de salida',
    body: 'Cada posición muestra en vivo sus 4 reglas: stop loss −12%, trailing −8% tras subir 5%, límite de 120 días y take-profit parcial al +15%. Cuando una se dispara, te avisa.',
    route: '/portafolio',
    placement: 'right',
  },
  {
    target: 'portfolio-alertas',
    title: 'Centro de alertas',
    body: 'Aquí aparece todo lo accionable: cuándo vender según tus reglas, señales nuevas y cambios en los índices. Clic para marcarlas leídas.',
    route: '/portafolio',
    placement: 'left',
  },
  {
    target: 'salud-modelo',
    title: 'Salud del modelo',
    body: 'Su precisión real en datos no vistos, cuándo se entrenó y su rendimiento por periodo. Aquí compruebas que el modelo sigue siendo fiable.',
    route: '/salud',
    placement: 'bottom',
  },
  {
    target: 'salud-drift',
    title: 'Deriva (drift)',
    body: 'Si el mercado cambia de régimen, este semáforo se pone en rojo y conviene reentrenar. Es tu aviso de que las premisas del modelo caducaron.',
    route: '/salud',
    placement: 'left',
  },
  {
    title: '¡Listo!',
    body: 'Ese es el flujo: Actualizar → revisar oportunidades → registrar lo que compras → atender alertas. Puedes repetir este tour cuando quieras desde el botón de ayuda. Recuerda: no es consejo financiero.',
    placement: 'center',
  },
]

const PAD = 8
const TOOLTIP_W = 340

export default function GuidedTour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [index, setIndex] = useState(0)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const navigate = useNavigate()
  const step = STEPS[index]
  const last = index === STEPS.length - 1
  const targetRef = useRef<string | undefined>(undefined)

  const close = useCallback(() => {
    localStorage.setItem('tour_seen_v1', '1')
    setIndex(0)
    setRect(null)
    onClose()
  }, [onClose])

  // Efecto de PASO: fija SÍNCRONAMENTE el objetivo (inmune a cancelaciones) y
  // dispara la navegación / apertura del detalle. La medición vive en su bucle.
  useEffect(() => {
    if (!open) return
    const s = STEPS[index]
    targetRef.current = s.target
    // Limpieza intencional del spotlight al cambiar de paso; el bucle de
    // medición lo vuelve a calcular una vez el nuevo objetivo está en el DOM.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRect(null)
    if (s.route && window.location.pathname !== s.route) navigate(s.route)
    if (s.action === 'open-detail') {
      const t = setTimeout(() => {
        ;(document.querySelector('[data-tour="opp-table"] tbody tr') as HTMLElement | null)?.click()
      }, 120)
      return () => clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, index])

  // Bucle de MEDICIÓN (atado solo a [open]): lee el objetivo vigente del ref,
  // espera a que aparezca tras navegar/abrir el detalle, hace scroll hacia él al
  // cambiar de objetivo y reposiciona el spotlight (solo re-render si cambió).
  useEffect(() => {
    if (!open) return
    const same = (a: DOMRect | null, r: DOMRect) =>
      !!a && a.top === r.top && a.left === r.left && a.width === r.width && a.height === r.height
    let lastTarget: string | undefined = 'init'
    const id = setInterval(() => {
      const sel = targetRef.current
      if (!sel) {
        setRect((prev) => (prev === null ? prev : null))
        lastTarget = undefined
        return
      }
      const el = document.querySelector(`[data-tour="${sel}"]`) as HTMLElement | null
      if (!el) return
      if (sel !== lastTarget) {
        el.scrollIntoView({ block: 'center', behavior: 'smooth' })
        lastTarget = sel
      }
      const r = el.getBoundingClientRect()
      setRect((prev) => (same(prev, r) ? prev : r))
    }, 150)
    return () => clearInterval(id)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
      else if (e.key === 'ArrowRight') setIndex((i) => Math.min(i + 1, STEPS.length - 1))
      else if (e.key === 'ArrowLeft') setIndex((i) => Math.max(i - 1, 0))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, close])

  if (!open) return null

  const placement: Placement = rect ? step.placement ?? 'bottom' : 'center'
  const tip = tooltipPosition(rect, placement)

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100 }}>
      {/* capa que bloquea la interacción real con la app durante el tour */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'auto' }} />

      {/* spotlight: oscurece todo menos el elemento (box-shadow gigante).
          Cuando no hay objetivo (pasos centrados) cubre toda la pantalla. */}
      <motion.div
        initial={false}
        animate={
          rect
            ? {
                top: rect.top - PAD,
                left: rect.left - PAD,
                width: rect.width + PAD * 2,
                height: rect.height + PAD * 2,
                borderRadius: 10,
                borderColor: 'rgba(61,220,151,1)',
              }
            : {
                top: -20,
                left: -20,
                width: window.innerWidth + 40,
                height: window.innerHeight + 40,
                borderRadius: 0,
                borderColor: 'rgba(61,220,151,0)',
              }
        }
        transition={{ type: 'spring', stiffness: 260, damping: 30 }}
        style={{
          position: 'absolute',
          boxShadow: '0 0 0 9999px rgba(7,10,14,0.82)',
          border: '2px solid rgba(61,220,151,0)',
          pointerEvents: 'none',
        }}
      />

      {/* tarjeta del paso: una sola, su posición se anima entre pasos */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, top: tip.top, left: tip.left }}
        transition={{ type: 'spring', stiffness: 320, damping: 30 }}
        style={{
          position: 'absolute',
          width: TOOLTIP_W,
          maxWidth: 'calc(100vw - 24px)',
          background: '#11161d',
          border: '1px solid #1c242e',
          borderRadius: 12,
          padding: '18px 20px',
          boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
          pointerEvents: 'auto',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <CandlestickChart size={16} color="#3ddc97" />
          <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: 10, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#66788a' }}>
            paso {index + 1} de {STEPS.length}
          </span>
          <button onClick={close} aria-label="cerrar" style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#66788a', cursor: 'pointer', padding: 0, display: 'flex' }}>
            <X size={16} />
          </button>
        </div>

        {/* el texto se anima al entrar en cada paso (sin esperar salidas) */}
        <div style={{ minHeight: 88 }}>
          <motion.div key={index} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.22 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: 16, fontWeight: 500, color: '#c8d2dc' }}>{step.title}</h3>
            <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: '#8b97a3' }}>{step.body}</p>
          </motion.div>
        </div>

        {/* puntos de progreso */}
        <div style={{ display: 'flex', gap: 5, margin: '16px 0 14px' }}>
          {STEPS.map((_, i) => (
            <span key={i} style={{ height: 3, flex: 1, borderRadius: 2, background: i <= index ? '#3ddc97' : '#1c242e', transition: 'background 0.3s' }} />
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={() => setIndex((i) => Math.max(i - 1, 0))} disabled={index === 0} style={btn(index === 0)}>
            <ArrowLeft size={14} /> Atrás
          </button>
          <button onClick={close} style={{ ...btn(false), marginLeft: 'auto', borderColor: 'transparent', color: '#66788a' }}>
            Saltar
          </button>
          {last ? (
            <button onClick={close} style={btnPrimary()}>
              <Check size={14} /> Entendido
            </button>
          ) : (
            <button onClick={() => setIndex((i) => i + 1)} style={btnPrimary()}>
              Siguiente <ArrowRight size={14} />
            </button>
          )}
        </div>
      </motion.div>
    </div>
  )
}

function tooltipPosition(rect: DOMRect | null, placement: Placement): { top: number; left: number } {
  const W = typeof window !== 'undefined' ? window.innerWidth : 1280
  const H = typeof window !== 'undefined' ? window.innerHeight : 800
  if (!rect || placement === 'center') {
    return { top: H / 2 - 120, left: W / 2 - TOOLTIP_W / 2 }
  }
  const clampL = (l: number) => Math.min(Math.max(l, 12), W - TOOLTIP_W - 12)
  const clampT = (t: number) => Math.min(Math.max(t, 12), H - 240)
  const gap = 16
  switch (placement) {
    case 'top':
      return { top: clampT(rect.top - 230), left: clampL(rect.left) }
    case 'left':
      return { top: clampT(rect.top), left: clampL(rect.left - TOOLTIP_W - gap) }
    case 'right':
      return { top: clampT(rect.top), left: clampL(rect.right + gap) }
    default: // bottom
      return { top: clampT(rect.bottom + gap), left: clampL(rect.left) }
  }
}

const baseBtn: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '7px 12px',
  fontFamily: 'IBM Plex Mono, monospace',
  fontSize: 12,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  borderRadius: 6,
  cursor: 'pointer',
  border: '1px solid #1c242e',
  background: 'transparent',
  color: '#c8d2dc',
}

function btn(disabled: boolean): React.CSSProperties {
  return { ...baseBtn, opacity: disabled ? 0.35 : 1, cursor: disabled ? 'default' : 'pointer' }
}
function btnPrimary(): React.CSSProperties {
  return { ...baseBtn, border: '1px solid rgba(61,220,151,0.4)', background: 'rgba(61,220,151,0.12)', color: '#3ddc97' }
}

import { describe, expect, it } from 'vitest'
import { fmtDate, fmtSignedPct, fmtUsd, todayIso } from './format'

describe('fmtDate', () => {
  it('no adelanta ni atrasa el día en husos al oeste de UTC', () => {
    // El bug original: new Date('2026-08-24') es medianoche UTC, y al
    // renderizarla en América mostraba el 23. Los tests corren con
    // TZ=America/Santo_Domingo (UTC-4) definido en vite.config.ts.
    expect(fmtDate('2026-08-24')).toContain('24')
  })

  it('respeta el día en el cambio de mes', () => {
    expect(fmtDate('2026-01-01')).toContain('01')
    expect(fmtDate('2026-12-31')).toContain('31')
  })

  it('devuelve un guion largo cuando no hay fecha', () => {
    expect(fmtDate(null)).toBe('—')
    expect(fmtDate(undefined)).toBe('—')
    expect(fmtDate('')).toBe('—')
  })
})

describe('todayIso', () => {
  it('usa el reloj local, no el UTC', () => {
    // 24 de agosto, 21:00 local en UTC-4 => ya es día 25 en UTC
    const nocheLocal = new Date(2026, 7, 24, 21, 0, 0)

    expect(todayIso(nocheLocal)).toBe('2026-08-24')
  })

  it('rellena mes y día con ceros', () => {
    expect(todayIso(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})

describe('formato de cifras', () => {
  it('marca explícitamente el signo del porcentaje', () => {
    expect(fmtSignedPct(0.153)).toBe('+15.3%')
    expect(fmtSignedPct(-0.12)).toBe('-12.0%')
    expect(fmtSignedPct(0)).toBe('+0.0%')
  })

  it('formatea dólares y tolera nulos', () => {
    expect(fmtUsd(1234.5)).toBe('$1,234.50')
    expect(fmtUsd(null)).toBe('—')
  })
})

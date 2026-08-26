# Frontend — dashboard del Stock Screener

SPA en React 19 + TypeScript que consume la API de FastAPI. En producción no se
sirve por separado: `npm run build` genera `dist/`, y el backend lo monta como
estático en `http://localhost:8000`.

## Scripts

| Comando | Qué hace |
|---|---|
| `npm run dev` | servidor de desarrollo en `:5173` con proxy de `/api` a `:8000` |
| `npm run build` | chequeo de tipos (`tsc -b`) + bundle de producción en `dist/` |
| `npm run lint` | ESLint (incluye `react-hooks` y `react-refresh`) |
| `npm run preview` | sirve el `dist/` ya compilado |

Para desarrollar necesitas el backend corriendo aparte:

```bash
cd backend && uv run uvicorn screener.api.main:app --port 8000
```

## Estructura

```
src/
├── App.tsx              # layout, navegación por pestañas y estado del pipeline
├── pages/
│   ├── Opportunities.tsx  # señales del día + watchlist
│   ├── Portfolio.tsx      # posiciones abiertas, alertas y reglas de salida
│   └── Health.tsx         # métricas del modelo, drift y cobertura de datos
├── components/
│   ├── SignalDetail.tsx    # panel de detalle: gráfico, SHAP y desglose de calidad
│   ├── PipelineProgress.tsx# barra de progreso en vivo del run diario
│   ├── AddPositionModal.tsx
│   ├── GuidedTour.tsx      # tour de onboarding (primera visita)
│   ├── FavoriteStar.tsx · InfoTip.tsx · ui.tsx
└── lib/
    ├── api.ts           # hooks de TanStack Query, un hook por endpoint
    ├── format.ts        # formateo de números, porcentajes y fechas
    └── glossary.ts      # definiciones de cada métrica (tooltips explicativos)
```

## Convenciones

- **Datos del servidor**: siempre vía TanStack Query (`src/lib/api.ts`). Ningún
  componente hace `fetch` por su cuenta.
- **Estilos**: Tailwind v4 con tokens semánticos definidos en `src/index.css`
  (`pos`, `neg`, `warn`, `info`, `muted`, `edge`…), no colores literales.
- **Sin jerga sin explicar**: toda métrica que se muestra tiene su entrada en
  `glossary.ts` y se expone con `<InfoTip>`.

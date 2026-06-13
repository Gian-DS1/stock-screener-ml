# Stock Screener

Stock screener personal impulsado por ML. Filosofía selectiva: **pocas
oportunidades de altísima calidad** — empresas en descuento con potencial de
crecimiento a mediano/largo plazo — en lugar de muchas señales de baja calidad.

## Arquitectura

- **Datos (gratuitos, Point-In-Time estricto)**: precios yfinance · fundamentales
  SEC EDGAR XBRL (por fecha real de filing) · macro FRED/ALFRED (vintages) ·
  sentimiento FinBERT sobre 8-K (lag +1 día hábil) · VIX.
- **Dos horizontes**: modelo táctico `HistGradientBoosting` (¿alcanzará +15% en
  120 días hábiles?) con CV temporal expanding-window y umbral que maximiza
  precisión sujeta a recall ≥ 0.25 + **quality score** 0-100 por reglas
  transparentes (calidad del negocio, descuento de valoración, solidez) como gate.
- **Señal** = prob ≥ umbral · calidad ≥ 60 · precio < SMA200×1.05 · liquidez ·
  cooldown 22 días. Cada señal trae su explicación SHAP.
- **Portafolio real**: registras tus compras; el sistema vigila a diario las
  reglas de salida (stop -12%, trailing -8% tras +5%, límite 120 días, TP parcial
  33% en +15%) y te alerta. **Nunca opera solo.**
- **Salud**: drift de datos y predicciones (evidently/KS) con recomendación de
  reentrenar. Backtest CLI honesto (probabilidades out-of-fold).

## Setup inicial

```powershell
# 1. Backend (requiere uv: https://docs.astral.sh/uv/)
cd backend
uv sync --group dev --extra sentiment --extra drift

# 2. API keys (gratuitas)
copy .env.example .env
# edita backend/.env:
#   FRED_API_KEY     -> https://fred.stlouisfed.org/docs/api/api_key.html
#   FINNHUB_API_KEY  -> https://finnhub.io/register (opcional, titulares en vivo)
#   SEC_USER_AGENT   -> tu email (la SEC lo exige)

# 3. Backfill histórico completo (una sola vez; varias horas por los 8-K)
uv run python -m screener.cli backfill

# 4. Dataset + entrenamiento
uv run python -m screener.cli build-dataset
uv run python -m screener.cli train

# 5. Frontend
cd ..\frontend
npm install
npm run build        # FastAPI sirve frontend/dist en producción

# 6. Accesos directos de un clic en el escritorio
powershell -ExecutionPolicy Bypass -File scripts\instalar_accesos.ps1

# 7. (opcional) Tarea diaria automática (tras el cierre del mercado)
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

## Uso diario

**La forma fácil:** doble clic en el acceso directo **"Stock Screener"** del
escritorio. Arranca el sistema sin terminal (solo en `127.0.0.1`, sin puertos
expuestos) y abre el dashboard. Para cerrarlo, **"Detener Stock Screener"**.

Guía detallada de uso: [TUTORIAL.md](TUTORIAL.md).

Alternativa por terminal:
```powershell
cd backend
uv run uvicorn screener.api.main:app --host 127.0.0.1 --port 8000
# -> http://localhost:8000  (dashboard)  ·  /api/docs (API)
```

La tarea programada (o el botón **Actualizar** del dashboard) ejecuta `run-daily`
(ingesta incremental → señales → evaluación del portafolio → drift). Todo el
estado persiste en `data/` y `models/`, así que continúas donde lo dejaste.

## Comandos CLI

| Comando | Qué hace |
|---|---|
| `backfill [--tickers A,B] [--skip-sentiment]` | descarga histórico al data lake |
| `build-dataset` | matriz PIT de entrenamiento (34 features + labels) |
| `train` | entrena, optimiza umbral, versiona el modelo |
| `score` | genera señales del día |
| `run-daily` | pipeline diario completo |
| `drift` | chequeo de deriva |
| `backtest --start 2018-01-01` | validación histórica (OOF, sin look-ahead) |

Desarrollo frontend: `npm run dev` (proxy a :8000). Tests: `uv run pytest`.

## Limitaciones conocidas (datos gratuitos)

- **Sesgo de supervivencia**: se entrena con los constituyentes actuales del
  S&P 500 + NASDAQ 100; las métricas históricas son optimistas.
- Titulares de noticias solo en inferencia (sin histórico profundo gratuito).
- Sin FRED_API_KEY el modelo entrena sin las 6 features macro (funciona, pero
  pierde el contexto de ciclo).

> Uso personal. Las señales no son consejo financiero.

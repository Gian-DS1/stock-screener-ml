# Tutorial de uso — Sniper Screener

Guía completa para operar el sistema y entender qué hace por dentro. Está
pensada para uso personal y local: nada se expone a internet.

> **Tour interactivo:** la primera vez que abres el dashboard se inicia un tour
> guiado que resalta cada parte de la interfaz paso a paso. Puedes repetirlo
> cuando quieras con el botón de ayuda (**?**) arriba a la derecha. Este
> documento es la referencia escrita y más detallada de ese mismo recorrido.

---

## 1. Arrancar y detener (sin terminal)

En tu **escritorio** tienes dos accesos directos:

| Acceso directo | Qué hace |
|---|---|
| **Sniper Screener** | Arranca el sistema (sin ventana de terminal) y abre el dashboard en tu navegador. |
| **Detener Sniper Screener** | Cierra el backend. Tus datos quedan guardados. |

- **Doble clic en "Sniper Screener"** → espera ~10 segundos → se abre el navegador en `http://localhost:8000`.
- Para cerrarlo, doble clic en **"Detener Sniper Screener"**. Cerrar solo la pestaña del navegador NO detiene el backend (sigue corriendo en segundo plano, lo cual es útil si quieres volver a abrir la pestaña).

> **Seguridad:** el sistema escucha únicamente en `127.0.0.1` (tu propia máquina).
> Ningún otro dispositivo de tu red ni de internet puede verlo o acceder. No se
> abre ningún puerto en tu router.

Si los accesos directos se borran, vuelve a crearlos con:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\instalar_accesos.ps1
```

---

## 2. Tus datos persisten entre sesiones

No tienes que rehacer nada al reabrir. Todo se guarda en disco:

| Qué | Dónde | Contiene |
|---|---|---|
| Estado de la app | `data/app.db` (SQLite) | Señales emitidas, tus posiciones, alertas, historial de ejecuciones, registro de modelos. |
| Data lake | `data/raw/`, `data/features/` (Parquet) | Precios, fundamentales, 8-K, macro, dataset de entrenamiento. |
| Modelos | `models/` | Modelos entrenados y su umbral óptimo. |

Cierra el sistema cuando quieras: al volver a arrancar, tus señales del día,
posiciones abiertas y alertas siguen ahí. **Continúas donde lo dejaste.**

> Haz una copia de seguridad ocasional de la carpeta `data/` si no quieres
> perder tu historial de posiciones ante un fallo de disco.

---

## 3. Flujo de trabajo diario recomendado

1. **Abre el sistema** (acceso directo) por la mañana o tras el cierre del mercado.
2. Pulsa **"Actualizar"** (arriba a la derecha) una vez al día. Descarga los
   datos nuevos, recalcula señales y revisa tus posiciones. Tarda unos minutos;
   verás la **barra de progreso** mientras corre.
3. Revisa la página **Oportunidades**: ¿hay señales nuevas de calidad?
4. Revisa **Portafolio**: ¿alguna alerta de venta (stop, trailing, take-profit)?
5. Si decides comprar/vender, **hazlo en tu broker** y luego **regístralo** en el
   dashboard para que el sistema vigile las reglas de salida.

> El sistema **nunca opera por ti**. Solo señala y avisa; tú ejecutas en tu broker.

Si prefieres que la actualización ocurra sola cada día (aunque no abras nada),
deja programada la tarea de Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

---

## 4. Las tres páginas del dashboard

### 4.1 Oportunidades

La tabla lista las señales activas, ordenadas por **score combinado** (las
mejores arriba). Cada columna:

| Columna | Significado |
|---|---|
| **Ticker / empresa** | El activo. |
| **Probabilidad** | P(que alcance +15% en ~6 meses) según el modelo. La marca naranja en la barra es el umbral mínimo. |
| **Calidad** | Score 0–100 de calidad + descuento del negocio (cargador segmentado). |
| **Score** | Ranking final = probabilidad × calidad. |
| **Precio** | Cierre más reciente. |
| **vs SMA200** | Cuánto está por encima/debajo de su media de 200 días. Negativo = en descuento (bueno). |

**Clic en una fila** abre el panel de detalle a la derecha:
- **Gráfico** de precio (verde) con la SMA200 (naranja punteada).
- **"Por qué dispara el modelo"**: las features que más empujan la señal (SHAP).
  Verde = empuja a favor, rojo = en contra. Es la explicación del modelo.
- **Calidad x/100**: desglose por componente (ROIC, márgenes, descuento, deuda…).
- **Noticias recientes** con su sentimiento (punto verde/rojo).
- Botón **"Registrar posición"**: si compraste, regístrala aquí.

El check **"ver descartadas"** muestra las que ocultaste con "Descartar".

### 4.2 Portafolio

Tus **posiciones reales** (las que registraste). Cada tarjeta muestra el P&L y
el estado **en vivo de las 4 reglas de salida**:

| Regla | Qué vigila |
|---|---|
| **Stop loss (−12%)** | Si el precio cae 12% bajo tu entrada → alerta de vender todo. |
| **Trailing stop** | Tras subir +5%, si retrocede 8% desde el pico → vender y proteger ganancia. |
| **Límite de tiempo** | A los 120 días hábiles estancado → vender (costo de oportunidad). |
| **Take profit parcial (+15%)** | Al +15% → vender 33% (asegura ganancia, deja correr el resto). |

A la derecha, el **centro de alertas**: cada vez que una regla se dispara o
aparece una señal nueva, sale aquí. Clic para marcarla leída.

- **+ Posición**: registrar una compra manual.
- **Cerrar / vender**: registrar una venta (total o parcial).
- Avisos de **concentración**: si un activo supera el 10% de tu cartera.

### 4.3 Salud del modelo

Diagnóstico del sistema:
- **Modelo activo**: cuándo se entrenó, con cuántas muestras, su umbral y la
  **precisión/recall out-of-fold** (lo honesto: rendimiento en datos no vistos).
- **Folds**: precisión por periodo histórico (estabilidad en el tiempo).
- **Deriva (drift)**: semáforo de datos y predicciones. Si se pone rojo, el
  mercado cambió de régimen → conviene reentrenar.
- **Importancia de features**: qué variables pesan más en el modelo.
- **Ejecuciones del pipeline**: historial de actualizaciones (éxito/error).
- **Acciones**: botones para actualizar datos, reconstruir dataset o reentrenar.

---

## 5. Cómo decidir con las métricas (lectura honesta)

- Una **probabilidad de 80%** significa que ~1 de cada 5 señales **fallará**. El
  sistema gana en el **agregado** de muchas operaciones, no en aciertos sueltos.
- Prioriza señales con **score alto** (probabilidad y calidad altas) y **buen
  descuento** vs SMA200.
- **Dimensiona** cada posición pequeña (~5% de tu cartera, máx. 15 posiciones,
  máx. 10% por activo). Esto es lo que hace que las pérdidas controladas no te
  saquen del juego.
- **Respeta las reglas de salida.** La rentabilidad histórica viene de cortar
  pérdidas en −9% de media y dejar correr ganadoras a +16% de media.

---

## 6. Cómo funciona por dentro

```
Datos (Point-In-Time)          Modelos                     Decisión
─────────────────────          ───────                     ────────
Precios (yfinance)        ┐
Fundamentales (SEC EDGAR) │   1. Modelo táctico (ML)        Señal SOLO si:
8-K + FinBERT (sentim.)   ├─► HistGradientBoosting       ┌─ prob ≥ umbral
Macro (FRED)              │   "¿+15% en 120 días?"        │  Y calidad ≥ 60
VIX (volatilidad)         ┘   precisión, no cantidad      │  Y precio < SMA200×1.05
                              + umbral: max precisión      │  Y liquidez suficiente
                                con recall ≥ 25%           └─ Y sin recompra < 22 días
                          2. Quality score (reglas)
                             calidad + descuento 0–100
```

**Las 34 features** se calculan respetando el principio **Point-In-Time**: cada
dato solo entra el día en que realmente se publicó (fechas reales de filing de la
SEC, vintages de FRED, rezago de 1 día en el sentimiento). Esto evita el
"look-ahead bias" (hacer trampa con información del futuro).

**Modelo táctico** (`HistGradientBoostingClassifier`): predice la probabilidad de
que el precio alcance **+15% de retorno máximo en 120 días hábiles** (~6 meses).
Se valida con **validación cruzada temporal** (entrena con pasado, valida con
futuro, con un hueco de separación). El umbral de decisión se optimiza para
**maximizar la precisión** exigiendo capturar al menos el 25% de las
oportunidades — filosofía francotirador: dispara poco, pero con alta certeza.

**Quality score** (reglas transparentes, sin ML): puntúa 0–100 combinando
calidad del negocio (ROIC, márgenes, crecimiento), descuento de valoración
(earnings/FCF yield frente a su propia historia, PEG) y solidez financiera
(deuda, cobertura de intereses, dilución). Actúa como **filtro**: una señal solo
cuenta si la empresa es de calidad y está barata.

**Reglas de salida** (preservación del capital primero): stop loss −12%, trailing
−8% tras +5%, límite de 120 días, y take-profit parcial del 33% al +15%.

---

## 7. Mantenimiento

- **Actualizar a diario**: botón "Actualizar" o la tarea programada. Es
  incremental y ligero (no reentrena).
- **Reentrenar el modelo**: cuando el drift se ponga en rojo o cada pocos meses.
  Botón "Reentrenar modelo" en Salud, o `python -m screener.cli train`. Tarda
  varios minutos (usa la GPU para el sentimiento).
- **Altas/bajas de los índices**: el sistema revisa semanalmente los
  constituyentes de S&P 500 + NASDAQ-100 y te avisa con una alerta cuando entra
  o sale una empresa. Forzar: `python -m screener.cli refresh-universe --force`.

---

## 8. Comandos (referencia, opcional)

Desde `backend/` con la terminal, si alguna vez lo necesitas:

| Comando | Para qué |
|---|---|
| `uv run python -m screener.cli run-daily` | Actualización diaria completa. |
| `uv run python -m screener.cli train` | Reentrenar el modelo. |
| `uv run python -m screener.cli score` | Regenerar señales (sin descargar datos). |
| `uv run python -m screener.cli drift` | Chequeo de deriva. |
| `uv run python -m screener.cli backtest --start 2017-01-01` | Backtest histórico. |
| `uv run python -m screener.cli refresh-universe --force` | Actualizar el universo. |

---

## 9. Solución de problemas

| Síntoma | Solución |
|---|---|
| El navegador no abre o da error | Espera 15 s y recarga `http://localhost:8000`. El backend tarda en levantar. |
| "Detener" no cierra el sistema | Vuelve a hacer doble clic; o reinicia el PC (no daña tus datos). |
| El dashboard se ve vacío | Pulsa "Actualizar" para generar señales del día. |
| Faltan datos macro | Revisa que `backend/.env` tenga `FRED_API_KEY`. |
| El icono no aparece en los accesos directos | Reejecuta `scripts/instalar_accesos.ps1`. |

---

## 10. Límites y advertencias

- **No es consejo financiero.** Son señales generadas por un modelo; tú decides
  y asumes el riesgo.
- **Sesgo de supervivencia:** el modelo se entrena con las empresas que HOY están
  en los índices. Las métricas históricas son por ello **optimistas**; el
  rendimiento real será algo menor.
- En el backtest 2017–2026 el sistema **no superó** a comprar y mantener el
  S&P 500 en rentabilidad, aunque tuvo **menor caída máxima**. Trátalo como una
  herramienta de **disciplina y gestión de riesgo**, no como una máquina de
  batir al mercado.

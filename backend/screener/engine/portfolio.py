"""Motor de salidas sobre posiciones REALES registradas por el usuario.

Se evalúa a diario (tras la ingesta). El sistema nunca vende: genera alertas
accionables con la jerarquía del diseño original, donde la preservación del
capital subordina todo lo demás:

1. STOP_LOSS   -12% desde la entrada: amputa la cola izquierda, innegociable.
2. TRAILING    activo tras +5%; dispara a -8% desde el pico máximo.
3. TIME_LIMIT  120 días hábiles estancado: el costo de oportunidad también cuesta.
4. TP_PARCIAL  +15%: vender 33% financia el riesgo del resto (free roll).
"""
import pandas as pd
from sqlalchemy import select

from screener.config import settings
from screener.db import Alert, Position, get_session, init_db
from screener.ingest.prices import load_prices
from screener.universe import load_universe


def check_exit_rules(
    entry_price: float, closes: pd.Series, partial_tp_done: bool
) -> dict:
    """Evalúa la jerarquía de salida. `closes`: cierres desde la entrada (incl. hoy).

    Devuelve estado + lista `triggered` de (tipo, mensaje) en orden jerárquico;
    una salida total (stop/trailing/tiempo) suprime el TP parcial.
    """
    last = float(closes.iloc[-1])
    peak = float(max(closes.max(), entry_price))
    days_held = int(len(closes))
    ret = last / entry_price - 1
    triggered: list[tuple[str, str]] = []

    stop_price = entry_price * (1 - settings.stop_loss_pct)
    if last <= stop_price:
        triggered.append((
            "STOP_LOSS",
            f"VENDER TODO: {ret:+.1%} perfora el stop loss de -{settings.stop_loss_pct:.0%} "
            f"({stop_price:.2f}). Amputar la pérdida ahora.",
        ))

    trailing_active = peak / entry_price - 1 >= settings.trailing_activation_pct
    if not triggered and trailing_active:
        trail_price = peak * (1 - settings.trailing_drop_pct)
        if last <= trail_price:
            triggered.append((
                "TRAILING",
                f"VENDER TODO: retrocedió {last / peak - 1:+.1%} desde el pico {peak:.2f} "
                f"(trailing stop en {trail_price:.2f}). Proteger la ganancia de {ret:+.1%}.",
            ))

    if not triggered and days_held >= settings.time_limit_days:
        triggered.append((
            "TIME_LIMIT",
            f"VENDER: {days_held} días hábiles sin resolverse ({ret:+.1%}). "
            f"El capital estancado tiene costo de oportunidad.",
        ))

    if not triggered and not partial_tp_done and ret >= settings.take_profit_pct:
        triggered.append((
            "TP_PARCIAL",
            f"VENDER {settings.take_profit_fraction:.0%} de la posición: {ret:+.1%} alcanzado. "
            f"Asegura el free roll y deja correr el resto con el trailing.",
        ))

    return {
        "last_price": last,
        "peak_price": peak,
        "days_held": days_held,
        "return_pct": ret,
        "trailing_active": trailing_active,
        "triggered": triggered,
    }


def _closes_since(ticker: str, opened_at) -> pd.Series | None:
    uni = load_universe()
    row = uni[uni["ticker"] == ticker.upper()]
    yf_ticker = row.iloc[0]["yf_ticker"] if not row.empty else ticker.upper().replace(".", "-")
    prices = load_prices(yf_ticker)
    if prices is None or prices.empty:
        return None
    since = prices[prices["date"] >= pd.Timestamp(opened_at)]
    if since.empty:
        return None
    return since.set_index("date")["close"]


def evaluate_positions(log=print) -> None:
    """Actualiza el estado de cada posición abierta y emite alertas nuevas."""
    init_db()
    with get_session() as session:
        positions = session.execute(
            select(Position).where(Position.status == "open")
        ).scalars().all()
        if not positions:
            log("  portafolio: sin posiciones abiertas")
            return

        for p in positions:
            closes = _closes_since(p.ticker, p.opened_at)
            if closes is None:
                log(f"  portafolio: sin precios para {p.ticker}; se omite")
                continue
            state = check_exit_rules(p.entry_price, closes, p.partial_tp_done)
            p.last_price = state["last_price"]
            p.peak_price = state["peak_price"]
            p.days_held = state["days_held"]
            p.last_eval_date = closes.index[-1].date()

            for alert_type, message in state["triggered"]:
                already = session.execute(
                    select(Alert.id).where(
                        Alert.position_id == p.id, Alert.type == alert_type
                    )
                ).scalar()
                if already:
                    continue  # no spamear la misma regla cada día
                severity = "critical" if alert_type in ("STOP_LOSS", "TRAILING") else "warning"
                session.add(Alert(
                    type=alert_type,
                    ticker=p.ticker,
                    position_id=p.id,
                    message=f"{p.ticker}: {message}",
                    severity=severity,
                ))
                log(f"  portafolio: ALERTA {alert_type} en {p.ticker}")

        log(f"  portafolio: {len(positions)} posiciones evaluadas")

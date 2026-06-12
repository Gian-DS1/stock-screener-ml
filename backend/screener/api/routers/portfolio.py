"""Posiciones reales, reglas de salida y centro de alertas.

El sistema NUNCA ejecuta órdenes: registra lo que el usuario operó y le avisa
cuándo las reglas de salida exigen actuar.
"""
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update

from screener.config import settings
from screener.db import Alert, Position, get_session

router = APIRouter(tags=["portfolio"])


def _rule_state(p: Position) -> dict:
    """Estado de cada regla de salida para visualizar en el dashboard."""
    last = p.last_price or p.entry_price
    ret = last / p.entry_price - 1
    peak = max(p.peak_price, p.entry_price)
    trailing_active = peak / p.entry_price - 1 >= settings.trailing_activation_pct
    return {
        "return_pct": ret,
        "stop_loss_price": p.entry_price * (1 - settings.stop_loss_pct),
        "stop_loss_distance": ret + settings.stop_loss_pct,  # margen hasta el stop
        "trailing_active": trailing_active,
        "trailing_stop_price": peak * (1 - settings.trailing_drop_pct) if trailing_active else None,
        "peak_price": peak,
        "days_held": p.days_held,
        "days_left": max(settings.time_limit_days - p.days_held, 0),
        "take_profit_price": p.entry_price * (1 + settings.take_profit_pct),
        "partial_tp_done": p.partial_tp_done,
    }


def _serialize(p: Position) -> dict:
    return {
        "id": p.id,
        "ticker": p.ticker,
        "opened_at": p.opened_at.isoformat(),
        "entry_price": p.entry_price,
        "shares": p.shares,
        "status": p.status,
        "last_price": p.last_price,
        "last_eval_date": p.last_eval_date.isoformat() if p.last_eval_date else None,
        "market_value": (p.last_price or p.entry_price) * p.shares,
        "pnl": ((p.last_price or p.entry_price) - p.entry_price) * p.shares,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "close_price": p.close_price,
        "notes": p.notes,
        "rules": _rule_state(p) if p.status == "open" else None,
    }


@router.get("/positions")
def list_positions(status: str = "open") -> dict:
    with get_session() as session:
        query = select(Position).order_by(Position.opened_at.desc())
        if status != "all":
            query = query.where(Position.status == status)
        positions = [_serialize(p) for p in session.execute(query).scalars().all()]

    open_positions = [p for p in positions if p["status"] == "open"]
    total_value = sum(p["market_value"] for p in open_positions)
    warnings = []
    if len(open_positions) >= settings.max_positions:
        warnings.append(f"Límite de {settings.max_positions} posiciones alcanzado: no abrir más")
    for p in open_positions:
        if total_value > 0 and p["market_value"] / total_value > settings.max_concentration:
            warnings.append(
                f"{p['ticker']} concentra {p['market_value'] / total_value:.0%} "
                f"(máximo {settings.max_concentration:.0%})"
            )
    return {
        "positions": positions,
        "total_value": total_value,
        "n_open": len(open_positions),
        "max_positions": settings.max_positions,
        "warnings": warnings,
    }


class NewPosition(BaseModel):
    ticker: str
    opened_at: date
    entry_price: float
    shares: float
    notes: str | None = None


@router.post("/positions")
def create_position(body: NewPosition) -> dict:
    if body.entry_price <= 0 or body.shares <= 0:
        raise HTTPException(422, "precio y cantidad deben ser positivos")
    with get_session() as session:
        p = Position(
            ticker=body.ticker.upper(),
            opened_at=body.opened_at,
            entry_price=body.entry_price,
            shares=body.shares,
            peak_price=body.entry_price,
            notes=body.notes,
        )
        session.add(p)
        session.flush()
        return _serialize(p)


class ClosePosition(BaseModel):
    close_price: float
    closed_at: date | None = None
    shares: float | None = None  # venta parcial: solo una parte


@router.post("/positions/{position_id}/close")
def close_position(position_id: int, body: ClosePosition) -> dict:
    with get_session() as session:
        p = session.get(Position, position_id)
        if p is None or p.status != "open":
            raise HTTPException(404, "posición abierta no encontrada")
        when = body.closed_at or date.today()
        if body.shares and 0 < body.shares < p.shares:
            # venta parcial: la posición sigue abierta con menos títulos
            p.shares -= body.shares
            p.partial_tp_done = True
            p.notes = (p.notes or "") + f" | venta parcial {body.shares} @ {body.close_price} ({when})"
        else:
            p.status = "closed"
            p.closed_at = when
            p.close_price = body.close_price
        return _serialize(p)


@router.delete("/positions/{position_id}")
def delete_position(position_id: int) -> dict:
    with get_session() as session:
        p = session.get(Position, position_id)
        if p is None:
            raise HTTPException(404, "posición no encontrada")
        session.delete(p)
        return {"ok": True}


@router.get("/alerts")
def list_alerts(unread_only: bool = False, limit: int = 50) -> list[dict]:
    with get_session() as session:
        query = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        if unread_only:
            query = query.where(Alert.read.is_(False))
        return [
            {
                "id": a.id,
                "created_at": a.created_at.isoformat(),
                "type": a.type,
                "ticker": a.ticker,
                "position_id": a.position_id,
                "message": a.message,
                "severity": a.severity,
                "read": a.read,
            }
            for a in session.execute(query).scalars().all()
        ]


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int) -> dict:
    with get_session() as session:
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(404, "alerta no encontrada")
        alert.read = True
        return {"ok": True}


@router.post("/alerts/read-all")
def mark_all_read() -> dict:
    with get_session() as session:
        session.execute(update(Alert).where(Alert.read.is_(False)).values(read=True))
        return {"ok": True}

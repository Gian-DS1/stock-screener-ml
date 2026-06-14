"""Lista de seguimiento del usuario: empresas que quiere vigilar aunque hoy
no sean compra. El screener avisa cuando una favorita dispara señal."""
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from screener.db import Favorite, get_session

router = APIRouter(tags=["favorites"])


def _serialize(f: Favorite) -> dict:
    return {
        "ticker": f.ticker,
        "company": f.company,
        "sector": f.sector,
        "note": f.note,
        "added_at": f.added_at.isoformat(),
    }


@router.get("/favorites")
def list_favorites() -> list[dict]:
    with get_session() as session:
        rows = session.execute(select(Favorite).order_by(Favorite.added_at.desc())).scalars().all()
        return [_serialize(f) for f in rows]


class NewFavorite(BaseModel):
    ticker: str
    company: str | None = None
    sector: str | None = None
    note: str | None = None


@router.post("/favorites")
def add_favorite(body: NewFavorite) -> dict:
    ticker = body.ticker.upper()
    with get_session() as session:
        existing = session.execute(
            select(Favorite).where(Favorite.ticker == ticker)
        ).scalars().first()
        if existing is not None:
            existing.company = body.company or existing.company
            existing.sector = body.sector or existing.sector
            return _serialize(existing)
        fav = Favorite(ticker=ticker, company=body.company, sector=body.sector, note=body.note)
        session.add(fav)
        session.flush()
        return _serialize(fav)


@router.delete("/favorites/{ticker}")
def remove_favorite(ticker: str) -> dict:
    with get_session() as session:
        fav = session.execute(
            select(Favorite).where(Favorite.ticker == ticker.upper())
        ).scalars().first()
        if fav is not None:
            session.delete(fav)
    return {"ok": True}

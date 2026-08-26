"""Avisos del endpoint de portafolio.

El límite de concentración se mide sobre el capital YA invertido, así que con
pocas posiciones abiertas superarlo es aritméticamente inevitable: con 4
posiciones iguales cada una pesa 25%. Avisar ahí sería ruido permanente y
contradiría la filosofía selectiva del screener.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from screener.api import main
from screener.config import settings
from screener.db import Position, get_session, init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    """App con una base de datos vacía y desechable por test."""
    import screener.db.session as db_session

    monkeypatch.setattr(settings, "db_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_SessionLocal", None)
    init_db()
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path / "sin-dist")
    return TestClient(main.create_app())


def _abrir(n: int, valor: float = 5_000.0, prefijo: str = "T") -> None:
    with get_session() as session:
        for i in range(n):
            session.add(
                Position(
                    ticker=f"{prefijo}{i:02d}",
                    opened_at=date(2026, 6, 15),
                    entry_price=100.0,
                    shares=valor / 100.0,
                    peak_price=100.0,
                    last_price=100.0,
                )
            )


def test_sin_posiciones_no_hay_avisos(client):
    body = client.get("/api/positions").json()

    assert body["n_open"] == 0
    assert body["warnings"] == []


def test_pocas_posiciones_no_generan_aviso_de_concentracion(client):
    """Con 4 posiciones iguales cada una pesa 25%, pero el límite es inalcanzable."""
    _abrir(4)

    body = client.get("/api/positions").json()

    assert body["n_open"] == 4
    assert body["warnings"] == []


def test_con_suficientes_posiciones_el_aviso_vuelve_a_ser_informativo(client):
    """10 posiciones iguales pesarían 10% cada una; la del doble sí se pasa."""
    _abrir(9)
    _abrir(1, valor=20_000.0, prefijo="GORDA")

    warnings = client.get("/api/positions").json()["warnings"]

    assert any(w.startswith("GORDA00 concentra") for w in warnings)
    assert not any(w.startswith("T0") for w in warnings)


def test_avisa_al_alcanzar_el_limite_de_posiciones(client):
    _abrir(settings.max_positions)

    warnings = client.get("/api/positions").json()["warnings"]

    assert any("Límite de" in w for w in warnings)

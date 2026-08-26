"""Contrato de la app FastAPI: la SPA no puede romperse al recargar.

El dashboard usa rutas de cliente (/oportunidades, /portafolio, /salud). Con
StaticFiles montado en "/" esas rutas devolvían un 404 JSON al recargar o al
abrir un enlace directo; el fallback debe servir index.html sin tocar /api.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from screener.api import main

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (dist / "logo.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)

    return TestClient(main.create_app())


@pytest.mark.parametrize("ruta", ["/oportunidades", "/portafolio", "/salud"])
def test_las_rutas_de_cliente_sirven_la_spa(client, ruta):
    resp = client.get(ruta)

    assert resp.status_code == 200
    assert "<div id=root>" in resp.text


def test_los_ficheros_reales_se_sirven_tal_cual(client):
    resp = client.get("/logo.svg")

    assert resp.status_code == 200
    assert resp.text == "<svg/>"


def test_la_api_sigue_devolviendo_404_json(client):
    """El fallback no puede tragarse los 404 de la API: rompería el cliente."""
    resp = client.get("/api/no-existe")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}

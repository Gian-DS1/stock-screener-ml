"""La deriva mostrada debe describir al modelo ACTIVO, nunca a uno anterior.

La deriva se mide contra las distribuciones de referencia guardadas dentro del
artefacto, así que el veredicto pertenece a un modelo concreto. Antes, el
dashboard tomaba el último informe de cada tipo sin mirar de qué modelo era: al
reentrenar, el semáforo seguía en "DERIVA DETECTADA" y pedía reentrenar en
bucle, describiendo un modelo que ya no estaba en uso.
"""
import json

import pytest
from fastapi.testclient import TestClient

from screener.api import main
from screener.config import settings
from screener.db import DriftReport, ModelRecord, get_session, init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    import screener.db.session as db_session

    monkeypatch.setattr(settings, "db_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_SessionLocal", None)
    init_db()
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path / "sin-dist")
    return TestClient(main.create_app())


def _modelo(activo: bool) -> int:
    with get_session() as session:
        record = ModelRecord(
            model_path="tactical_x.joblib",
            threshold=0.75,
            horizon_days=120,
            min_return=0.15,
            n_samples=1000,
            n_features=34,
            metrics_json=json.dumps({"folds": [], "oof": {}}),
            feature_names_json=json.dumps([]),
            active=activo,
        )
        session.add(record)
        session.flush()
        return record.id


def _informe(kind: str, drifted: bool, model_id: int | None) -> None:
    with get_session() as session:
        session.add(
            DriftReport(kind=kind, drifted=drifted, metric=0.2, model_id=model_id)
        )


def test_la_deriva_del_modelo_anterior_no_se_muestra(client):
    """Reentrenar deja el semáforo en 'sin datos', no en la alarma vieja."""
    viejo = _modelo(activo=False)
    _informe("prediction", drifted=True, model_id=viejo)
    _modelo(activo=True)  # reentrenamiento: modelo nuevo, aún sin chequeo

    drift = client.get("/api/health/summary").json()["drift"]

    assert drift == {}


def test_la_deriva_del_modelo_activo_si_se_muestra(client):
    activo = _modelo(activo=True)
    _informe("prediction", drifted=True, model_id=activo)

    drift = client.get("/api/health/summary").json()["drift"]

    assert drift["prediction"]["drifted"] is True


def test_los_informes_sin_modelo_no_cuentan_como_vigentes(client):
    """Filas anteriores a la columna model_id: modelo desconocido, no vigentes."""
    _modelo(activo=True)
    _informe("prediction", drifted=True, model_id=None)

    drift = client.get("/api/health/summary").json()["drift"]

    assert drift == {}


def test_sin_modelo_entrenado_no_hay_deriva_que_mostrar(client):
    _informe("prediction", drifted=True, model_id=None)

    body = client.get("/api/health/summary").json()

    assert body["model"] is None
    assert body["drift"] == {}

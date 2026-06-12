"""Registro y carga del modelo táctico activo.

Seguridad: joblib deserializa con pickle, que puede ejecutar código arbitrario.
Aquí es seguro porque los artefactos los genera SIEMPRE este mismo sistema en
models/ (uso personal, local); nunca se cargan modelos de terceros.
"""
import json
from functools import lru_cache

import joblib
from sqlalchemy import select, update

from screener.config import settings
from screener.db import ModelRecord, get_session, init_db


def register_model(
    model_path: str,
    threshold: float,
    n_samples: int,
    metrics_json: str,
    importances_json: str,
) -> dict:
    from screener.features import ALL_FEATURES

    init_db()
    with get_session() as session:
        session.execute(update(ModelRecord).values(active=False))
        record = ModelRecord(
            model_path=model_path,
            threshold=threshold,
            horizon_days=settings.prediction_horizon_days,
            min_return=settings.min_return_target,
            n_samples=n_samples,
            n_features=len(ALL_FEATURES),
            metrics_json=metrics_json,
            feature_names_json=json.dumps(ALL_FEATURES),
            importances_json=importances_json,
            active=True,
        )
        session.add(record)
        session.flush()
        load_active_artifact.cache_clear()
        return {
            "id": record.id,
            "model_path": model_path,
            "threshold": threshold,
            "n_samples": n_samples,
        }


def get_active_record() -> ModelRecord | None:
    init_db()
    with get_session() as session:
        return session.execute(
            select(ModelRecord).where(ModelRecord.active).order_by(ModelRecord.id.desc())
        ).scalars().first()


@lru_cache(maxsize=1)
def load_active_artifact() -> dict:
    record = get_active_record()
    if record is None:
        raise RuntimeError("No hay modelo entrenado: ejecuta `train` primero")
    return joblib.load(record.model_path)

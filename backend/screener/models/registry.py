"""Registro y carga del modelo táctico activo.

Seguridad: joblib deserializa con pickle, que puede ejecutar código arbitrario.
Aquí es seguro porque los artefactos los genera SIEMPRE este mismo sistema en
models/ (uso personal, local); nunca se cargan modelos de terceros.
"""
import json
import ntpath
from functools import lru_cache
from pathlib import Path

import joblib
from sqlalchemy import select, update

from screener.config import settings
from screener.db import ModelRecord, get_session, init_db


def _basename(path: str) -> str:
    """Nombre de fichero a partir de una ruta, sea cual sea su SO de origen.

    `pathlib.Path(...).name` solo separa por el delimitador del SO actual: en
    Linux (CI, contenedores) una ruta de un registro antiguo entrenado en
    Windows ("C:\\...\\modelo.joblib") no tiene ninguna barra normal, así que
    `.name` devuelve la ruta completa en vez del nombre. `ntpath.basename`
    reconoce ambos separadores en cualquier plataforma.
    """
    return ntpath.basename(path)


def resolve_model_path(model_path: str) -> Path:
    """Devuelve la ruta absoluta del artefacto en la instalación actual.

    En el registro se guarda solo el nombre del fichero, de modo que el proyecto
    se pueda mover o clonar sin romper la carga. Los registros antiguos guardaban
    la ruta absoluta de la máquina donde se entrenó: de ahí el fallback por nombre.
    """
    candidate = Path(model_path)
    if candidate.is_file():
        return candidate
    return settings.models_dir / _basename(model_path)


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
            model_path=_basename(model_path),
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
    path = resolve_model_path(record.model_path)
    if not path.is_file():
        raise RuntimeError(
            f"El artefacto '{path.name}' no está en {settings.models_dir}. "
            "Vuelve a ejecutar `train` para regenerarlo."
        )
    return joblib.load(path)

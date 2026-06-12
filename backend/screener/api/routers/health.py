"""Salud del modelo: métricas de entrenamiento, drift y auditoría de runs."""
import json

from fastapi import APIRouter
from sqlalchemy import select

from screener.config import settings
from screener.db import DriftReport, ModelRecord, Run, get_session

router = APIRouter(tags=["health"])


@router.get("/health/summary")
def health_summary() -> dict:
    with get_session() as session:
        model = session.execute(
            select(ModelRecord).where(ModelRecord.active).order_by(ModelRecord.id.desc())
        ).scalars().first()

        drift_reports = {}
        for kind in ("data", "prediction"):
            report = session.execute(
                select(DriftReport).where(DriftReport.kind == kind)
                .order_by(DriftReport.id.desc())
            ).scalars().first()
            if report:
                drift_reports[kind] = {
                    "created_at": report.created_at.isoformat(),
                    "drifted": report.drifted,
                    "metric": report.metric,
                    "detail": json.loads(report.detail_json) if report.detail_json else None,
                }

        runs = session.execute(select(Run).order_by(Run.id.desc()).limit(15)).scalars().all()

    return {
        "model": None if model is None else {
            "id": model.id,
            "trained_at": model.trained_at.isoformat(),
            "threshold": model.threshold,
            "horizon_days": model.horizon_days,
            "min_return": model.min_return,
            "n_samples": model.n_samples,
            "n_features": model.n_features,
            "metrics": json.loads(model.metrics_json),
            "importances": json.loads(model.importances_json or "{}"),
        },
        "drift": drift_reports,
        "runs": [
            {
                "id": r.id,
                "kind": r.kind,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "detail": (r.detail or "")[:400],
            }
            for r in runs
        ],
        "config": {
            "quality_gate": settings.quality_gate,
            "sma_headroom": settings.sma_headroom,
            "cooldown_days": settings.cooldown_days,
            "recall_floor": settings.recall_floor,
            "horizon_days": settings.prediction_horizon_days,
            "min_return_target": settings.min_return_target,
        },
    }

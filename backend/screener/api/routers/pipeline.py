"""Disparo manual del pipeline desde el dashboard (un job a la vez)."""
import threading

from fastapi import APIRouter, HTTPException

from screener.pipeline import audited_run

router = APIRouter(tags=["pipeline"])

_lock = threading.Lock()
_current: dict = {"kind": None}

_JOBS = {
    "run-daily": "run_daily_pipeline",
    "score": "run_score",
    "train": "run_train",
    "build-dataset": "run_build_dataset",
    "drift": "run_drift",
}


def _execute(kind: str) -> None:
    import screener.pipeline as pipeline

    fn = getattr(pipeline, _JOBS[kind])
    try:
        with audited_run("daily" if kind == "run-daily" else kind):
            fn()
    except Exception:
        pass  # el traceback queda registrado en la tabla runs
    finally:
        with _lock:
            _current["kind"] = None


@router.post("/pipeline/{kind}")
def trigger(kind: str) -> dict:
    if kind not in _JOBS:
        raise HTTPException(404, f"job desconocido: {kind}")
    with _lock:
        if _current["kind"] is not None:
            raise HTTPException(409, f"ya hay un job en ejecución: {_current['kind']}")
        _current["kind"] = kind
    threading.Thread(target=_execute, args=(kind,), daemon=True).start()
    return {"started": kind}


@router.get("/pipeline/status")
def status() -> dict:
    return {"running": _current["kind"]}

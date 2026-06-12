"""Esquema de la base de datos de la aplicación (SQLite).

El data lake analítico vive en Parquet; aquí solo va el estado de la app:
señales emitidas, posiciones reales, alertas, auditoría de runs y registro de modelos.
"""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Run(Base):
    """Auditoría de cada ejecución del pipeline (daily, backfill, train, drift)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # daily | backfill | train | drift | score
    status: Mapped[str] = mapped_column(String(10), default="running")  # running | success | error
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # resumen o traceback


class Signal(Base):
    """Señal de compra emitida por el screener para una fecha dada."""

    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("date", "ticker", name="uq_signal_date_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    company: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(60), nullable=True)
    probability: Mapped[float] = mapped_column(Float)       # P(retorno >= target) del modelo táctico
    quality_score: Mapped[float] = mapped_column(Float)     # score largo plazo 0-100
    combined_score: Mapped[float] = mapped_column(Float)    # ranking final
    price: Mapped[float] = mapped_column(Float)
    sma200: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_vs_sma200: Mapped[float | None] = mapped_column(Float, nullable=True)  # precio/SMA200 - 1
    shap_json: Mapped[str | None] = mapped_column(Text, nullable=True)         # top features que explican la señal
    quality_breakdown_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="new")  # new | dismissed | bought


class Position(Base):
    """Posición real registrada manualmente por el usuario."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    opened_at: Mapped[date] = mapped_column(Date)
    entry_price: Mapped[float] = mapped_column(Float)
    shares: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | closed

    # Estado del motor de salidas (actualizado en cada evaluación diaria)
    peak_price: Mapped[float] = mapped_column(Float, default=0.0)   # máximo de cierre desde la entrada
    partial_tp_done: Mapped[bool] = mapped_column(Boolean, default=False)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_eval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_held: Mapped[int] = mapped_column(Integer, default=0)      # días hábiles

    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base):
    """Alerta accionable mostrada en el dashboard. El sistema nunca opera solo."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    type: Mapped[str] = mapped_column(String(20))  # STOP_LOSS | TRAILING | TIME_LIMIT | TP_PARCIAL | NUEVA_SENAL | DRIFT
    ticker: Mapped[str | None] = mapped_column(String(10), nullable=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info | warning | critical
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelRecord(Base):
    """Registro de cada modelo táctico entrenado y su umbral óptimo."""

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    model_path: Mapped[str] = mapped_column(String(260))
    threshold: Mapped[float] = mapped_column(Float)
    horizon_days: Mapped[int] = mapped_column(Integer)
    min_return: Mapped[float] = mapped_column(Float)
    n_samples: Mapped[int] = mapped_column(Integer)
    n_features: Mapped[int] = mapped_column(Integer)
    metrics_json: Mapped[str] = mapped_column(Text)          # precision/recall por fold + agregados OOF
    feature_names_json: Mapped[str] = mapped_column(Text)
    importances_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DriftReport(Base):
    """Resultado de cada chequeo de deriva de datos o de predicciones."""

    __tablename__ = "drift_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    kind: Mapped[str] = mapped_column(String(12))  # data | prediction
    drifted: Mapped[bool] = mapped_column(Boolean)
    metric: Mapped[float] = mapped_column(Float)   # share de columnas con drift, o estadístico KS
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)

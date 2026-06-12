"""Configuración central del sistema.

Todos los umbrales de la estrategia viven aquí para que el screener, el motor
de portafolio, el labeling y el backtest usen exactamente los mismos valores.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- API keys / identificación ---
    fred_api_key: str = ""
    finnhub_api_key: str = ""
    sec_user_agent: str = "SniperScreener personal contacto@example.com"

    # --- Rutas ---
    data_dir: Path = PROJECT_ROOT / "data"
    models_dir: Path = PROJECT_ROOT / "models"
    db_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}"

    # --- Target / modelo táctico ---
    prediction_horizon_days: int = 120  # días hábiles hacia adelante
    min_return_target: float = 0.15     # retorno máximo requerido en la ventana
    recall_floor: float = 0.25          # restricción para optimizar el umbral
    cv_folds: int = 5                   # folds expanding-window

    # --- Filtros de entrada del screener ---
    quality_gate: float = 60.0          # score de calidad mínimo (0-100)
    sma_headroom: float = 1.05          # precio < SMA200 * headroom
    min_dollar_volume: float = 5_000_000.0  # volumen medio diario en USD (20d)
    cooldown_days: int = 22             # días hábiles sin recomprar el mismo ticker

    # --- Gestión de portafolio ---
    position_size_pct: float = 0.05
    max_positions: int = 15
    max_concentration: float = 0.10

    # --- Reglas de salida ---
    stop_loss_pct: float = 0.12         # -12% desde la entrada
    trailing_activation_pct: float = 0.05  # trailing activo tras +5%
    trailing_drop_pct: float = 0.08     # -8% desde el pico
    time_limit_days: int = 120          # días hábiles máximos de holding
    take_profit_pct: float = 0.15       # +15% dispara TP parcial
    take_profit_fraction: float = 0.33  # fracción vendida en el TP parcial

    # --- Universo / datos ---
    price_history_start: str = "2014-01-01"
    min_history_days: int = 300         # historial mínimo para puntuar un ticker

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def features_dir(self) -> Path:
        return self.data_dir / "features"


settings = Settings()


def ensure_dirs() -> None:
    for d in (
        settings.data_dir,
        settings.raw_dir,
        settings.raw_dir / "prices",
        settings.features_dir,
        settings.models_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)

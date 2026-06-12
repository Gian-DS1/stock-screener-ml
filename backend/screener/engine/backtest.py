"""Backtest de la estrategia completa (CLI, sin UI): validación, no optimización.

Honestidad metodológica:
- Las probabilidades son OUT-OF-FOLD (mismo CV temporal del entrenamiento):
  ninguna señal histórica usa un modelo que haya visto su propio futuro.
- Entrada al cierre del día hábil SIGUIENTE a la señal (la señal se genera
  tras el cierre del viernes).
- Universo actual => sesgo de supervivencia: los resultados son optimistas,
  útiles para validar la mecánica y comparar variantes, no como promesa.

Uso: python -m screener.cli backtest --start 2018-01-01
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from screener.config import settings
from screener.features import ALL_FEATURES
from screener.features.builder import dataset_path
from screener.ingest.prices import load_close_matrix
from screener.models.quality import quality_score
from screener.models.tactical import _expanding_folds, _make_model, optimize_threshold, _CALENDAR_PER_TRADING
from screener.universe import load_universe


@dataclass
class _Position:
    ticker: str
    entry_price: float
    shares: float
    entry_date: pd.Timestamp
    peak: float = 0.0
    days: int = 0
    partial_done: bool = False

    def __post_init__(self):
        self.peak = self.entry_price


@dataclass
class _Trade:
    ticker: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: float
    reason: str

    @property
    def ret(self) -> float:
        return self.exit_price / self.entry_price - 1


def _oof_probabilities(df: pd.DataFrame, log) -> np.ndarray:
    gap = pd.Timedelta(days=int(settings.prediction_horizon_days * _CALENDAR_PER_TRADING) + 7)
    unique_dates = np.sort(df["date"].unique())
    base_cutoff = unique_dates[int(len(unique_dates) * 0.4)] - gap
    base = df[df["date"] < base_cutoff]
    features = [f for f in ALL_FEATURES if base[f].dropna().nunique() >= 2]
    X = df[features].to_numpy(dtype=float)
    y = df["label"].to_numpy(dtype=int)

    oof = np.full(len(df), np.nan)
    for k, (train_mask, val_mask, _) in enumerate(
        _expanding_folds(df["date"], settings.cv_folds, gap)
    ):
        model = _make_model()
        model.fit(X[train_mask], y[train_mask])
        oof[val_mask] = model.predict_proba(X[val_mask])[:, 1]
        log(f"  backtest: fold {k} listo ({val_mask.sum():,} predicciones OOF)")
    return oof


def run_backtest(start: str = "2018-01-01", end: str | None = None, capital: float = 100_000.0, log=print) -> dict:
    df = pd.read_parquet(dataset_path()).dropna(subset=["label"]).sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    log(f"  backtest: dataset {len(df):,} filas")

    df["prob"] = _oof_probabilities(df, log)
    scored = df.dropna(subset=["prob"]).copy()
    threshold, prec, rec = optimize_threshold(
        scored["label"].to_numpy(int), scored["prob"].to_numpy(), settings.recall_floor
    )
    log(f"  backtest: umbral OOF={threshold:.3f} (precisión {prec:.1%}, recall {rec:.1%})")

    quality, _ = quality_score(scored)
    scored["quality"] = quality
    candidates = scored[
        (scored["prob"] >= threshold)
        & (scored["quality"] >= settings.quality_gate)
        & scored["sma200"].notna()
        & (scored["close"] < scored["sma200"] * settings.sma_headroom)
        & (scored["dollar_volume_20d"] >= settings.min_dollar_volume)
    ].copy()
    candidates["score"] = candidates["prob"] * candidates["quality"] / 100
    log(f"  backtest: {len(candidates):,} señales candidatas históricas")

    uni = load_universe()
    yf_map = dict(zip(uni["ticker"], uni["yf_ticker"]))
    closes = load_close_matrix([yf_map.get(t, t) for t in scored["ticker"].unique()])
    closes = closes.rename(columns={v: k for k, v in yf_map.items()})
    closes = closes.loc[(closes.index >= pd.Timestamp(start)) & (closes.index <= pd.Timestamp(end or "2100-01-01"))]

    signals_by_date: dict[pd.Timestamp, pd.DataFrame] = {
        d: g.sort_values("score", ascending=False) for d, g in candidates.groupby("date")
    }

    cash = capital
    positions: dict[str, _Position] = {}
    trades: list[_Trade] = []
    cooldown_until: dict[str, pd.Timestamp] = {}
    pending_entries: list[str] = []
    equity_curve = []
    cd_offset = pd.offsets.BDay(settings.cooldown_days)

    for day in closes.index:
        prices_today = closes.loc[day]

        # 1) SALIDAS primero: garantizar liquidez real antes de cualquier compra
        for ticker in list(positions):
            price = prices_today.get(ticker)
            if pd.isna(price):
                continue
            p = positions[ticker]
            p.days += 1
            p.peak = max(p.peak, price)
            ret = price / p.entry_price - 1
            reason = None
            if price <= p.entry_price * (1 - settings.stop_loss_pct):
                reason = "STOP_LOSS"
            elif (
                p.peak / p.entry_price - 1 >= settings.trailing_activation_pct
                and price <= p.peak * (1 - settings.trailing_drop_pct)
            ):
                reason = "TRAILING"
            elif p.days >= settings.time_limit_days:
                reason = "TIME_LIMIT"
            elif not p.partial_done and ret >= settings.take_profit_pct:
                # TP parcial: vende 33%, el resto sigue con trailing (free roll)
                sold = p.shares * settings.take_profit_fraction
                cash += sold * price
                trades.append(_Trade(ticker, p.entry_date, day, p.entry_price, price, sold, "TP_PARCIAL"))
                p.shares -= sold
                p.partial_done = True
                continue
            if reason:
                cash += p.shares * price
                trades.append(_Trade(ticker, p.entry_date, day, p.entry_price, price, p.shares, reason))
                del positions[ticker]
                cooldown_until[ticker] = day + cd_offset

        # equity al cierre de hoy (para dimensionar entradas)
        market_value = sum(
            p.shares * prices_today.get(t, p.entry_price) for t, p in positions.items()
        )
        equity = cash + market_value

        # 2) ENTRADAS pendientes de la señal de ayer (al cierre de hoy)
        for ticker in pending_entries:
            price = prices_today.get(ticker)
            if (
                pd.isna(price)
                or ticker in positions
                or len(positions) >= settings.max_positions
                or cooldown_until.get(ticker, pd.Timestamp.min) > day
            ):
                continue
            size = equity * settings.position_size_pct
            if size > cash:
                continue
            shares = size / price
            cash -= size
            positions[ticker] = _Position(ticker, price, shares, day)
        pending_entries = []

        # 3) señales generadas HOY se ejecutan mañana
        if day in signals_by_date:
            pending_entries = signals_by_date[day]["ticker"].tolist()

        equity_curve.append((day, equity))

    eq = pd.Series(dict(equity_curve)).sort_index()
    total_return = eq.iloc[-1] / capital - 1
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    cagr = (eq.iloc[-1] / capital) ** (1 / years) - 1
    drawdown = (eq / eq.cummax() - 1).min()
    full_exits = [t for t in trades if t.reason != "TP_PARCIAL"]
    wins = [t for t in full_exits if t.ret > 0]

    log("")
    log(f"  ===== BACKTEST {eq.index[0].date()} -> {eq.index[-1].date()} =====")
    log(f"  capital final     : {eq.iloc[-1]:>12,.0f}  (inicial {capital:,.0f})")
    log(f"  retorno total     : {total_return:>11.1%}")
    log(f"  CAGR              : {cagr:>11.1%}")
    log(f"  max drawdown      : {drawdown:>11.1%}")
    log(f"  trades cerrados   : {len(full_exits)} (+{len(trades) - len(full_exits)} TP parciales)")
    if full_exits:
        log(f"  win rate          : {len(wins) / len(full_exits):>11.1%}")
        log(f"  retorno medio     : {np.mean([t.ret for t in full_exits]):>11.1%}")
        by_reason = pd.Series([t.reason for t in full_exits]).value_counts()
        for reason, count in by_reason.items():
            log(f"    salidas {reason:<11}: {count}")
    log("  AVISO: universo actual => sesgo de supervivencia; resultados optimistas.")

    trades_df = pd.DataFrame([vars(t) | {"ret": t.ret} for t in trades])
    out_path = settings.data_dir / "backtest_trades.csv"
    trades_df.to_csv(out_path, index=False)
    log(f"  trades guardados en {out_path}")

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "max_drawdown": float(drawdown),
        "n_trades": len(full_exits),
        "win_rate": len(wins) / len(full_exits) if full_exits else None,
    }

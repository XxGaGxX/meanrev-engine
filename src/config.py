"""Typed configuration loader.

Single source of truth: config/settings.yaml.
NO hardcoded parameters anywhere else in the codebase — they all flow through
this module. See docs/superpowers/plans/ROADMAP_MVP.md, Phase 0 gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Default location shared by tests and runtime; overridable via load_settings().
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    universe_size: int
    gap_min_pct: float
    gap_max_pct: float
    opening_range_bars: int
    confirmation_bars: int


@dataclass(frozen=True)
class DataConfig:
    start_date: date
    end_date: date
    dev_end_date: date
    cache_dir: str

    def __post_init__(self) -> None:
        # Roadmap requires temporal ordering and a 5y+ window.
        if not (self.start_date < self.dev_end_date < self.end_date):
            raise ValueError(
                "data config: require start_date < dev_end_date < end_date; "
                f"got {self.start_date} / {self.dev_end_date} / {self.end_date}"
            )


@dataclass(frozen=True)
class ExecutionConfig:
    broker: str
    paper_trading: bool
    forced_exit_time: str
    risk_per_trade: float
    initial_capital: float


@dataclass(frozen=True)
class RiskConfig:
    """Position sizing / exit parameters (Phase 4 + Fase A quant fix)."""
    sl_atr_multiple: float
    tp_extend_atr_multiple: float
    partial_tp_frac: float
    time_stop_bars: Optional[int]


@dataclass(frozen=True)
class FiltersConfig:
    """Entry filters (Phase 3+ / Fase A winrate lift)."""
    ema_period: int
    use_ema_filter: bool
    gap_min_pct: float
    gap_max_pct: float
    vix_max: float
    adx_max: float


@dataclass(frozen=True)
class GatesConfig:
    """Decision thresholds lifted out of settings.yaml so the rest of the
    code reads typed constants."""

    eda_min_trades_per_cell: int
    backtest_oos_min_sharpe: float
    backtest_oos_min_profit_factor: float
    paper_trading_min_days: int


@dataclass(frozen=True)
class Settings:
    strategy: StrategyConfig
    data: DataConfig
    execution: ExecutionConfig
    gates: GatesConfig
    risk: RiskConfig
    filters: FiltersConfig


def _coerce_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"{field}: expected ISO date string, got {type(value).__name__}")


def load_settings(path: Path | None = None) -> Settings:
    """Load and validate config/settings.yaml into a typed Settings object.

    Raises FileNotFoundError if the path does not exist.
    Raises ValueError/KeyError/TypeError on malformed config.
    """
    settings_path = path or SETTINGS_PATH
    if not settings_path.is_file():
        raise FileNotFoundError(f"settings file not found: {settings_path}")

    with settings_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    try:
        s = raw["strategy"]
        d = raw["data"]
        e = raw["execution"]
        g = raw["gates"]
        r = raw["risk"]
        f = raw["filters"]
    except KeyError as exc:
        raise KeyError(f"settings.yaml missing required block: {exc}") from exc

    data_cfg = DataConfig(
        start_date=_coerce_date(d["start_date"], "data.start_date"),
        end_date=_coerce_date(d["end_date"], "data.end_date"),
        dev_end_date=_coerce_date(d["dev_end_date"], "data.dev_end_date"),
        cache_dir=str(d["cache_dir"]),
    )

    strategy_cfg = StrategyConfig(
        name=str(s["name"]),
        universe_size=int(s["universe_size"]),
        gap_min_pct=float(s["gap_min_pct"]),
        gap_max_pct=float(s["gap_max_pct"]),
        opening_range_bars=int(s["opening_range_bars"]),
        confirmation_bars=int(s["confirmation_bars"]),
    )

    execution_cfg = ExecutionConfig(
        broker=str(e["broker"]),
        paper_trading=bool(e["paper_trading"]),
        forced_exit_time=str(e["forced_exit_time"]),
        risk_per_trade=float(e["risk_per_trade"]),
        initial_capital=float(e["initial_capital"]),
    )

    gates_cfg = GatesConfig(
        eda_min_trades_per_cell=int(g["eda_min_trades_per_cell"]),
        backtest_oos_min_sharpe=float(g["backtest_oos_min_sharpe"]),
        backtest_oos_min_profit_factor=float(g["backtest_oos_min_profit_factor"]),
        paper_trading_min_days=int(g["paper_trading_min_days"]),
    )

    risk_cfg = RiskConfig(
        sl_atr_multiple=float(r["sl_atr_multiple"]),
        tp_extend_atr_multiple=float(r["tp_extend_atr_multiple"]),
        partial_tp_frac=float(r["partial_tp_frac"]),
        time_stop_bars=(int(r["time_stop_bars"]) if r.get("time_stop_bars") is not None else None),
    )

    filters_cfg = FiltersConfig(
        ema_period=int(f["ema_period"]),
        use_ema_filter=bool(f["use_ema_filter"]),
        gap_min_pct=float(f["gap_min_pct"]),
        gap_max_pct=float(f["gap_max_pct"]),
        vix_max=float(f["vix_max"]),
        adx_max=float(f["adx_max"]),
    )

    return Settings(
        strategy=strategy_cfg,
        data=data_cfg,
        execution=execution_cfg,
        gates=gates_cfg,
        risk=risk_cfg,
        filters=filters_cfg,
    )

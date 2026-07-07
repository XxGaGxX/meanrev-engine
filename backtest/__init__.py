"""
Backtest Package — Mean Reversion Intraday (FASE 4)
====================================================

Engine wrapper that runs the FULL strategy pipeline (clean → indicators →
regime → entry → exit → risk-based sizing → equity curves → metrics)
against a single in-memory OHLCV DataFrame and returns an aggregated result.

Slices
------
- Slice 1 (this file): In-memory single-symbol pipeline composition.
- Slice 2 (planned) : `run_backtest_for_symbol(symbol, cfg)` — adds the
                       data-fetch layer on top of Slice 1.
- Slice 3 (done)    : `run_universe_backtest(symbols, cfg, ...)` — multi-symbol
                       orchestration with per-symbol metrics. Dict-level
                       aggregation only (no portfolio semantics).
- Slice 4 (planned) : Portfolio aggregation with `max_open_positions` cap
                       and cross-symbol correlation limits.

Usage
-----
    from backtest import run_backtest
    result = run_backtest(df_raw, cfg={"regime_filter": {"adx_threshold": 30.0}})
    print(result.metrics["sharpe_ratio"])
"""

from .engine import BacktestResult, run_backtest, run_universe_backtest

__all__ = ["BacktestResult", "run_backtest", "run_universe_backtest"]

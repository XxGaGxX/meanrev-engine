"""Tests for Phase 3+ regime filter (TDD, RED before GREEN).

Contract (docs/specs §2.4 Regime Classification + our quant finding that
the 5-min backtest loses ONLY in trending regimes):

  A trade is ALLOWED only if the market regime is NOT adverse:
    - ADX(14) below `adx_max` (no strong trend)
    - For LONG:  price >= 200EMA (uptrend allowed) is OK, but a strong
      uptrend with high ADX is filtered. We keep it simple: block when
      ADX > adx_max regardless of direction (strong trend = no mean-rev).
    - VIX below `vix_max` (already a Fase 3 gate input elsewhere).

Pure functions, no IO.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategy.filters import (
    compute_adx,
    compute_ema,
    regime_allows_trade,
    ema_filter_allows,
)


def _ohlc_series(highs, lows, closes):
    return pd.DataFrame({
        "high": pd.Series(highs, dtype=float),
        "low": pd.Series(lows, dtype=float),
        "close": pd.Series(closes, dtype=float),
    })


def test_compute_ema_basic() -> None:
    closes = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], dtype=float)
    ema = compute_ema(closes, 3)
    assert len(ema) == 5
    # EMA should be between min and max, increasing
    assert ema.iloc[-1] > ema.iloc[0]


def test_compute_adx_rises_in_trend() -> None:
    # Strong uptrend: ADX should be high (> threshold).
    n = 40
    closes = np.linspace(100, 200, n)  # monotonic up
    highs = closes + 1
    lows = closes - 1
    df = _ohlc_series(highs, lows, closes)
    adx = compute_adx(df, period=14)
    assert adx.iloc[-1] > 25  # strong trend


def test_compute_adx_low_in_chop() -> None:
    # Near-flat noisy series: ADX should be low (no sustained direction).
    n = 40
    rng = np.random.default_rng(0)
    closes = 100 + np.cumsum(rng.normal(0, 0.2, n))
    highs = closes + 0.3
    lows = closes - 0.3
    df = _ohlc_series(highs, lows, closes)
    adx = compute_adx(df, period=14)
    assert adx.iloc[-1] < 25


def test_regime_allows_in_chop_low_adx() -> None:
    n = 40
    rng = np.random.default_rng(0)
    closes = 100 + np.cumsum(rng.normal(0, 0.2, n))
    highs = closes + 0.3
    lows = closes - 0.3
    df = _ohlc_series(highs, lows, closes)
    # price ~ 100, ema ~ 100, adx low -> allowed
    allowed = regime_allows_trade(
        df, direction="LONG", adx_max=25, ema_period=20, vix=None, vix_max=30,
    )
    assert allowed is True


def test_regime_blocks_strong_trend() -> None:
    n = 40
    closes = np.linspace(100, 200, n)
    highs = closes + 1
    lows = closes - 1
    df = _ohlc_series(highs, lows, closes)
    allowed = regime_allows_trade(
        df, direction="LONG", adx_max=25, ema_period=20, vix=None, vix_max=30,
    )
    assert allowed is False  # strong trend -> block


def test_regime_blocks_high_vix() -> None:
    n = 40
    closes = 100 + np.sin(np.linspace(0, 10, n))
    highs = closes + 0.5
    lows = closes - 0.5
    df = _ohlc_series(highs, lows, closes)
    allowed = regime_allows_trade(
        df, direction="LONG", adx_max=25, ema_period=20, vix=35.0, vix_max=30,
    )
    assert allowed is False  # VIX > 30 -> no trade


def test_ema_filter_allows_long_below_ema() -> None:
    """LONG (down gap) only allowed when price is BELOW the EMA."""
    n = 60
    closes = np.linspace(100, 110, n, dtype=float)
    df = _ohlc_series(closes + 0.5, closes - 0.5, closes)
    # price still above EMA -> LONG blocked
    assert bool(ema_filter_allows(df, direction="LONG", ema_period=20)) is False
    # pull last price below EMA -> overshoot -> LONG allowed
    df_below = df.copy()
    df_below.loc[df_below.index[-1], "close"] = 95.0
    assert bool(ema_filter_allows(df_below, direction="LONG", ema_period=20)) is True


def test_ema_filter_allows_short_above_ema() -> None:
    n = 60
    closes = np.linspace(100, 110, n, dtype=float)
    df = _ohlc_series(closes + 0.5, closes - 0.5, closes)
    # price above EMA -> SHORT (up-gap overshoot) allowed
    assert bool(ema_filter_allows(df, direction="SHORT", ema_period=20)) is True
    # push last price below EMA -> SHORT blocked
    df_below = df.copy()
    df_below.loc[df_below.index[-1], "close"] = 95.0
    assert bool(ema_filter_allows(df_below, direction="SHORT", ema_period=20)) is False


def test_ema_filter_blocks_short_history() -> None:
    n = 10
    closes = np.linspace(100, 110, n, dtype=float)
    df = _ohlc_series(closes + 0.5, closes - 0.5, closes)
    # < ema_period bars -> conservative BLOCK
    assert bool(ema_filter_allows(df, direction="LONG", ema_period=20)) is False

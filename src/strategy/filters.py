"""Phase 3+ regime filter — keep mean-reversion out of adverse regimes.

The design doc (§2.4) lists four ways mean reversion fails: regime
change, news-driven gap, strong trend, high volatility. The 5-min
backtest confirmed the third: in a trending market the strategy loses.
This module lets the orchestrator SKIP trades when the regime is
adverse, using only data available at the decision timestamp (no
look-ahead).

Pure functions, no IO, no hidden state.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average. Returns a Series aligned to input."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period!r}")
    return series.ewm(span=period, adjust=False).mean()


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index. High => strong trend (either direction).

    Returns a Series aligned to df index; first `period` values are NaN
    (insufficient history). Caller should use the LAST value.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period!r}")
    if not {"high", "low", "close"}.issubset(df.columns):
        raise ValueError("df must have high/low/close columns")
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = (up.where((up > 0) & (up > down), 0.0))
    minus_dm = (down.where((down > 0) & (down > up), 0.0))
    tr = _true_range(df)

    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, float("nan"))
    dx = dx.fillna(0.0) * 100.0  # ADX is expressed in 0..100
    adx = dx.rolling(period).mean()
    return adx


def regime_allows_trade(
    df: pd.DataFrame,
    *,
    direction: str,
    adx_max: float = 25.0,
    ema_period: int = 200,
    vix: Optional[float] = None,
    vix_max: float = 30.0,
) -> bool:
    """Return True iff the regime permits a mean-reversion trade.

    Rules (design §2.4):
      - ADX(14) > adx_max  -> strong trend -> BLOCK (mean reversion fails).
      - VIX > vix_max      -> high vol -> BLOCK.
      - Otherwise (chop / mild trend) -> ALLOW.

    `df` must carry enough history for ADX(14) and EMA. We use the LAST
    row's values only (the decision timestamp), never future bars.

    Note: a full 200EMA check needs >=200 bars; callers with less history
    should pass a smaller ema_period or skip the EMA leg (we only enforce
    ADX + VIX here, which need no 200-bar lookback).
    """
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"direction must be LONG/SHORT, got {direction!r}")
    if df.empty:
        return False

    adx = compute_adx(df, period=14)
    last_adx = adx.iloc[-1]
    if pd.isna(last_adx) or last_adx > adx_max:
        return False

    if vix is not None and vix > vix_max:
        return False

    return True

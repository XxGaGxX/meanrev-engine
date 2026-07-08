"""
Momentum / Breakout Entry Signals — Intraday
=============================================

Level 2 alternative for trending regimes where mean-reversion fails.

Generates long (and optional short) breakout signals based on:

* Price breaks above/below a prior N-bar high/low (Donchian channel).
* ``ADX >= adx_min`` confirms the regime is trending, not ranging —
  the opposite of the mean-reversion ``regime_ok`` filter which
  demands low ADX.
* Optional volume confirmation (``df['vol_confirm']``).

Output schema matches ``signals.entry.generate_entry_signals`` so the
downstream ``signals.exit.simulate_all_trades`` +
``risk.sizing.apply_position_sizing`` pipeline runs unmodified:
``signal_long`` and ``signal_short`` boolean columns on the input
dataframe.

Usage
-----
    from signals.momentum_entry import generate_momentum_entry_signals
    df = generate_momentum_entry_signals(
        df,
        cfg={
            "breakout_lookback": 20,
            "adx_min": 25.0,
            "direction_mode": "long_only",
        },
    )
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

_REQUIRED_COLS = {
    "close", "high", "low",
    "vol_confirm",  # from indicators/volume.add_volume_filter
    "adx",          # from indicators/adx.add_adx
}


def generate_momentum_entry_signals(
    df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Generate long (and optional short) breakout entry signals.

    Required columns in ``df``:
        ``close``, ``high``, ``low``, ``adx``, ``vol_confirm``.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with the required indicator columns.
    cfg : dict, optional
        Configuration overrides:

        - ``breakout_lookback`` (int, default 20): window for the
          Donchian rolling high/low. ``shift(1)`` ensures the trigger
          bar's own high/low is NOT in the reference window.
        - ``adx_min`` (float, default 25.0): minimum ADX at the
          trigger bar — opposite of mean-reversion's low-ADX regime
          filter; momentum is for trending markets.
        - ``use_volume_confirm`` (bool, default True): require
          ``df['vol_confirm']`` to be True at the trigger bar.
        - ``direction_mode`` (str, default ``"long_only"``):
          ``"long_only"`` zeroes out ``signal_short`` so a bullish
          regime backtest only goes long; ``"both"`` also emits
          short-breakout signals on close < prior_low.

    Returns
    -------
    pd.DataFrame
        Copy of ``df`` with added ``signal_long`` / ``signal_short``
        boolean columns. Empty-DataFrame safe: returns a copy with
        the schema columns initialised to ``False``.
    """
    cfg = cfg or {}

    if df.empty:
        df = df.copy()
        df["signal_long"] = pd.Series(False, index=df.index)
        df["signal_short"] = pd.Series(False, index=df.index)
        return df

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"generate_momentum_entry_signals missing required columns: {missing}"
        )

    breakout_lookback = int(cfg.get("breakout_lookback", 20))
    adx_min = float(cfg.get("adx_min", 25.0))
    use_volume = bool(cfg.get("use_volume_confirm", True))
    direction_mode = str(cfg.get("direction_mode", "long_only"))

    df = df.copy()

    # Donchian channel: rolling max/min of the past N bars, excluding
    # the current bar via ``shift(1)``. Without the shift, every bar
    # that touches its own rolling max would self-trigger a flat
    # breakout and dilute the signal pool with high-frequency noise.
    prior_high = df["high"].rolling(breakout_lookback).max().shift(1)
    prior_low = df["low"].rolling(breakout_lookback).min().shift(1)

    long_cond = (
        (df["close"] > prior_high)
        & (df["adx"] >= adx_min)
    )
    if use_volume:
        long_cond = long_cond & df["vol_confirm"]

    if direction_mode not in ("long_only", "both"):
        raise ValueError(
            f"direction_mode must be 'long_only' or 'both', got {direction_mode!r}"
        )

    df["signal_long"] = long_cond.fillna(False).astype(bool)

    if direction_mode == "long_only":
        df["signal_short"] = pd.Series(False, index=df.index)
    else:  # "both"
        short_cond = (
            (df["close"] < prior_low)
            & (df["adx"] >= adx_min)
        )
        if use_volume:
            short_cond = short_cond & df["vol_confirm"]
        df["signal_short"] = short_cond.fillna(False).astype(bool)

    return df


def momentum_signal_counts(df: pd.DataFrame) -> Dict[str, int]:
    """Return the number of momentum long and short signals in the DataFrame."""
    return {
        "long_signals": int(df["signal_long"].sum()),
        "short_signals": int(df["signal_short"].sum()),
        "total_signals": int(df["signal_long"].sum() + df["signal_short"].sum()),
    }

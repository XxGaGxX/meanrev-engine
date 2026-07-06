"""
Exit Simulation Module — Mean Reversion Intraday
=================================================
Level 3 of the strategy: decides WHEN to exit.

Simulates trade exits from an entry point using four rules in priority:
1. Take Profit (TP)    : z-score reverts to ≥0 (long) or ≤0 (short)
2. Stop Loss (SL)      : 1.5× ATR from entry price
3. Time Stop           : forced exit after N bars
4. Regime Stop         : immediate exit if ADX crosses above threshold

Usage:
    from signals.exit import simulate_exit, simulate_all_trades
    trade_log = simulate_all_trades(df)
"""

from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

_REQUIRED_COLS = {
    "open", "high", "low", "close",
    "zscore", "atr", "adx", "regime_ok",
}

ExitResult = Dict[str, Any]


def simulate_exit(
    df: pd.DataFrame,
    entry_idx: int,
    direction: int,  # 1 = long, -1 = short
    atr_multiplier: float = 1.5,
    max_bars: int = 25,
    adx_stop_threshold: float = 25.0,
) -> ExitResult:
    """
    Simulate a single trade from entry to first exit trigger.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with OHLCV + indicator columns.
    entry_idx : int
        Integer position of the entry bar in df.
    direction : int
        1 for long, -1 for short.
    atr_multiplier : float
        Stop-loss distance as multiple of ATR at entry.
    max_bars : int
        Maximum bars to hold the position (time stop).
    adx_stop_threshold : float
        ADX level that triggers regime stop exit.

    Returns
    -------
    dict
        {
            "entry_idx": int,
            "exit_idx": int,
            "entry_price": float,
            "exit_price": float,
            "direction": int,
            "pnl_pct": float,
            "bars_held": int,
            "exit_reason": str,  # "tp", "sl", "time", "regime", "end_of_data"
        }

    Raises
    ------
    ValueError
        If entry_idx is out of bounds or required columns are missing.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"simulate_exit missing required columns: {missing}")

    if entry_idx < 0 or entry_idx >= len(df):
        raise ValueError(f"entry_idx {entry_idx} out of bounds (0-{len(df)-1})")

    if direction not in (1, -1):
        raise ValueError(f"direction must be 1 (long) or -1 (short), got {direction}")

    entry_price = float(df["close"].iloc[entry_idx])
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")

    entry_atr = float(df["atr"].iloc[entry_idx])
    if np.isnan(entry_atr) or entry_atr <= 0:
        raise ValueError(f"entry ATR must be positive and finite, got {entry_atr}")

    # Calculate stop-loss price at entry
    if direction == 1:  # long
        sl_price = entry_price - (entry_atr * atr_multiplier)
    else:  # short
        sl_price = entry_price + (entry_atr * atr_multiplier)

    max_idx = min(entry_idx + max_bars, len(df) - 1)

    for i in range(entry_idx + 1, max_idx + 1):
        bar = df.iloc[i]
        z = bar["zscore"]
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]
        adx = bar["adx"]
        regime_ok = bar["regime_ok"]

        # NaN guard: if OHLC or critical indicators are NaN, exit at last known close
        if pd.isna(close) or pd.isna(high) or pd.isna(low):
            last_valid_close = df["close"].iloc[:i].dropna().iloc[-1] if i > 0 else entry_price
            return _build_result(entry_idx, i, entry_price, last_valid_close, direction, "nan_data")
        if pd.isna(z) or pd.isna(adx):
            return _build_result(entry_idx, i, entry_price, close, direction, "nan_data")

        # 1. Stop Loss: price hits SL level (checked first for conservative simulation)
        if direction == 1 and low <= sl_price:
            return _build_result(entry_idx, i, entry_price, sl_price, direction, "sl")
        if direction == -1 and high >= sl_price:
            return _build_result(entry_idx, i, entry_price, sl_price, direction, "sl")

        # 2. Take Profit: z-score reversion
        if direction == 1 and z >= 0:
            return _build_result(entry_idx, i, entry_price, close, direction, "tp")
        if direction == -1 and z <= 0:
            return _build_result(entry_idx, i, entry_price, close, direction, "tp")

        # 3. Regime Stop: ADX > threshold OR regime breaks
        if adx > adx_stop_threshold or not regime_ok:
            return _build_result(entry_idx, i, entry_price, close, direction, "regime")

    # 4. Time Stop: max bars reached (or end of data)
    final_close = df["close"].iloc[max_idx]
    reason = "time" if max_idx == entry_idx + max_bars else "end_of_data"
    return _build_result(entry_idx, max_idx, entry_price, final_close, direction, reason)


def _build_result(
    entry_idx: int,
    exit_idx: int,
    entry_price: float,
    exit_price: float,
    direction: int,
    reason: str,
) -> ExitResult:
    """Build a consistent exit result dictionary."""
    pnl_pct = direction * (exit_price - entry_price) / entry_price
    return {
        "entry_idx": entry_idx,
        "exit_idx": exit_idx,
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "direction": direction,
        "pnl_pct": float(pnl_pct),
        "bars_held": int(exit_idx - entry_idx),
        "exit_reason": reason,
    }


def simulate_all_trades(
    df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Simulate all trades from entry signals in the DataFrame.

    Long and short signals are evaluated sequentially. Signals that fire
    while a previous trade is still "open" are skipped (no overlapping
    positions on the same asset).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'signal_long', 'signal_short', and all required columns.
    cfg : dict, optional
        Exit configuration overrides (atr_multiplier, max_bars, adx_stop_threshold).

    Returns
    -------
    pd.DataFrame
        Trade log with one row per simulated trade.
    """
    if "signal_long" not in df.columns or "signal_short" not in df.columns:
        raise ValueError(
            "DataFrame must contain 'signal_long' and 'signal_short' columns. "
            "Run generate_entry_signals first."
        )

    cfg = cfg or {}
    atr_multiplier = cfg.get("atr_multiplier", 1.5)
    max_bars = cfg.get("max_bars", 25)
    adx_stop_threshold = cfg.get("adx_stop_threshold", 25.0)

    # Get integer positions directly (much faster than index→position conversion)
    long_positions = np.where(df["signal_long"].values)[0].tolist()
    short_positions = np.where(df["signal_short"].values)[0].tolist()

    # Combine and sort all signals with their direction
    signals: List[Tuple[int, int]] = [(pos, 1) for pos in long_positions] + [(pos, -1) for pos in short_positions]

    signals.sort(key=lambda x: x[0])

    trades: List[ExitResult] = []
    last_exit_pos = -1

    for pos, direction in signals:
        # Skip signals that fire while a previous trade is still open
        if pos <= last_exit_pos:
            continue

        result = simulate_exit(
            df,
            entry_idx=pos,
            direction=direction,
            atr_multiplier=atr_multiplier,
            max_bars=max_bars,
            adx_stop_threshold=adx_stop_threshold,
        )
        trades.append(result)
        last_exit_pos = result["exit_idx"]

    if not trades:
        # Return empty DataFrame with correct columns
        return pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct", "bars_held", "exit_reason",
        ])

    return pd.DataFrame(trades)


def exit_reason_stats(trade_log: pd.DataFrame) -> pd.DataFrame:
    """
    Return the count and percentage of trades by exit reason.
    """
    if trade_log.empty:
        return pd.DataFrame(columns=["count", "pct"])
    counts = trade_log["exit_reason"].value_counts()
    pct = trade_log["exit_reason"].value_counts(normalize=True) * 100
    return pd.concat([counts, pct], axis=1, keys=["count", "pct"])

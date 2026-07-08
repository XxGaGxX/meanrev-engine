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


# Public column schema for the trade log DataFrame produced by
# simulate_all_trades. Other modules (e.g. risk.sizing.build_pct_curve and
# the contract test in tests/test_risk_sizing.py) should import this
# instead of hardcoding the column names — that way the schema can evolve
# in one place.
TRADE_LOG_COLUMNS: tuple = (
    "entry_idx",
    "exit_idx",
    "entry_price",
    "exit_price",
    "direction",
    "pnl_pct",
    "bars_held",
    "exit_reason",
)


def simulate_exit(
    df: pd.DataFrame,
    entry_idx: int,
    direction: int,  # 1 = long, -1 = short
    atr_multiplier: float = 1.5,
    max_bars: int = 25,
    adx_stop_threshold: float = 25.0,
    tp_mode: str = "zscore",
    tp_atr_target: float = 4.0,
    regime_stop: bool = True,
) -> ExitResult:
    """
    Simulate a single trade from entry to first exit trigger.

    Realistic-fill contract (2026-07-07 — closes the look-ahead bias)
    -----------------------------------------------------------------
    The decision bar is ``entry_idx``. The fill bar is ``entry_idx + 1``
    (T+1), because the strategy can only submit an order after the
    close of the signal bar and the broker fills it on the next bar's
    open — not at the trigger price itself.

    1. **Entry fill** = ``df["open"].iloc[entry_idx + 1]``.
       The trigger's close (``df["close"].iloc[entry_idx]``) is no
       longer assumed to be the fill price. This removes the biased
       assumption that we knew the signal-bar close at the moment of
       entry.
    2. **Stop-Loss (SL) gap fill** = when a post-trigger bar opens AT
       OR BEYOND the SL, fill at that bar's OPEN (the SL could not be
       honored because the market gapped through). Marked
       ``exit_reason = "open_gap_sl"``.
    3. **Intra-bar SL** = if the bar's ``low`` (long) or ``high``
       (short) reaches the SL *inside* the bar, fill at SL.
       Marked ``exit_reason = "sl"``.
    4. **Take Profit (TP)** = unchanged. TP is anchored to the
       close-based z-score reversion (computed on
       ``df["close"].iloc[bar]``); TP does not gap-fill because the
       trigger is a computed indicator on close, not a fixed price
       level.
    5. **End-of-data / NaN / regime / time** = same as before.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with OHLCV + indicator columns. MUST include
        ``open`` for the realistic-fill contract.
    entry_idx : int
        Integer position of the SIGNAL bar (T) in df. Fill happens
        at T+1 (``entry_idx + 1``).
    direction : int
        1 for long, -1 for short.
    atr_multiplier : float
        Stop-loss distance as multiple of ATR at the SIGNAL bar (T).
    max_bars : int
        Maximum bars from signal bar to hold the position (time stop).
    adx_stop_threshold : float
        ADX level that triggers regime stop exit.
    tp_mode : str
        Take-profit mode: ``"zscore"`` (default), ``"atr_target"``, or ``"none"``.
    tp_atr_target : float
        ATR multiplier for the ``"atr_target"`` take-profit distance.
    regime_stop : bool
        When ``True`` (default), the regime-stop condition (``adx >
        adx_stop_threshold`` or ``not regime_ok``) is checked at every
        bar. Set ``False`` for momentum strategies where high ADX is
        expected and not a reason to exit.

    Returns
    -------
    dict
        {
            "entry_idx": int,    # signal bar (T)
            "exit_idx": int,     # bar where the trigger fired (>= T+1)
            "entry_price": float,# fill price = T+1 open (the realistic fill)
            "exit_price": float,
            "direction": int,
            "pnl_pct": float,
            "bars_held": int,
            "exit_reason": str,  # "tp", "sl", "open_gap_sl",
                                 # "time", "regime", "end_of_data", "nan_data"
        }

    Raises
    ------
    ValueError
        If ``entry_idx`` is out of bounds, the required columns are
        missing (including ``open``), ``direction`` is not 1/-1, or
        the signal-bar ATR is non-positive / non-finite.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"simulate_exit missing required columns: {missing}")
    if "open" not in df.columns:
        raise ValueError(
            "simulate_exit requires an 'open' column for the realistic-fill "
            "contract (T+1 open entry). Re-add 'open' to the indicator pipeline."
        )

    if entry_idx < 0 or entry_idx >= len(df):
        raise ValueError(f"entry_idx {entry_idx} out of bounds (0-{len(df)-1})")

    if direction not in (1, -1):
        raise ValueError(f"direction must be 1 (long) or -1 (short), got {direction}")

    signal_atr = float(df["atr"].iloc[entry_idx])
    if np.isnan(signal_atr) or signal_atr <= 0:
        raise ValueError(f"entry ATR must be positive and finite, got {signal_atr}")

    # The signal-bar close is reused as a synthetic fill in both
    # early-return paths below (end-of-data and NaN-fill-bar). If
    # the close itself is NaN, the synthetic fill would propagate
    # NaN into the trade log; guard explicitly. (The signal-bar
    # close is not part of the realistic-fill contract — it only
    # feeds the fallback branches, which by construction should
    # never see a "good" close.)
    signal_close = float(df["close"].iloc[entry_idx])
    if pd.isna(signal_close) or signal_close <= 0:
        raise ValueError(
            f"signal-bar close must be positive and finite for "
            f"fallback-fill, got {signal_close}"
        )
    if entry_idx + 1 >= len(df):
        return _build_result(
            entry_idx, len(df) - 1, signal_close, signal_close, direction, "end_of_data"
        )

    fill_bar_idx = entry_idx + 1
    fill_open = df["open"].iloc[fill_bar_idx]
    if pd.isna(fill_open) or float(fill_open) <= 0:
        # Corrupted T+1 bar — NaN guard path.
        last_valid_close = (
            df["close"].iloc[:fill_bar_idx].dropna().iloc[-1]
            if fill_bar_idx > 0 else signal_close
        )
        return _build_result(
            entry_idx, fill_bar_idx, signal_close, last_valid_close, direction, "nan_data"
        )
    entry_price = float(fill_open)

    # SL price is computed from the realistic fill (T+1 open) and the
    # signal-bar ATR — not from the signal bar's close. A corporation
    # bar that opens THROUGH the planned SL on the fill bar itself
    # (T+1 open already beyond SL) will gap-fill on i = entry_idx+1
    # with exit_reason="open_gap_sl".
    if direction == 1:
        sl_price = entry_price - (signal_atr * atr_multiplier)
    else:
        sl_price = entry_price + (signal_atr * atr_multiplier)

    max_idx = min(entry_idx + max_bars, len(df) - 1)

    for i in range(entry_idx + 1, max_idx + 1):
        bar = df.iloc[i]
        z = bar["zscore"]
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]
        opn = bar["open"]
        adx = bar["adx"]
        regime_ok = bar["regime_ok"]

        # NaN guard — exit at last known close, same as pre-fix.
        if pd.isna(close) or pd.isna(high) or pd.isna(low):
            last_valid_close = (
                df["close"].iloc[:i].dropna().iloc[-1] if i > 0 else entry_price
            )
            return _build_result(
                entry_idx, i, entry_price, last_valid_close, direction, "nan_data"
            )
        if pd.isna(z) or pd.isna(adx) or pd.isna(opn):
            return _build_result(
                entry_idx, i, entry_price, close, direction, "nan_data"
            )

        # 1. SL gap fill: bar opened at or beyond the planned SL — the
        #    broker's auction does not let us stop out at the stated
        #    price. Fill at open (worse than SL).
        if direction == 1 and opn <= sl_price:
            return _build_result(
                entry_idx, i, entry_price, float(opn), direction, "open_gap_sl"
            )
        if direction == -1 and opn >= sl_price:
            return _build_result(
                entry_idx, i, entry_price, float(opn), direction, "open_gap_sl"
            )

        # 2. Intra-bar SL: bar reached the planned SL inside the
        #    OHLC range. Fill at SL price.
        if direction == 1 and low <= sl_price:
            return _build_result(
                entry_idx, i, entry_price, sl_price, direction, "sl"
            )
        if direction == -1 and high >= sl_price:
            return _build_result(
                entry_idx, i, entry_price, sl_price, direction, "sl"
            )

        # 3. Take Profit: mode-dependent.
        # - tp_mode="zscore" (default): mean-reversion TP — the original
        #   zscore revert to 0 behavior. Suitable only for mean-reversion.
        # - tp_mode="atr_target": fixed profit target at +N*ATR from entry.
        #   The trigger price is the entry price + signal_atr * tp_atr_target
        #   for longs (- that for shorts). The intra-bar check is matched on
        #   bar.high/low so we fill at the target price (no gap-fill).
        # - tp_mode="none": no TP; let winners run until SL/time/regime exits.
        if tp_mode == "zscore":
            if direction == 1 and z >= 0:
                return _build_result(
                    entry_idx, i, entry_price, close, direction, "tp"
                )
            if direction == -1 and z <= 0:
                return _build_result(
                    entry_idx, i, entry_price, close, direction, "tp"
                )
        elif tp_mode == "atr_target":
            target_distance = signal_atr * tp_atr_target
            target_price = (
                entry_price + target_distance
                if direction == 1
                else entry_price - target_distance
            )
            if direction == 1 and high >= target_price:
                return _build_result(
                    entry_idx, i, entry_price, target_price, direction, "tp"
                )
            if direction == -1 and low <= target_price:
                return _build_result(
                    entry_idx, i, entry_price, target_price, direction, "tp"
                )
        # tp_mode == "none": no TP trigger; relies on SL/time/regime only.

        # 4. Regime Stop: ADX > threshold or regime breaks mid-trade.
        #    When ``regime_stop=False`` (e.g. momentum strategies), this
        #    block is bypassed entirely — winners run until SL / time / TP.
        if regime_stop and (adx > adx_stop_threshold or not regime_ok):
            return _build_result(
                entry_idx, i, entry_price, close, direction, "regime"
            )

    # 5. Time / end-of-data — unchanged. Note: ``max_idx`` may be <
    #    ``entry_idx + max_bars`` when the dataset ends earlier; in that
    #    case the reason flips to "end_of_data".
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
    tp_mode = cfg.get("tp_mode", "zscore")
    tp_atr_target = cfg.get("tp_atr_target", 4.0)
    if tp_mode not in ("zscore", "atr_target", "none"):
        raise ValueError(
            f"tp_mode must be 'zscore', 'atr_target', or 'none', got {tp_mode!r}"
        )
    if tp_mode == "atr_target" and tp_atr_target <= 0:
        raise ValueError(
            f"tp_atr_target must be > 0 for tp_mode='atr_target', "
            f"got {tp_atr_target!r}"
        )
    regime_stop = bool(cfg.get("regime_stop", True))

    # Get integer positions directly (much faster than index→position conversion)
    long_positions = np.where(df["signal_long"].values)[0].tolist()
    short_positions = np.where(df["signal_short"].values)[0].tolist()

    # Combine and sort all signals with their direction
    signals: List[Tuple[int, int]] = [(pos, 1) for pos in long_positions] + [(pos, -1) for pos in short_positions]

    signals.sort(key=lambda x: x[0])

    trades: List[ExitResult] = []
    last_exit_pos = -1
    total_signals = len(signals)
    skipped = 0

    for pos, direction in signals:
        # Skip signals that fire while a previous trade is still open
        if pos <= last_exit_pos:
            skipped += 1
            continue

        result = simulate_exit(
            df,
            entry_idx=pos,
            direction=direction,
            atr_multiplier=atr_multiplier,
            max_bars=max_bars,
            adx_stop_threshold=adx_stop_threshold,
            tp_mode=tp_mode,
            tp_atr_target=tp_atr_target,
            regime_stop=regime_stop,
        )
        trades.append(result)
        last_exit_pos = result["exit_idx"]

    if not trades:
        # Return empty DataFrame with correct columns
        result_df = pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct", "bars_held", "exit_reason",
        ])
        result_df.attrs["signals_total"] = total_signals
        result_df.attrs["signals_skipped"] = skipped
        result_df.attrs["signals_executed"] = total_signals - skipped
        return result_df

    result_df = pd.DataFrame(trades)
    result_df.attrs["signals_total"] = total_signals
    result_df.attrs["signals_skipped"] = skipped
    result_df.attrs["signals_executed"] = total_signals - skipped
    return result_df


def exit_reason_stats(trade_log: pd.DataFrame) -> pd.DataFrame:
    """
    Return the count and percentage of trades by exit reason.
    """
    if trade_log.empty:
        return pd.DataFrame(columns=["count", "pct"])
    counts = trade_log["exit_reason"].value_counts()
    pct = trade_log["exit_reason"].value_counts(normalize=True) * 100
    return pd.concat([counts, pct], axis=1, keys=["count", "pct"])

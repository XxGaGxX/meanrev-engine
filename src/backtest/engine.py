"""Phase 5 — Backtest trade simulator (pure, event-free per-bar scan).

Single responsibility: given a PositionPlan and the bars AFTER entry
(chronological, no look-ahead), decide the exit and its price. The
caller (scripts/backtest_proxy.py) feeds ONLY post-entry bars; this
module never sees the entry bar's own close.

Exit priority per bar (first match wins):
  1. partial TP (tp_partial_price) -> take partial_tp_frac out
  2. full TP (tp_price)            -> remaining closes at tp
  3. SL (sl_price)                 -> full stop
  4. time_stop_bars reached        -> exit at this bar's close
  5. end of bars                   -> forced EOD exit at last close

All thresholds are STRICT (>= / <= would fire on a touch).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

import pandas as pd

from src.strategy.risk import PositionPlan, Direction


class ExitReason(str, Enum):
    TP_FULL = "TP_FULL"
    TP_PARTIAL = "TP_PARTIAL"
    SL = "SL"
    TIME_STOP = "TIME_STOP"
    EOD = "EOD"


@dataclass(frozen=True)
class TradeResult:
    pnl: float              # per-share P&L (signed)
    exit_reason: ExitReason
    exit_price: float
    bars_held: int
    entry_bar_index: int = -1   # bar index where the position was filled
    signal_bar_index: int = -1  # bar index where the signal fired (MUST be < entry)


def _exit_price_for_partial(plan: PositionPlan) -> float:
    """Effective exit price when partial TP is used then remainder at TP.

    half at tp_partial_price, half at tp_price (size-weighted avg).
    """
    frac = plan.partial_tp_frac
    if frac <= 0 or plan.tp_partial_price is None:
        return plan.tp_price
    return frac * plan.tp_partial_price + (1.0 - frac) * plan.tp_price


def simulate_trade(
    plan: PositionPlan,
    bars_after: pd.DataFrame,
    entry_bar_index: int = -1,
    signal_bar_index: int = -1,
) -> TradeResult:
    """Simulate one trade from entry to exit.

    Args:
        plan: PositionPlan from src.strategy.risk.compute_position.
        bars_after: DataFrame with a 'close' column, bars strictly AFTER
            entry, chronological. The first row is the bar right after
            the entry fill.
        entry_bar_index: index of the bar where the position was filled
            (signal_bar_index + 1). Used for the anti-look-ahead gate.
        signal_bar_index: index of the bar where the signal fired.
            MUST be strictly less than entry_bar_index.

    Returns:
        TradeResult with signed per-share P&L and exit reason.

    Raises:
        ValueError: entry_bar_index <= signal_bar_index (look-ahead).
    """
    if entry_bar_index >= 0 and signal_bar_index >= 0:
        if entry_bar_index <= signal_bar_index:
            raise ValueError(
                f"entry_bar_index ({entry_bar_index}) must be > "
                f"signal_bar_index ({signal_bar_index}) — look-ahead gate"
            )
    if "close" not in bars_after.columns:
        raise ValueError("bars_after must have a 'close' column")
    closes = bars_after["close"].to_numpy(dtype=float)
    n = len(closes)
    if n == 0:
        # No bars after entry -> cannot simulate; treat as EOD at entry.
        return TradeResult(0.0, ExitReason.EOD, plan.entry_price, 0,
                           entry_bar_index, signal_bar_index)

    is_long = plan.direction is Direction.LONG
    time_stop = plan.time_stop_bars
    partial_hit = False  # becomes True once price touches tp_partial_price

    for i in range(n):
        c = float(closes[i])
        # partial TP (only relevant if frac > 0)
        if plan.partial_tp_frac > 0 and plan.tp_partial_price is not None:
            hit_partial = c >= plan.tp_partial_price if is_long else c <= plan.tp_partial_price
            if hit_partial:
                partial_hit = True
        # full TP
        hit_tp = c >= plan.tp_price if is_long else c <= plan.tp_price
        # SL
        hit_sl = c <= plan.sl_price if is_long else c >= plan.sl_price

        if hit_tp:
            exit_px = _exit_price_for_partial(plan) if partial_hit else plan.tp_price
            return TradeResult(_pnl(plan, exit_px), ExitReason.TP_FULL, exit_px, i + 1,
                               entry_bar_index, signal_bar_index)
        if hit_sl:
            return TradeResult(
                _pnl(plan, plan.sl_price),
                ExitReason.SL,
                plan.sl_price,
                i + 1,
                entry_bar_index,
                signal_bar_index,
            )
        if time_stop is not None and (i + 1) >= time_stop:
            return TradeResult(_pnl(plan, c), ExitReason.TIME_STOP, c, i + 1,
                               entry_bar_index, signal_bar_index)

    # Reached end of bars without TP/SL/time-stop -> forced EOD exit.
    last = float(closes[-1])
    return TradeResult(
        _pnl(plan, last),
        ExitReason.EOD,
        last,
        n,
        entry_bar_index,
        signal_bar_index,
    )


def _pnl(plan: PositionPlan, exit_price: float) -> float:
    if plan.direction is Direction.LONG:
        return exit_price - plan.entry_price
    return plan.entry_price - exit_price

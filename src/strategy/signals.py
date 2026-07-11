"""Phase 3 — Signal Generator (pure, state-free entry-signal logic).

Single responsibility: turn one day of 5-min OHLCV bars + yesterday's
close into a LONG / SHORT / FLAT entry signal, with the confirmation
bar index so the backtest can fill at the NEXT bar's open (anti
look-ahead).

Design contract (docs/superpowers/plans/ROADMAP_MVP.md Phase 3, design
§3.2):

  gap = (open_first_bar - prev_close) / prev_close          (signed)
  |gap| outside [gap_min_pct, gap_max_pct] -> FLAT
  DOWN gap (negative) -> LONG  candidate
  UP   gap (positive) -> SHORT candidate
  Opening Range = max(high) / min(low) over the first `opening_range_bars`
  LONG  confirmed when `confirmation_bars` consecutive CLOSEs break
        ABOVE  opening_range_high
  SHORT confirmed when `confirmation_bars` consecutive CLOSEs break
        BELOW  opening_range_low
  scan runs over bars [opening_range_bars .. (end | deadline)]
  No confirmation -> FLAT, bar_index = None

No hidden state, no network, no disk. All parameters come from the
caller (wired to config/settings.yaml by the orchestrator in Phase 5) —
never hardcoded.

Look-ahead policy: the function only ever reads bars <= the confirmation
bar. `bar_index` is the bar where confirmation closes; the consumer must
fill at the FOLLOWING bar. `test_signal_does_not_peek_into_future`
locks this invariant.

Contract for downstream phases:
  - Phase 4 (risk) MUST define the protective stop. With entry at the OR
    breakout and TP at prev_close, the price-based R:R is structurally
    < 1 (stop below OR-low is wider than the target). A time-stop and/or
    partial-TP is REQUIRED to make the trade economics viable. This module
    emits only the entry direction; it is not responsible for R:R.
  - Phase 5 (backtest) MUST apply the VIX / news / regime filters BEFORE
    calling this function, otherwise emitted signals violate the strategy
    definition in docs/strategic-foundation-mean-reversion.md.
  - The breakout test is STRICT (`close > or_high` / `close < or_low`): a
    close exactly on the OR boundary does NOT confirm.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class Signal(str, Enum):
    """Entry action. String-valued so it serializes cleanly to logs/CSV."""

    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass(frozen=True)
class EntrySignal:
    """Outcome of generate_entry_signal.

    action:    what the strategy wants to do at the bar AFTER bar_index.
    bar_index: 0-based index of the bar where confirmation CLOSED, or None
               for FLAT. The backtest enters at bar bar_index + 1 (open) to
               avoid look-ahead.
    gap_pct:   signed gap that triggered candidacy (0.0 if FLAT/invalid).
    direction: "DOWN" (-> LONG) / "UP" (-> SHORT) / None for FLAT.
    """

    action: Signal
    bar_index: Optional[int]
    gap_pct: float = 0.0
    direction: Optional[str] = None
    prev_close: float = 0.0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EntrySignal):
            return NotImplemented
        return (
            self.action is other.action
            and self.bar_index == other.bar_index
            and self.gap_pct == other.gap_pct
            and self.direction == other.direction
        )


# Sensible defaults mirror settings.yaml so the function is callable
# without plumbing the full config during ad-hoc use / unit tests.
_DEFAULT_GAP_MIN = 0.003
_DEFAULT_GAP_MAX = 0.02
_DEFAULT_OR_BARS = 3
_DEFAULT_CONF_BARS = 2


def generate_entry_signal(
    day_bars: pd.DataFrame,
    *,
    prev_close: float,
    gap_min_pct: float = _DEFAULT_GAP_MIN,
    gap_max_pct: float = _DEFAULT_GAP_MAX,
    opening_range_bars: int = _DEFAULT_OR_BARS,
    confirmation_bars: int = _DEFAULT_CONF_BARS,
    confirm_deadline_index: Optional[int] = None,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> EntrySignal:
    """Emit a LONG/SHORT/FLAT entry signal for a single trading day.

    Args:
        day_bars: DataFrame of 5-min bars for one day, chronological
            (index 0 = first bar after 09:30 open). Must contain OHLC.
        prev_close: official prior-session close (the "mean" to revert to).
        gap_min_pct / gap_max_pct: operating window half-widths.
        opening_range_bars: number of leading bars defining the OR.
        confirmation_bars: consecutive closes needed to confirm a breakout.
        confirm_deadline_index: optional exclusive upper bound on the scan
            (e.g. map "no trade after 11:00" to a bar index). None = scan
            to the end of the day.
        *_col: column names for OHLC.

    Returns:
        EntrySignal. For FLAT, bar_index is None.

    Raises:
        ValueError: if prev_close <= 0, or if there are too few bars to
            even form the opening range.
    """
    if prev_close <= 0:
        raise ValueError(f"prev_close must be positive, got {prev_close!r}")
    if close_col not in day_bars.columns:
        raise ValueError(f"missing '{close_col}' column in day_bars")
    for col in (open_col, high_col, low_col, close_col):
        if col not in day_bars.columns:
            raise ValueError(f"missing '{col}' column in day_bars")

    n = len(day_bars)
    if n < opening_range_bars:
        # Not enough bars to define an opening range -> cannot trade.
        return EntrySignal(Signal.FLAT, None)

    # Defensive ordering: the function assumes chronological order by
    # position (index 0 = first bar after 09:30). If a time column exists
    # (datetime-like, or named 'bar'/'index'), sort on it so shuffled
    # input is restored to chronological order. If no such column is
    # present we trust the caller's positional order after a clean reindex.
    _ordered = day_bars.reset_index(drop=True)
    _time_col = None
    for cand in ("datetime", "timestamp", "time", "bar_time", "date"):
        if cand in _ordered.columns:
            _time_col = cand
            break
    else:
        # pandas DatetimeIndex under a reset name (e.g. 'index')
        if isinstance(_ordered.index, pd.DatetimeIndex):
            _time_col = _ordered.index.name or "index"
    if _time_col is not None:
        _ordered = _ordered.sort_values(_time_col).reset_index(drop=True)
    day_bars = _ordered

    # --- Gap computation (uses ONLY the first bar's open; no future data) ---
    first_open = float(day_bars.iloc[0][open_col])
    gap_pct = (first_open - prev_close) / prev_close

    if not (gap_min_pct <= abs(gap_pct) <= gap_max_pct):
        return EntrySignal(Signal.FLAT, None, gap_pct=gap_pct)

    is_down_gap = gap_pct < 0.0  # DOWN -> LONG candidate

    # --- Opening range from the first `opening_range_bars` bars ---
    or_slice = day_bars.iloc[:opening_range_bars]
    or_high = float(or_slice[high_col].max())
    or_low = float(or_slice[low_col].min())

    # --- Scan for consecutive close breakouts ---
    scan_end = n
    if confirm_deadline_index is not None:
        scan_end = min(scan_end, int(confirm_deadline_index))
    if scan_end <= opening_range_bars:
        # Deadline before the OR finishes -> no room to confirm.
        return EntrySignal(
            Signal.FLAT, None, gap_pct=gap_pct,
            direction="DOWN" if is_down_gap else "UP", prev_close=prev_close,
        )

    closes = day_bars[close_col].to_numpy(dtype=float)
    run = 0
    confirm_idx: Optional[int] = None

    for i in range(opening_range_bars, scan_end):
        c = closes[i]
        if is_down_gap:
            # LONG: close must break ABOVE OR high
            hit = c > or_high
        else:
            # SHORT: close must break BELOW OR low
            hit = c < or_low
        run = run + 1 if hit else 0
        if run >= confirmation_bars:
            confirm_idx = i
            break

    if confirm_idx is None:
        return EntrySignal(
            Signal.FLAT, None, gap_pct=gap_pct,
            direction="DOWN" if is_down_gap else "UP", prev_close=prev_close,
        )

    action = Signal.LONG if is_down_gap else Signal.SHORT
    return EntrySignal(
        action,
        confirm_idx,
        gap_pct=gap_pct,
        direction="DOWN" if is_down_gap else "UP",
        prev_close=prev_close,
    )

"""Tests for Phase 3 Signal Generator — pure entry-signal function.

TDD discipline: written BEFORE src/strategy/signals.py. They must FAIL
(RED) until the module exists and implements the contract below.

Contract (docs/superpowers/plans/ROADMAP_MVP.md, Phase 3 + design §3.2):
  - gap = (open_first_bar - prev_close) / prev_close  (signed)
  - |gap| outside [gap_min_pct, gap_max_pct] -> FLAT (no trade)
  - DOWN gap (negative) -> LONG candidate
  - UP   gap (positive) -> SHORT candidate
  - Opening Range = max(high)/min(low) over first `opening_range_bars`
  - LONG confirmed when `confirmation_bars` consecutive 5-min CLOSEs break
    ABOVE opening_range_high
  - SHORT confirmed when `confirmation_bars` consecutive CLOSEs break
    BELOW opening_range_low
  - No confirmation by end of scan (or deadline) -> FLAT
  - bar_index = the bar where confirmation CLOSES. The backtest must fill
    at the NEXT bar's open (anti-look-ahead); the signal itself uses no
    future information.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.strategy.signals import (
    EntrySignal,
    Signal,
    generate_entry_signal,
)
from src.config import load_settings, SETTINGS_PATH


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _bar(o, h, l, c) -> dict:
    return {"open": o, "high": h, "low": l, "close": c}


def _day_bars(rows: list) -> pd.DataFrame:
    return pd.DataFrame(rows)


# Scenario: DOWN gap -1% (open 99 vs prev_close 100).
# OR (first 3 bars): high 99.1, low 98.7
_DOWN_OR = [
    _bar(99.0, 99.1, 98.9, 99.0),
    _bar(99.0, 99.1, 98.8, 98.9),
    _bar(98.9, 99.0, 98.7, 98.8),
]


# ---------------------------------------------------------------------------
# Direction / gap filtering
# ---------------------------------------------------------------------------


def test_flat_when_gap_too_small() -> None:
    # open 99.8 -> gap -0.2% (< 0.3% floor) -> FLAT
    bars = _day_bars([
        _bar(99.8, 99.9, 99.7, 99.8),
        _bar(99.8, 99.9, 99.7, 99.7),
        _bar(99.7, 99.8, 99.6, 99.7),
        _bar(99.7, 99.9, 99.6, 99.8),
        _bar(99.8, 99.9, 99.7, 99.8),
    ])
    sig = generate_entry_signal(bars, prev_close=100.0)
    assert sig.action is Signal.FLAT
    assert sig.bar_index is None


def test_flat_when_gap_too_big() -> None:
    # open 97 -> gap -3% (> 2% ceiling) -> FLAT
    bars = _day_bars([
        _bar(97.0, 97.1, 96.9, 97.0),
        _bar(97.0, 97.1, 96.8, 96.9),
        _bar(96.9, 97.0, 96.7, 96.8),
        _bar(96.8, 97.0, 96.6, 96.9),
        _bar(96.9, 97.1, 96.8, 97.0),
    ])
    sig = generate_entry_signal(bars, prev_close=100.0)
    assert sig.action is Signal.FLAT
    assert sig.bar_index is None


def test_flat_when_no_confirmation() -> None:
    # DOWN gap in range, but price never breaks OR_high -> FLAT
    bars = _day_bars(_DOWN_OR + [
        _bar(98.8, 99.0, 98.6, 98.9),   # close 98.9 <= OR_high 99.1
        _bar(98.9, 99.0, 98.5, 98.7),
        _bar(98.7, 98.9, 98.4, 98.6),
    ])
    sig = generate_entry_signal(bars, prev_close=100.0)
    assert sig.action is Signal.FLAT
    assert sig.bar_index is None


# ---------------------------------------------------------------------------
# Confirmation -> signal
# ---------------------------------------------------------------------------


def test_long_on_down_gap_breakout() -> None:
    # DOWN gap -1%; OR high 99.1. Bars 3,4 close > 99.1 -> LONG at idx 4.
    bars = _day_bars(_DOWN_OR + [
        _bar(98.8, 99.3, 98.8, 99.2),   # idx3 close 99.2 > 99.1
        _bar(99.2, 99.5, 99.1, 99.4),   # idx4 close 99.4 > 99.1 -> confirm
    ])
    sig = generate_entry_signal(bars, prev_close=100.0)
    assert sig.action is Signal.LONG
    assert sig.bar_index == 4


def test_short_on_up_gap_breakdown() -> None:
    # UP gap +1% (open 101). OR low 100.8. Bars 4,5 close < 100.8 -> SHORT idx5.
    bars = _day_bars([
        _bar(101.0, 101.2, 100.9, 101.0),   # OR1
        _bar(101.0, 101.3, 100.9, 101.1),   # OR2
        _bar(101.1, 101.3, 100.8, 101.0),   # OR3 -> low 100.8
        _bar(101.0, 101.0, 100.7, 100.8),   # idx3 close 100.8 == low (not <)
        _bar(100.8, 100.8, 100.5, 100.6),   # idx4 close 100.6 < 100.8 -> run 1
        _bar(100.6, 100.6, 100.3, 100.2),   # idx5 close 100.2 < 100.8 -> run 2
    ])
    sig = generate_entry_signal(bars, prev_close=100.0)
    assert sig.action is Signal.SHORT
    assert sig.bar_index == 5


def test_no_signal_when_confirmation_not_consecutive() -> None:
    # DOWN gap; bar3 > OR_high, bar4 <= , bar5 > again -> never 2 in a row.
    bars = _day_bars(_DOWN_OR + [
        _bar(98.8, 99.3, 98.8, 99.2),   # idx3 close 99.2 > 99.1 (run 1)
        _bar(99.2, 99.3, 98.9, 99.0),   # idx4 close 99.0 <= 99.1 (reset)
        _bar(99.0, 99.4, 98.9, 99.3),   # idx5 close 99.3 > 99.1 (run 1 only)
    ])
    sig = generate_entry_signal(bars, prev_close=100.0)
    assert sig.action is Signal.FLAT
    assert sig.bar_index is None


def test_deadline_caps_confirmation_scan() -> None:
    # Same as long scenario (confirm at idx4) but deadline=3 -> scan empty -> FLAT.
    bars = _day_bars(_DOWN_OR + [
        _bar(98.8, 99.3, 98.8, 99.2),
        _bar(99.2, 99.5, 99.1, 99.4),
    ])
    sig = generate_entry_signal(
        bars, prev_close=100.0, confirm_deadline_index=3
    )
    assert sig.action is Signal.FLAT
    assert sig.bar_index is None


# ---------------------------------------------------------------------------
# Anti-look-ahead invariant (quant-critical)
# ---------------------------------------------------------------------------


def test_signal_does_not_peek_into_future() -> None:
    """Cut the day at the confirmation bar: prefix [0..bar_index] must give
    the SAME signal/bar_index, and any strict prefix must be FLAT. This
    proves the function never consumes bars after the entry bar."""
    bars = _day_bars(_DOWN_OR + [
        _bar(98.8, 99.3, 98.8, 99.2),
        _bar(99.2, 99.5, 99.1, 99.4),
        _bar(99.4, 99.6, 99.3, 99.5),   # extra future bar (must NOT affect idx4)
    ])
    full = generate_entry_signal(bars, prev_close=100.0)
    assert full.action is Signal.LONG and full.bar_index == 4

    # Prefix up to and including the confirmation bar.
    prefix = generate_entry_signal(bars.iloc[:5], prev_close=100.0)
    assert prefix == full

    # Strict prefix before confirmation must be FLAT (no peeking).
    early = generate_entry_signal(bars.iloc[:4], prev_close=100.0)
    assert early.action is Signal.FLAT


# ---------------------------------------------------------------------------
# No hardcoding — params flow from settings.yaml (Fase 3 gate)
# ---------------------------------------------------------------------------


def test_params_come_from_settings_not_hardcoded() -> None:
    """Prove parameters flow from settings.yaml, not literals: the SAME
    bars that yield LONG under the real gap_min_pct become FLAT if we pass
    a TIGHTER gap_min_pct. This is a behavioural check (no floating-point
    boundary dependence) that the function is parameter-driven."""
    s = load_settings(SETTINGS_PATH)
    st = s.strategy

    # open 99.5 vs prev 100 -> gap -0.005 (clearly inside the 0.3% window).
    bars = _day_bars([
        _bar(99.5, 99.8, 99.4, 99.5),
        _bar(99.5, 99.8, 99.3, 99.4),
        _bar(99.4, 99.7, 99.2, 99.3),
        _bar(99.3, 99.95, 99.3, 99.85),   # close 99.85 > OR high 99.8
        _bar(99.85, 99.95, 99.75, 99.9),  # close 99.9  > OR high 99.8
    ])

    with_settings = generate_entry_signal(
        bars,
        prev_close=100.0,
        gap_min_pct=st.gap_min_pct,   # 0.003
        gap_max_pct=st.gap_max_pct,
        opening_range_bars=st.opening_range_bars,
        confirmation_bars=st.confirmation_bars,
    )
    assert with_settings.action is Signal.LONG
    assert st.gap_min_pct == 0.003

    # Tighten the floor to 0.6% (0.006): the -0.005 gap is now OUT of range
    # and the function must return FLAT — proving the param, not a literal,
    # gates the trade.
    tightened = generate_entry_signal(
        bars,
        prev_close=100.0,
        gap_min_pct=0.006,
        gap_max_pct=st.gap_max_pct,
        opening_range_bars=st.opening_range_bars,
        confirmation_bars=st.confirmation_bars,
    )
    assert tightened.action is Signal.FLAT


def test_invalid_prev_close_raises() -> None:
    bars = _day_bars(_DOWN_OR)
    with pytest.raises(ValueError):
        generate_entry_signal(bars, prev_close=0.0)


def test_too_few_bars_returns_flat() -> None:
    bars = _day_bars([_bar(99.0, 99.1, 98.9, 99.0)])
    sig = generate_entry_signal(bars, prev_close=100.0)
    assert sig.action is Signal.FLAT
    assert sig.bar_index is None

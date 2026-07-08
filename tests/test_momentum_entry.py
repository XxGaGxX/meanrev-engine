"""
Tests for signals.momentum_entry (Donchian breakout / momentum entry).

Verifies the entry signal logic across:

* Long breakouts (close > prior N-bar high) with ADX filter and vol confirm
* Short breakouts (close < prior N-bar low) under direction_mode="both"
* Direction locking (long_only zeroing signal_short)
* Validation (missing columns, invalid direction_mode, empty df)
* Momentum signal_counts helper
"""
import numpy as np
import pandas as pd
import pytest

from signals.momentum_entry import (
    generate_momentum_entry_signals,
    momentum_signal_counts,
)


@pytest.fixture
def base_df():
    """50 bars synthetic 15-min OHLCV with the indicator columns momentum
    requires plus the mean-reversion columns it doesn't use (so the
    downstream pipeline can run unchanged)."""
    n = 50
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = np.full(n, 100.0, dtype=float)
    high = np.full(n, 100.0, dtype=float)
    low = np.full(n, 100.0, dtype=float)
    volume = np.full(n, 1000.0, dtype=float)

    # Insert a clear long breakout at bar 25 (close=101 vs prior 20-bar max=100)
    close[25] = 101.0
    high[25] = 101.5

    df = pd.DataFrame({
        "open": close,
        "close": close,
        "high": high,
        "low": low,
        "volume": volume,
        # Momentum-required columns:
        "adx": np.full(n, 30.0, dtype=float),  # >= 25 threshold
        "vol_confirm": np.full(n, True, dtype=bool),
        # Mean-reversion columns (unused but present):
        "rsi": np.full(n, 60.0, dtype=float),
        "bb_upper": np.full(n, 102.0, dtype=float),
        "bb_lower": np.full(n, 98.0, dtype=float),
        "zscore": np.full(n, 0.5, dtype=float),
        "regime_ok": np.full(n, True, dtype=bool),
    }, index=idx)
    return df


def test_long_breakout_fires_on_close_above_20_bar_high(base_df):
    """Bar 25 close=101, prior_high=100 (rolling 20-bar max excluding self)."""
    out = generate_momentum_entry_signals(base_df)
    assert bool(out["signal_long"].iloc[25])


def test_no_signal_when_adx_below_threshold(base_df):
    """ADX=20 is below the default 25 threshold; breakout is suppressed."""
    base_df["adx"] = 20.0
    out = generate_momentum_entry_signals(base_df)
    assert not out["signal_long"].iloc[25]


def test_long_only_mode_zeros_signal_short(base_df):
    """default direction_mode='long_only' → signal_short column all False."""
    out = generate_momentum_entry_signals(base_df)
    assert out["signal_short"].sum() == 0


def test_both_mode_emits_short_breakout(base_df):
    """Reshape bar 25 to a short breakout (close<100, low<100) and enable both."""
    idx25 = base_df.index[25]
    base_df.loc[idx25, "close"] = 99.0
    base_df.loc[idx25, "low"] = 98.5
    base_df.loc[idx25, "high"] = 100.0  # ensure long doesn't also fire
    out = generate_momentum_entry_signals(base_df, cfg={"direction_mode": "both"})
    assert bool(out["signal_short"].loc[idx25])
    assert not out["signal_long"].loc[idx25]


def test_volume_confirm_filters_when_enabled(base_df):
    """With use_volume_confirm=True and vol_confirm=False, breakouts are filtered out."""
    base_df["vol_confirm"] = False
    out_strict = generate_momentum_entry_signals(base_df, cfg={"use_volume_confirm": True})
    out_relaxed = generate_momentum_entry_signals(base_df, cfg={"use_volume_confirm": False})
    assert not out_strict["signal_long"].iloc[25]
    assert bool(out_relaxed["signal_long"].iloc[25])


def test_invalid_direction_mode_raises(base_df):
    """Unknown direction_mode values raise ValueError with helpful message."""
    with pytest.raises(ValueError, match="direction_mode"):
        generate_momentum_entry_signals(base_df, cfg={"direction_mode": "sideways"})


def test_missing_columns_raises():
    """Bare df without required columns raises ValueError."""
    df = pd.DataFrame({"close": [100.0]})
    with pytest.raises(ValueError, match="missing"):
        generate_momentum_entry_signals(df)


def test_empty_df_returns_false_signals():
    """Empty df returns a copy with signal_long / signal_short initialized to False."""
    df = pd.DataFrame(columns=["close", "high", "low", "adx", "vol_confirm", "open", "volume"])
    out = generate_momentum_entry_signals(df)
    assert len(out) == 0
    assert "signal_long" in out.columns
    assert "signal_short" in out.columns
    assert out["signal_long"].dtype == bool
    assert out["signal_short"].dtype == bool


def test_no_breakout_on_flat_prices():
    """A totally flat price series (close=high=low=100) produces zero signals."""
    n = 50
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    df = pd.DataFrame({
        "open": np.full(n, 100.0), "close": np.full(n, 100.0),
        "high": np.full(n, 100.0), "low": np.full(n, 100.0),
        "volume": np.full(n, 1000.0), "adx": np.full(n, 30.0),
        "vol_confirm": np.full(n, True), "rsi": np.full(n, 60.0),
        "bb_upper": np.full(n, 102.0), "bb_lower": np.full(n, 98.0),
        "zscore": np.full(n, 0.5), "regime_ok": np.full(n, True),
    }, index=idx)
    out = generate_momentum_entry_signals(df)
    assert out["signal_long"].sum() == 0
    assert out["signal_short"].sum() == 0


def test_momentum_signal_counts_helper(base_df):
    """momentum_signal_counts returns correct total / long / short counts."""
    out = generate_momentum_entry_signals(base_df)
    counts = momentum_signal_counts(out)
    assert counts["long_signals"] == 1
    assert counts["short_signals"] == 0  # direction_mode="long_only"
    assert counts["total_signals"] == counts["long_signals"] + counts["short_signals"]

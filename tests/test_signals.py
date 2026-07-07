"""
Tests for signals/entry.py and signals/exit.py
"""

import numpy as np
import pandas as pd
import pytest

from signals.entry import generate_entry_signals, signal_counts, validate_signal_count
from signals.exit import simulate_exit, simulate_all_trades, exit_reason_stats


def _make_df(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame with all indicator columns."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    df = pd.DataFrame(index=idx)
    df["open"] = 100 + rng.standard_normal(n).cumsum() * 0.5
    df["high"] = df["open"] + rng.uniform(0, 1, n)
    df["low"] = df["open"] - rng.uniform(0, 1, n)
    df["close"] = (df["open"] + df["high"] + df["low"]) / 3 + rng.normal(0, 0.1, n)
    df["volume"] = rng.integers(1_000_000, 10_000_000, n)

    # Add indicators
    df["rsi"] = rng.uniform(20, 80, n)
    df["bb_upper"] = df["close"] + 2.0
    df["bb_lower"] = df["close"] - 2.0
    df["zscore"] = rng.uniform(-3, 3, n)
    df["vol_confirm"] = rng.choice([True, False], n, p=[0.3, 0.7])
    df["regime_ok"] = rng.choice([True, False], n, p=[0.6, 0.4])
    df["atr"] = rng.uniform(0.5, 2.0, n)
    df["adx"] = rng.uniform(10, 30, n)
    df["hurst"] = rng.uniform(0.2, 0.8, n)
    df["hurst_fast"] = rng.uniform(0.2, 0.8, n)

    return df


class TestEntrySignals:
    def test_generate_entry_signals_adds_columns(self):
        df = _make_df()
        df_out = generate_entry_signals(df)
        assert "signal_long" in df_out.columns
        assert "signal_short" in df_out.columns
        assert df_out["signal_long"].dtype == bool
        assert df_out["signal_short"].dtype == bool

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"close": [100]})
        with pytest.raises(ValueError, match="missing required columns"):
            generate_entry_signals(df)

    def test_long_signal_conditions(self):
        df = _make_df(n=50)
        # Force a clear long signal at index 10
        df.loc[df.index[10], "regime_ok"] = True
        df.loc[df.index[10], "rsi"] = 25.0
        df.loc[df.index[10], "close"] = 90.0
        df.loc[df.index[10], "bb_lower"] = 95.0
        df.loc[df.index[10], "zscore"] = -3.0
        df.loc[df.index[10], "vol_confirm"] = True

        df_out = generate_entry_signals(df)
        assert df_out["signal_long"].iloc[10]
        assert not df_out["signal_short"].iloc[10]

    def test_short_signal_conditions(self):
        df = _make_df(n=50)
        # Force a clear short signal at index 15
        df.loc[df.index[15], "regime_ok"] = True
        df.loc[df.index[15], "rsi"] = 75.0
        df.loc[df.index[15], "close"] = 110.0
        df.loc[df.index[15], "bb_upper"] = 105.0
        df.loc[df.index[15], "zscore"] = 3.0
        df.loc[df.index[15], "vol_confirm"] = True

        df_out = generate_entry_signals(df)
        assert df_out["signal_short"].iloc[15]
        assert not df_out["signal_long"].iloc[15]

    def test_no_signal_without_regime(self):
        df = _make_df(n=50)
        df["regime_ok"] = False
        df_out = generate_entry_signals(df)
        assert df_out["signal_long"].sum() == 0
        assert df_out["signal_short"].sum() == 0

    def test_no_signal_without_volume_when_required(self):
        df = _make_df(n=50)
        df["regime_ok"] = True
        df["rsi"] = 25.0
        df["close"] = 90.0
        df["bb_lower"] = 95.0
        df["zscore"] = -3.0
        df["vol_confirm"] = False
        df_out = generate_entry_signals(df)
        assert df_out["signal_long"].sum() == 0

    def test_volume_optional(self):
        df = _make_df(n=50)
        df["regime_ok"] = True
        df["rsi"] = 25.0
        df["close"] = 90.0
        df["bb_lower"] = 95.0
        df["zscore"] = -3.0
        df["vol_confirm"] = False
        df_out = generate_entry_signals(df, cfg={"use_volume_confirm": False})
        assert df_out["signal_long"].sum() > 0

    def test_signal_counts(self):
        df = _make_df(n=50)
        df_out = generate_entry_signals(df)
        counts = signal_counts(df_out)
        assert "long_signals" in counts
        assert "short_signals" in counts
        assert "total_signals" in counts
        assert counts["total_signals"] == counts["long_signals"] + counts["short_signals"]

    def test_validate_signal_count_passes(self):
        df = _make_df(n=200)
        # Force at least one signal
        df.loc[df.index[10], "regime_ok"] = True
        df.loc[df.index[10], "rsi"] = 25.0
        df.loc[df.index[10], "close"] = 90.0
        df.loc[df.index[10], "bb_lower"] = 95.0
        df.loc[df.index[10], "zscore"] = -3.0
        df.loc[df.index[10], "vol_confirm"] = True
        df = generate_entry_signals(df)
        assert validate_signal_count(df, min_signals=1)

    def test_validate_signal_count_fails(self):
        df = _make_df(n=10)
        df["signal_long"] = False
        df["signal_short"] = False
        assert not validate_signal_count(df, min_signals=1)

    # ── Sprint 4: Entry soft scoring ────────────────────────────

    def test_entry_scoring_columns_present_with_soft_scoring(self):
        """When soft_scoring=True, entry_score and component scores appear."""
        from filters.regime import apply_regime_filter
        df = _make_df()
        df = apply_regime_filter(df, adx_threshold=30, hurst_threshold=0.6)
        df = generate_entry_signals(df, cfg={"soft_scoring": True})
        for col in ("entry_score", "rsi_score", "bb_score",
                     "zscore_score", "regime_score_entry"):
            assert col in df.columns, f"missing: {col}"

    def test_soft_scoring_produces_signals_when_binary_and_would_not(self):
        """A bar with excellent RSI+BB+z-score but regime_ok=False
        can fire with soft scoring (compensation) but never with binary AND."""
        from filters.regime import apply_regime_filter
        df = _make_df()
        df = apply_regime_filter(df, adx_threshold=30, hurst_threshold=0.6)
        # Force regime_ok=False for ALL bars
        df["regime_ok"] = False
        # But set strong entry conditions
        df["rsi"] = 25.0        # oversold
        df["zscore"] = -2.5     # extreme
        df["close"] = df["bb_lower"] - 1.0  # below lower
        df["vol_confirm"] = True
        # Binary AND: 0 signals (regime_ok=False blocks everything)
        df_bin = generate_entry_signals(df.copy(), cfg={"soft_scoring": False})
        assert df_bin["signal_long"].sum() == 0
        # Soft scoring with low entry_threshold: should fire
        df_soft = generate_entry_signals(df.copy(), cfg={
            "soft_scoring": True,
            "entry_score_threshold": 0.40,
            "score_regime_weight": 0.10,
        })
        assert df_soft["signal_long"].sum() > 0, (
            "soft scoring should fire when RSI/BB/z score compensate for regime"
        )

    def test_soft_scoring_respects_direction(self):
        """A bar with strong RSI oversold fires LONG, not SHORT."""
        from filters.regime import apply_regime_filter
        df = _make_df(n=30)
        df = apply_regime_filter(df, adx_threshold=30, hurst_threshold=0.6)
        df["rsi"] = 25.0       # oversold -> long signal
        df["zscore"] = -2.5    # negative -> long
        df_soft = generate_entry_signals(df, cfg={
            "soft_scoring": True,
            "entry_score_threshold": 0.40,
        })
        assert df_soft["signal_long"].iloc[-1], "long should fire on oversold + negative z"
        assert not df_soft["signal_short"].iloc[-1], "short should NOT fire on oversold"

    def test_binary_and_still_works_when_soft_scoring_false(self):
        """Backward compat: soft_scoring=False uses original AND logic."""
        from filters.regime import apply_regime_filter
        df = _make_df()
        df = apply_regime_filter(df, adx_threshold=30, hurst_threshold=0.6)
        df_bin = generate_entry_signals(df.copy(), cfg={"soft_scoring": False})
        df_def = generate_entry_signals(df.copy())
        # Default (None) should match explicit False
        assert (df_bin["signal_long"] == df_def["signal_long"]).all()
        assert (df_bin["signal_short"] == df_def["signal_short"]).all()


class TestExitSimulation:
    def test_simulate_exit_long_tp(self):
        """Long trade: zscore reverts to >=0 → TP.

        Realistic-fill note: all ``open`` values are pinned to 100.0
        so no post-entry bar can gap-fill the very tight SL
        (100 - 1.5*0.01 = 99.985) by accident.
        """
        df = _make_df(n=30)
        df["zscore"] = np.concatenate([[-2.5], np.linspace(-1, 1, 29)])
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.01  # tiny ATR so SL is never hit
        df["open"] = 100.0  # pin opens so no bar gaps past SL=99.985
        df.loc[df.index[0], "close"] = 100.0
        # Ensure low doesn't hit SL (SL = 100 - 1.5*0.01 = 99.985)
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.99
            df.loc[df.index[i], "high"] = 100.01

        result = simulate_exit(df, entry_idx=0, direction=1)
        assert result["direction"] == 1
        assert result["exit_reason"] == "tp"
        assert result["bars_held"] >= 1

    def test_simulate_exit_short_tp(self):
        """Short trade: zscore reverts to <=0 → TP."""
        df = _make_df(n=30)
        df["zscore"] = np.concatenate([[2.5], np.linspace(1, -1, 29)])
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0

        result = simulate_exit(df, entry_idx=0, direction=-1)
        assert result["direction"] == -1
        assert result["exit_reason"] == "tp"

    def test_simulate_exit_long_sl(self):
        """Long trade: price drops below SL → SL exit.

        Realistic-fill contract (2026-07-07): entry fills at T+1 open
        (not at signal-bar close). We pin T+1 open to 100 so the SL
        price is deterministic: 100 - 1.5*2 = 97.
        """
        df = _make_df(n=30)
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[0], "atr"] = 2.0
        # Realistic-fill: T+1 open is the actual fill price.
        df.loc[df.index[1], "open"] = 100.0
        # SL = 100 - 1.5*2 = 97
        for i in range(1, 10):
            df.loc[df.index[i], "low"] = 96.0
            df.loc[df.index[i], "high"] = 99.0
            df.loc[df.index[i], "close"] = 98.0
            df.loc[df.index[i], "zscore"] = -1.0  # prevent TP
            df.loc[df.index[i], "adx"] = 20.0
            df.loc[df.index[i], "regime_ok"] = True

        result = simulate_exit(df, entry_idx=0, direction=1)
        assert result["exit_reason"] == "sl"
        assert result["exit_price"] == pytest.approx(97.0, rel=1e-9)
        # Realistic fill: entry_price = T+1 open = 100, not close of
        # signal bar.
        assert result["entry_price"] == pytest.approx(100.0, rel=1e-9)
        # bars_held is exit_idx - entry_idx, where entry_idx is the
        # signal bar and exit_idx is the bar where the trigger fired.
        assert result["bars_held"] == 1

    def test_simulate_exit_time_stop(self):
        """Trade held until max_bars → time stop.

        Realistic-fill note: all opens pinned to 100.0 so the very
        tight SL (100 - 1.5*0.001 = 99.9985) cannot be gap-filled
        by a random open from ``_make_df``.
        """
        df = _make_df(n=50)
        df["zscore"] = -1.0  # never reaches TP
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001  # tiny ATR so SL isn't hit
        df["open"] = 100.0  # pin opens so no bar gaps past SL=99.9985
        df.loc[df.index[0], "close"] = 100.0
        # Ensure low doesn't hit SL
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001

        result = simulate_exit(df, entry_idx=0, direction=1, max_bars=5)
        assert result["exit_reason"] == "time"
        assert result["bars_held"] == 5

    def test_simulate_exit_regime_stop(self):
        """ADX spikes above threshold → regime stop.

        Realistic-fill note: all opens pinned to 100.0 so the very
        tight SL (100 - 1.5*0.001 = 99.9985) cannot be gap-filled
        before the regime_stop at bar 5.
        """
        df = _make_df(n=30)
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df.loc[df.index[5], "adx"] = 30.0  # spike
        df["regime_ok"] = True
        df["atr"] = 0.001
        df["open"] = 100.0  # pin opens so no bar gaps past SL=99.9985
        df.loc[df.index[0], "close"] = 100.0
        # Ensure low doesn't hit SL
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001

        result = simulate_exit(df, entry_idx=0, direction=1, adx_stop_threshold=25.0)
        assert result["exit_reason"] == "regime"
        assert result["exit_idx"] == 5

    def test_simulate_exit_end_of_data(self):
        """Entry near end of DataFrame → end_of_data."""
        df = _make_df(n=10)
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001
        df.loc[df.index[0], "close"] = 100.0
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999

        result = simulate_exit(df, entry_idx=8, direction=1, max_bars=25)
        assert result["exit_reason"] == "end_of_data"

    def test_invalid_direction_raises(self):
        df = _make_df(n=10)
        with pytest.raises(ValueError, match="direction must be 1"):
            simulate_exit(df, entry_idx=0, direction=0)

    def test_out_of_bounds_entry_raises(self):
        df = _make_df(n=10)
        with pytest.raises(ValueError, match="out of bounds"):
            simulate_exit(df, entry_idx=100, direction=1)

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"close": [100]})
        with pytest.raises(ValueError, match="missing required columns"):
            simulate_exit(df, entry_idx=0, direction=1)


class TestSimulateAllTrades:
    def test_simulate_all_trades_basic(self):
        df = _make_df(n=100)
        df = generate_entry_signals(df)
        trades = simulate_all_trades(df)
        assert isinstance(trades, pd.DataFrame)
        # Either we have trades or an empty DataFrame with correct columns
        expected_cols = [
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct", "bars_held", "exit_reason",
        ]
        assert list(trades.columns) == expected_cols

    def test_no_signals_returns_empty(self):
        df = _make_df(n=50)
        df["signal_long"] = False
        df["signal_short"] = False
        trades = simulate_all_trades(df)
        assert trades.empty
        assert list(trades.columns) == [
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct", "bars_held", "exit_reason",
        ]

    def test_overlapping_signals_skipped(self):
        """Signals that fire while a trade is open should be skipped."""
        df = _make_df(n=50)
        # Ensure signal columns exist
        df["signal_long"] = False
        df["signal_short"] = False
        # Force two long signals close together
        df.loc[df.index[5], "signal_long"] = True
        df.loc[df.index[6], "signal_long"] = True
        # Make first trade take 10 bars (time stop)
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001
        df.loc[df.index[0], "close"] = 100.0
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001

        trades = simulate_all_trades(df, cfg={"max_bars": 10})
        # Only the first signal should produce a trade
        if not trades.empty:
            assert len(trades) == 1
            assert trades.iloc[0]["entry_idx"] == 5

    def test_exit_reason_stats(self):
        df = _make_df(n=200)
        df = generate_entry_signals(df)
        trades = simulate_all_trades(df)
        if not trades.empty:
            stats = exit_reason_stats(trades)
            assert "count" in stats.columns or len(stats.columns) == 2

    def test_exit_reason_stats_empty(self):
        empty = pd.DataFrame(columns=["exit_reason"])
        stats = exit_reason_stats(empty)
        assert stats.empty

    def test_nan_guard_exits_immediately(self):
        """If zscore becomes NaN mid-trade, exit immediately with nan_data reason.

        Realistic-fill note: all opens pinned to 100.0 so the very
        tight SL (100 - 1.5*0.001 = 99.9985) cannot be gap-filled
        before the NaN injection at bar 7.
        """
        df = _make_df(n=30)
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001
        df["open"] = 100.0  # pin opens so no bar gaps past SL=99.9985
        df.loc[df.index[0], "close"] = 100.0
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001
        # Inject NaN zscore at bar 7
        df.loc[df.index[7], "zscore"] = np.nan

        result = simulate_exit(df, entry_idx=0, direction=1)
        assert result["exit_reason"] == "nan_data"
        assert result["exit_idx"] == 7
        assert not np.isnan(result["pnl_pct"])

    def test_mixed_direction_trades(self):
        """Interleaved long and short signals are sorted and simulated correctly."""
        df = _make_df(n=60)
        df["signal_long"] = False
        df["signal_short"] = False
        # Long at 5, short at 15, long at 25
        df.loc[df.index[5], "signal_long"] = True
        df.loc[df.index[15], "signal_short"] = True
        df.loc[df.index[25], "signal_long"] = True
        # Prevent TP / SL / regime stop so time stop fires predictably
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001

        trades = simulate_all_trades(df, cfg={"max_bars": 5})
        assert len(trades) == 3
        assert trades.iloc[0]["direction"] == 1   # long at 5
        assert trades.iloc[0]["entry_idx"] == 5
        assert trades.iloc[1]["direction"] == -1  # short at 15
        assert trades.iloc[1]["entry_idx"] == 15
        assert trades.iloc[2]["direction"] == 1   # long at 25
        assert trades.iloc[2]["entry_idx"] == 25
        # Verify overlap skipping: next signal at 25, previous exits at 20 (5+5)
        assert trades.iloc[2]["entry_idx"] > trades.iloc[1]["exit_idx"]


class TestSignalsSkipped:
    """Tests for signals_skipped counter (FIX_PLAN_v2 Step 5)."""

    def test_signals_skipped_counted(self):
        """Two overlapped signals: second is skipped, counter reflects it."""
        df = _make_df(n=50)
        df["signal_long"] = False
        df["signal_short"] = False
        # Two close long signals: bar 5 and bar 6
        df.loc[df.index[5], "signal_long"] = True
        df.loc[df.index[6], "signal_long"] = True
        # Make first trade take long enough to overlap
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001

        trades = simulate_all_trades(df, cfg={"max_bars": 10})
        assert trades.attrs["signals_total"] == 2
        assert trades.attrs["signals_skipped"] >= 1
        assert trades.attrs["signals_executed"] == 1

    def test_signals_skipped_zero_when_no_overlap(self):
        """Well-spaced signals: none are skipped."""
        df = _make_df(n=60)
        df["signal_long"] = False
        df["signal_short"] = False
        # Signals far apart: bar 5 and bar 40
        df.loc[df.index[5], "signal_long"] = True
        df.loc[df.index[40], "signal_long"] = True
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001

        trades = simulate_all_trades(df, cfg={"max_bars": 5})
        assert trades.attrs["signals_total"] == 2
        assert trades.attrs["signals_skipped"] == 0
        assert trades.attrs["signals_executed"] == 2

    def test_signals_skipped_empty_df(self):
        """No signals: total=0, skipped=0, executed=0."""
        df = _make_df(n=10)
        df["signal_long"] = False
        df["signal_short"] = False
        trades = simulate_all_trades(df)
        assert trades.attrs["signals_total"] == 0
        assert trades.attrs["signals_skipped"] == 0
        assert trades.attrs["signals_executed"] == 0


class TestRealisticFillContract:
    """
    Invariant tests for the realistic-fill contract introduced
    2026-07-07 to close the execution-model look-ahead bias.

    Contract recap (see ``signals.exit.simulate_exit`` docstring):

    1. Entry fills at OPEN of T+1 (next bar after signal), not at
       the close of the signal bar.
    2. When a post-trigger bar opens AT OR BEYOND the planned SL,
       the trade gap-fills at that bar's OPEN with
       ``exit_reason == "open_gap_sl"``.
    3. When a post-trigger bar reaches the SL inside its OHLC
       range, fill at the SL price with ``exit_reason == "sl"``.
    4. Take Profit is still close-based (z-score on close), so it
       does not gap-fill.
    """

    def test_entry_fills_at_t_plus_1_open_not_signal_close(self):
        """
        Construct a df where signal-bar close and T+1 open are
        DIFFERENT. The trade MUST use T+1 open as entry_price, not
        the signal-bar close. This locks the no-look-ahead contract.
        """
        df = _make_df(n=30)
        # Signal bar 0: close = 100, ATR = 1.
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[0], "atr"] = 1.0
        # T+1 (bar 1): open = 105 — a deliberate gap up. The trade
        # must fill at 105, not at the close-of-signal 100.
        df.loc[df.index[1], "open"] = 105.0
        df.loc[df.index[1], "high"] = 106.0
        df.loc[df.index[1], "low"] = 104.0
        df.loc[df.index[1], "close"] = 105.5
        # Tame all later bars so no post-entry bar can hit the SL
        # (105 - 1.5*1 = 103.5). We pin high/low/close as well as
        # open because ``_make_df`` already computed high/low from
        # the original random-walk opens; overriding ``open`` alone
        # would leave random low values that easily hit the SL.
        df.loc[df.index[2:], "open"] = 110.0
        df.loc[df.index[2:], "high"] = 111.0
        df.loc[df.index[2:], "low"] = 109.0
        df.loc[df.index[2:], "close"] = 110.5
        # z-score path: -2 -> +1 over 9 bars so TP fires mid-trade
        # (TP fires on the first bar where z >= 0, around bar 7).
        df["zscore"] = np.concatenate(
            [[-2.0], np.linspace(-2, 1, 9), [0.5] * (len(df) - 10)]
        )
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0  # constant ATR for deterministic SL math

        result = simulate_exit(df, entry_idx=0, direction=1)
        # Realistic fill: T+1 open, NOT signal-bar close.
        assert result["entry_price"] == pytest.approx(105.0, rel=1e-9)
        # The pre-fix bias (close-of-signal) would have used 100.0.
        assert result["entry_price"] != pytest.approx(100.0, rel=1e-9)
        # Sanity: the trade must have hit TP at some point.
        assert result["exit_reason"] == "tp"

    def test_sl_gap_fill_when_post_entry_bar_opens_past_sl(self):
        """
        Long trade. On bar i = entry_idx + 2 the open is BELOW the
        planned SL. The trade MUST gap-fill at that open with
        ``exit_reason == "open_gap_sl"``, NOT at the SL price.
        """
        df = _make_df(n=30)
        # Signal at bar 0.
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[0], "atr"] = 1.0
        # T+1 fill: open = 100. SL = 100 - 1.5*1 = 98.5.
        df.loc[df.index[1], "open"] = 100.0
        df.loc[df.index[1], "high"] = 100.5
        df.loc[df.index[1], "low"] = 99.5
        df.loc[df.index[1], "close"] = 99.8
        # T+2: open gaps DOWN to 98.0, well below SL of 98.5. This
        # is the gap-fill bar.
        df.loc[df.index[2], "open"] = 98.0
        df.loc[df.index[2], "high"] = 98.4
        df.loc[df.index[2], "low"] = 97.0
        df.loc[df.index[2], "close"] = 97.5
        # Tame the rest of the bars so a regime stop or time stop
        # never pre-empts the gap-fill observation.
        for i in range(3, len(df)):
            df.loc[df.index[i], "open"] = 100.0
            df.loc[df.index[i], "high"] = 100.5
            df.loc[df.index[i], "low"] = 99.5
            df.loc[df.index[i], "close"] = 100.0
        # Prevent TP by keeping z-score always negative.
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0

        result = simulate_exit(df, entry_idx=0, direction=1)
        # The fill bar at idx 1 has open=100, not a gap. The
        # gap-fill should fire on bar 2.
        assert result["exit_reason"] == "open_gap_sl"
        assert result["exit_idx"] == 2
        # exit_price = the open of the gap bar (98.0), NOT the SL
        # price (98.5). This is the gap-fill contract: cannot fill at
        # SL when the market gapped through.
        assert result["exit_price"] == pytest.approx(98.0, rel=1e-9)
        assert result["entry_price"] == pytest.approx(100.0, rel=1e-9)

    def test_intra_bar_sl_still_fills_at_sl_price(self):
        """
        Long trade. The post-trigger bar opens INSIDE the SL
        corridor (open > SL) but its low reaches the SL. The trade
        must fill at the SL price, not at the open. This locks the
        pre-existing intra-bar SL contract.
        """
        df = _make_df(n=30)
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[0], "atr"] = 1.0
        # T+1 fill: open = 100, SL = 98.5.
        df.loc[df.index[1], "open"] = 100.0
        df.loc[df.index[1], "high"] = 100.5
        df.loc[df.index[1], "low"] = 99.5
        df.loc[df.index[1], "close"] = 99.8
        # T+2: opens at 99 (above SL of 98.5 → not a gap), but
        # the bar's low reaches 98.4 (below SL of 98.5).
        # Intra-bar SL fills at the SL price (98.5).
        df.loc[df.index[2], "open"] = 99.0
        df.loc[df.index[2], "high"] = 99.4
        df.loc[df.index[2], "low"] = 98.4
        df.loc[df.index[2], "close"] = 98.8
        # Tame the rest.
        for i in range(3, len(df)):
            df.loc[df.index[i], "open"] = 100.0
            df.loc[df.index[i], "high"] = 100.5
            df.loc[df.index[i], "low"] = 99.5
            df.loc[df.index[i], "close"] = 100.0
        df["zscore"] = -1.0  # never TP
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0

        result = simulate_exit(df, entry_idx=0, direction=1)
        assert result["exit_reason"] == "sl"
        assert result["exit_price"] == pytest.approx(98.5, rel=1e-9)
        # And NOT the bar's open (99.0) nor its low (98.4): the
        # fill is the planned SL price.
        assert result["exit_price"] != pytest.approx(99.0, rel=1e-9)
        assert result["exit_price"] != pytest.approx(98.4, rel=1e-9)

    def test_sl_gap_fill_for_short(self):
        """
        Symmetric short-side gap-fill test. On a short, when bar i
        opens at or above the planned SL (which is ABOVE
        entry_price for shorts), the trade must gap-fill at that
        open with ``exit_reason == "open_gap_sl"``.
        """
        df = _make_df(n=30)
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[0], "atr"] = 1.0
        # T+1 fill: open = 100. Short SL = 100 + 1.5 = 101.5.
        df.loc[df.index[1], "open"] = 100.0
        df.loc[df.index[1], "high"] = 100.5
        df.loc[df.index[1], "low"] = 99.5
        df.loc[df.index[1], "close"] = 99.8
        # T+2: open gaps UP to 102.0, above SL of 101.5. Gap-fill
        # fires for the short.
        df.loc[df.index[2], "open"] = 102.0
        df.loc[df.index[2], "high"] = 102.4
        df.loc[df.index[2], "low"] = 101.9
        df.loc[df.index[2], "close"] = 102.1
        for i in range(3, len(df)):
            df.loc[df.index[i], "open"] = 100.0
            df.loc[df.index[i], "high"] = 100.5
            df.loc[df.index[i], "low"] = 99.5
            df.loc[df.index[i], "close"] = 100.0
        df["zscore"] = 1.0  # never TP for short
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0

        result = simulate_exit(df, entry_idx=0, direction=-1)
        assert result["exit_reason"] == "open_gap_sl"
        assert result["exit_idx"] == 2
        assert result["exit_price"] == pytest.approx(102.0, rel=1e-9)
        assert result["entry_price"] == pytest.approx(100.0, rel=1e-9)

    def test_entry_bar_cannot_self_gap_fill(self):
        """
        Structural invariant: the entry bar (T+1) cannot gap-fill
        its own SL by construction, because the SL price is
        computed from entry_price (long: SL = open - 1.5*ATR, so
        the gap-fill condition ``opn <= sl_price`` reduces to
        ``open <= open - 1.5*ATR`` which is impossible when ATR > 0).

        We pin this property by constructing a scenario that
        DELIBERATELY produces a gap-fill on bar i = entry_idx+2
        (the earliest possible gap-fill bar) and asserting the
        trade does NOT exit on the fill bar (i = entry_idx+1).
        If a future refactor lets the fill bar self-gap-fill, the
        test's hard ``exit_idx != entry_idx+1`` assertion trips.
        """
        df = _make_df(n=30)
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[0], "atr"] = 1.0
        # T+1 open = 100. SL = 100 - 1.5*1 = 98.5. The fill bar
        # open (100) is NOT <= SL (98.5), so the gap-fill on the
        # fill bar itself is structurally impossible.
        df.loc[df.index[1], "open"] = 100.0
        df.loc[df.index[1], "high"] = 100.5
        df.loc[df.index[1], "low"] = 99.5
        df.loc[df.index[1], "close"] = 100.0
        # T+2: open = 95 (below SL of 98.5). This is the bar where
        # the gap-fill MUST fire, and it must fire here (not on
        # bar 1).
        df.loc[df.index[2], "open"] = 95.0
        df.loc[df.index[2], "high"] = 95.4
        df.loc[df.index[2], "low"] = 94.0
        df.loc[df.index[2], "close"] = 95.0
        for i in range(3, len(df)):
            df.loc[df.index[i], "open"] = 100.0
            df.loc[df.index[i], "high"] = 100.5
            df.loc[df.index[i], "low"] = 99.5
            df.loc[df.index[i], "close"] = 100.0
        df["zscore"] = -1.0  # never TP
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0

        result = simulate_exit(df, entry_idx=0, direction=1)
        # The trade MUST reach the gap-fill at i = entry_idx + 2.
        # This single assertion locks the structural property: the
        # fill bar (i = entry_idx + 1) cannot self-gap-fill, so the
        # earliest possible gap-fill is bar 2. (Long: gap-fill is
        # ``opn <= SL`` = ``opn <= entry_price - 1.5*ATR``, which
        # is impossible on the fill bar where opn = entry_price.)
        assert result["exit_reason"] == "open_gap_sl"
        assert result["exit_idx"] == 2, (
            "Gap-fill on the entry bar itself is impossible by "
            "construction (SL = entry_price - 1.5*ATR, so opn <= "
            "SL reduces to 0 <= -1.5*ATR). If exit_idx != 2, the "
            "SL math has regressed."
        )

    def test_realistic_fill_diverges_from_old_signal_close_contract(self):
        """
        The realistic-fill contract MUST produce a DIFFERENT pnl_pct
        than the old (close-of-signal) contract would have, when
        T+1 open diverges from the signal-bar close.

        Construct a scenario where:
        - signal-bar close = 100 (this is what the OLD contract
          would have used as the entry price);
        - T+1 open = 110 (a 10% gap up — a LARGE divergence that
          makes the contracts numerically distinct);
        - the trade hits TP before any gap-fill can fire.

        With realistic fill, entry_price = 110. With old contract,
        entry_price = 100. The same exit price therefore yields
        different pnl_pct under the two contracts.
        """
        df = _make_df(n=30)
        df.loc[df.index[0], "close"] = 100.0  # signal-bar close
        df.loc[df.index[0], "atr"] = 1.0
        # T+1 open = 110 (deliberate 10% gap up vs signal close 100).
        df.loc[df.index[1], "open"] = 110.0
        df.loc[df.index[1], "high"] = 111.0
        df.loc[df.index[1], "low"] = 109.0
        df.loc[df.index[1], "close"] = 110.5
        # Tame all later bars so no post-entry bar can hit the SL
        # (110 - 1.5*1 = 108.5). We pin high/low/close as well as
        # open because ``_make_df`` already computed high/low from
        # the original random-walk opens.
        df.loc[df.index[2:], "open"] = 115.0
        df.loc[df.index[2:], "high"] = 116.0
        df.loc[df.index[2:], "low"] = 114.0
        df.loc[df.index[2:], "close"] = 115.5
        # z-score path: -2 -> +1 over 9 bars so TP fires mid-trade.
        df["zscore"] = np.concatenate(
            [[-2.0], np.linspace(-2, 1, 9), [0.5] * (len(df) - 10)]
        )
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0

        result = simulate_exit(df, entry_idx=0, direction=1)
        # Realistic fill uses T+1 open.
        assert result["entry_price"] == pytest.approx(110.0, rel=1e-9)
        # Sanity: the trade must have hit TP (no gap-fill because
        # all opens after the fill bar are at 115, far above SL 108.5).
        assert result["exit_reason"] == "tp"
        # Compute the OLD-contract pnl_pct for comparison: with the
        # same exit_price and a hypothetical entry_price=100, the
        # pnl_pct would be (exit_price - 100) / 100.
        old_pnl_pct = (result["exit_price"] - 100.0) / 100.0
        # Sign-pinned assertion: the realistic fill (entry at T+1
        # open = 110) is at a higher price than the old contract
        # would have used (entry at signal close = 100). For the
        # same exit, pnl_pct MUST be strictly smaller under the
        # realistic contract. A coincidental `!=` could pass if a
        # regression silently reversed the contract direction; this
        # deterministic `<` catches it.
        assert result["pnl_pct"] < old_pnl_pct, (
            f"Realistic-fill pnl_pct ({result['pnl_pct']:.6f}) must be "
            f"strictly less than the old-contract pnl_pct "
            f"({old_pnl_pct:.6f}) when T+1 open (110) exceeds the "
            f"signal-bar close (100). A higher entry price on the "
            f"same exit yields a smaller return. If this fails, the "
            f"contract direction has been silently reversed."
        )

    def test_realistic_fill_diverges_for_short(self):
        """
        Symmetric SHORT version of the divergence test.

        Construct a scenario where:
        - signal-bar close = 100 (what OLD contract would have used);
        - T+1 open = 90 (a gap DOWN, more favorable for the short);
        - the trade hits TP (z <= 0 for a short) before any gap-fill.

        With the realistic fill (entry at 90), the percentage return
        is computed with a smaller denominator than the old contract
        (entry at 100). For the same exit price, the realistic
        contract's pnl_pct MUST be strictly smaller — same sign
        direction as the LONG test because a higher-denominator
        entry on the same exit yields a smaller return.
        """
        df = _make_df(n=30)
        df.loc[df.index[0], "close"] = 100.0  # signal-bar close
        df.loc[df.index[0], "atr"] = 1.0
        # T+1 open = 90 (gap DOWN; short fills at a lower price).
        df.loc[df.index[1], "open"] = 90.0
        df.loc[df.index[1], "high"] = 91.0
        df.loc[df.index[1], "low"] = 89.0
        df.loc[df.index[1], "close"] = 90.5
        # Tame all later bars so no post-entry bar can gap-fill the
        # SL (for short: SL = 90 + 1.5*1 = 91.5, gap-fill fires when
        # open >= 91.5). Pin all later opens to 85 (well below SL).
        df.loc[df.index[2:], "open"] = 85.0
        df.loc[df.index[2:], "high"] = 86.0
        df.loc[df.index[2:], "low"] = 84.0
        df.loc[df.index[2:], "close"] = 85.5
        # z-score path: +2 -> -1 so TP (z <= 0) fires mid-trade.
        df["zscore"] = np.concatenate(
            [[2.0], np.linspace(2, -1, 9), [-0.5] * (len(df) - 10)]
        )
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 1.0

        result = simulate_exit(df, entry_idx=0, direction=-1)
        # Realistic fill uses T+1 open.
        assert result["entry_price"] == pytest.approx(90.0, rel=1e-9)
        # Sanity: the trade must have hit TP (no gap-fill because all
        # later opens are at 85, well below SL 91.5).
        assert result["exit_reason"] == "tp"
        # Old contract would have entered at signal close (100).
        # Short pnl = -1 * (exit - entry) / entry.
        old_pnl_pct = -1.0 * (result["exit_price"] - 100.0) / 100.0
        # Sign-pinned: the realistic fill (entry at 90) has a smaller
        # denominator → smaller pnl_pct for the same exit. Same sign
        # as the LONG divergence test.
        assert result["pnl_pct"] < old_pnl_pct, (
            f"Realistic-fill short pnl_pct ({result['pnl_pct']:.6f}) must "
            f"be strictly less than the old-contract pnl_pct "
            f"({old_pnl_pct:.6f}) when T+1 open (90) is below the "
            f"signal-bar close (100). A lower short-entry price on the "
            f"same exit magnifies the divergence. If this fails, the "
            f"contract direction has been silently reversed."
        )

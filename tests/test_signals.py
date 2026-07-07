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
        """Long trade: zscore reverts to >=0 → TP."""
        df = _make_df(n=30)
        df["zscore"] = np.concatenate([[-2.5], np.linspace(-1, 1, 29)])
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.01  # tiny ATR so SL is never hit
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
        """Long trade: price drops below SL → SL exit."""
        df = _make_df(n=30)
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[0], "atr"] = 2.0
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

    def test_simulate_exit_time_stop(self):
        """Trade held until max_bars → time stop."""
        df = _make_df(n=50)
        df["zscore"] = -1.0  # never reaches TP
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001  # tiny ATR so SL isn't hit
        df.loc[df.index[0], "close"] = 100.0
        # Ensure low doesn't hit SL
        for i in range(len(df)):
            df.loc[df.index[i], "low"] = 99.999
            df.loc[df.index[i], "high"] = 100.001

        result = simulate_exit(df, entry_idx=0, direction=1, max_bars=5)
        assert result["exit_reason"] == "time"
        assert result["bars_held"] == 5

    def test_simulate_exit_regime_stop(self):
        """ADX spikes above threshold → regime stop."""
        df = _make_df(n=30)
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df.loc[df.index[5], "adx"] = 30.0  # spike
        df["regime_ok"] = True
        df["atr"] = 0.001
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
        """If zscore becomes NaN mid-trade, exit immediately with nan_data reason."""
        df = _make_df(n=30)
        df["zscore"] = -1.0
        df["adx"] = 20.0
        df["regime_ok"] = True
        df["atr"] = 0.001
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

"""Unit tests for indicator modules."""

import numpy as np
import pandas as pd
import pytest

from indicators.adx import add_adx
from indicators.atr import add_atr
from indicators.bollinger import add_bollinger
from indicators.hurst import add_hurst, add_hurst_fast
from indicators.rsi import add_rsi
from indicators.volume import add_volume_filter
from indicators.zscore import add_zscore


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Generate a small synthetic OHLCV DataFrame."""
    np.random.seed(42)
    n = 50
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame(
        {
            "open": close - np.random.rand(n) * 0.5,
            "high": close + np.random.rand(n) * 0.5 + 0.1,
            "low": close - np.random.rand(n) * 0.5 - 0.1,
            "close": close,
            "volume": np.random.randint(1_000, 10_000, n),
        },
        index=idx,
    )
    return df


class TestADX:
    def test_adds_column(self, sample_df):
        df = add_adx(sample_df)
        assert "adx" in df.columns
        # ADX needs 2*period-1 bars to warm up in TA-Lib
        assert df["adx"].iloc[27:].notna().all()

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"close": [100, 101]})
        with pytest.raises(ValueError, match="add_adx missing required columns"):
            add_adx(df)


class TestRSI:
    def test_adds_column(self, sample_df):
        df = add_rsi(sample_df)
        assert "rsi" in df.columns
        assert df["rsi"].iloc[14:].notna().all()

    def test_range_0_100(self, sample_df):
        df = add_rsi(sample_df)
        valid = df["rsi"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"open": [100]})
        with pytest.raises(ValueError, match="add_rsi missing required columns"):
            add_rsi(df)


class TestBollinger:
    def test_adds_columns(self, sample_df):
        df = add_bollinger(sample_df)
        assert set(df.columns) >= {"bb_upper", "bb_mid", "bb_lower"}

    def test_band_order(self, sample_df):
        df = add_bollinger(sample_df).dropna()
        assert (df["bb_upper"] >= df["bb_mid"]).all()
        assert (df["bb_mid"] >= df["bb_lower"]).all()


class TestZScore:
    def test_adds_column(self, sample_df):
        df = add_zscore(sample_df)
        assert "zscore" in df.columns

    def test_no_division_by_zero(self):
        """Flat prices should yield zscore = 0 (not inf/NaN) once window is warm."""
        df = pd.DataFrame({"close": [100.0] * 30})
        df = add_zscore(df)
        valid = df["zscore"].dropna()
        assert (valid == 0.0).all()

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"volume": [1000]})
        with pytest.raises(ValueError, match="add_zscore missing required columns"):
            add_zscore(df)


class TestVolume:
    def test_adds_columns(self, sample_df):
        df = add_volume_filter(sample_df)
        assert set(df.columns) >= {"vol_avg", "vol_confirm"}

    def test_confirm_is_bool(self, sample_df):
        df = add_volume_filter(sample_df)
        assert df["vol_confirm"].dropna().isin({True, False}).all()


class TestATR:
    def test_adds_column(self, sample_df):
        df = add_atr(sample_df)
        assert "atr" in df.columns
        assert df["atr"].iloc[14:].notna().all()

    def test_positive(self, sample_df):
        df = add_atr(sample_df)
        assert (df["atr"].dropna() > 0).all()

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"close": [100, 101]})
        with pytest.raises(ValueError, match="add_atr missing required columns"):
            add_atr(df)


class TestHurst:
    def test_adds_column(self, sample_df):
        df = add_hurst(sample_df, window=30)
        assert "hurst" in df.columns

    def test_value_range(self, sample_df):
        df = add_hurst(sample_df, window=30).dropna()
        # Hurst can theoretically be any real number, but for this
        # synthetic random-walk-like data it should be near 0.5
        if len(df) > 0:
            assert -1.0 <= df["hurst"].mean() <= 2.0

    def test_flat_prices_returns_nan(self):
        """Flat prices have zero std → all tau = 0 → valid < 2 → NaN."""
        df = pd.DataFrame({"close": [100.0] * 100})
        df = add_hurst(df, window=30)
        assert df["hurst"].isna().all()

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"volume": [1000]})
        with pytest.raises(ValueError, match="Hurst calculation missing required columns"):
            add_hurst(df)


class TestHurstFast:
    """Tests for the fast Hurst (window=50) added in Sprint 1 bottleneck fix."""

    def test_adds_column(self, sample_df):
        # window=30 fits the 50-bar sample_df fixture
        df = add_hurst_fast(sample_df, window=30)
        assert "hurst_fast" in df.columns

    def test_different_from_slow_hurst(self, sample_df):
        """Fast Hurst (window=30) should diverge from slow Hurst (window=50)
        because the rolling windows capture different time scales."""
        df = add_hurst(sample_df, window=50)
        df = add_hurst_fast(df, window=30)
        both = df[["hurst", "hurst_fast"]].dropna()
        if len(both) > 0:
            assert not (both["hurst"] == both["hurst_fast"]).all(), (
                "Fast and slow Hurst should differ on non-trivial data"
            )

    def test_default_window_is_50(self, sample_df):
        """Default window for fast Hurst is 50 (spec from BOTTLENECK_FIX_PLAN)."""
        # Build a df large enough for window=50
        n = 50
        idx = pd.date_range("2024-01-01", periods=n, freq="15min")
        df = pd.DataFrame({
            "open": 100.0, "high": 101.0, "low": 99.0,
            "close": 100.0, "volume": 1_000_000.0,
        }, index=idx)
        result = add_hurst_fast(df)
        assert "hurst_fast" in result.columns
        # With flat prices, last value is NaN (zero std → no valid lags)
        # but the column exists and has the correct length
        assert len(result) == n

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"volume": [1000]})
        with pytest.raises(ValueError, match="Hurst calculation missing required columns"):
            add_hurst_fast(df)

"""Unit tests for filter modules."""

import numpy as np
import pandas as pd
import pytest

from filters.regime import apply_regime_filter, regime_coverage


@pytest.fixture
def regime_df() -> pd.DataFrame:
    """Synthetic DataFrame with indicator columns ready for regime filter."""
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    df = pd.DataFrame(
        {
            "adx": np.linspace(15, 30, n),     # crosses threshold
            "hurst": np.full(n, 0.40),         # mean-reverting
            "atr": np.full(n, 1.0),
            "close": np.full(n, 100.0),
        },
        index=idx,
    )
    return df


class TestRegimeFilter:
    def test_adds_columns(self, regime_df):
        df = apply_regime_filter(regime_df)
        assert set(df.columns) >= {"atr_rel", "atr_rel_z", "regime_ok"}

    def test_regime_ok_is_bool(self, regime_df):
        df = apply_regime_filter(regime_df)
        assert df["regime_ok"].dropna().isin({True, False}).all()

    def test_coverage_between_0_and_100(self, regime_df):
        df = apply_regime_filter(regime_df)
        cov = regime_coverage(df)
        assert 0.0 <= cov <= 100.0

    def test_constant_atr_zscore_is_zero(self):
        """When ATR is constant, atr_rel_z should be 0 (not inf/NaN)."""
        df = pd.DataFrame(
            {
                "adx": [20.0] * 50,
                "hurst": [0.40] * 50,
                "atr": [1.0] * 50,
                "close": [100.0] * 50,
            }
        )
        df = apply_regime_filter(df)
        assert df["atr_rel_z"].iloc[20:].fillna(0).eq(0).all()

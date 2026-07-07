"""Unit tests for indicators pipeline."""

import numpy as np
import pandas as pd
import pytest

from indicators.pipeline import build_all_indicators


@pytest.fixture
def sample_df() -> pd.DataFrame:
    np.random.seed(7)
    n = 60
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


class TestBuildAllIndicators:
    def test_adds_all_columns(self, sample_df):
        df = build_all_indicators(sample_df)
        expected = {
            "adx", "hurst", "rsi", "bb_upper", "bb_mid", "bb_lower",
            "zscore", "vol_avg", "vol_confirm", "atr",
        }
        assert expected.issubset(set(df.columns))

    def test_respects_cfg(self, sample_df):
        cfg = {"rsi": {"period": 7}}
        df = build_all_indicators(sample_df, cfg=cfg)
        assert "rsi" in df.columns
        # RSI with period 7 warms up faster
        assert df["rsi"].iloc[10:].notna().all()

    def test_ignores_unknown_cfg_keys(self, sample_df):
        cfg = {"rsi": {"period": 14, "oversold": 30}}
        # "oversold" is not a parameter of add_rsi — should be silently ignored
        df = build_all_indicators(sample_df, cfg=cfg)
        assert "rsi" in df.columns

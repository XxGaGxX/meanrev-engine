"""
End-to-end integration test — Mean Reversion Intraday
=======================================================
Chains the full pipeline:  clean → indicators → filter → metrics
using only in-memory synthetic data (no network calls).
"""

import numpy as np
import pandas as pd

from data.clean import clean_data, filter_session_hours
from filters.regime import apply_regime_filter, regime_coverage
from indicators.pipeline import build_all_indicators
from utils.config import config
from utils.metrics import calculate_all_metrics, print_metrics


def generate_synthetic_ohlcv(n_bars: int = 500, seed: int = 42) -> pd.DataFrame:
    """Create realistic-looking intraday OHLCV data."""
    np.random.seed(seed)
    # Start on a Monday, 15-min bars for ~2 weeks of trading
    idx = pd.date_range("2024-01-08 09:30", periods=n_bars, freq="15min")
    # Remove after-hours bars to simulate real market hours
    mask = (idx.time >= pd.Timestamp("09:30").time()) & (
        idx.time <= pd.Timestamp("16:00").time()
    )
    idx = idx[mask][:n_bars]

    returns = np.random.randn(len(idx)) * 0.003
    close = 450 * np.exp(np.cumsum(returns))
    noise = np.random.rand(len(idx)) * 0.5
    df = pd.DataFrame(
        {
            "open": close - noise,
            "high": close + noise + 0.2,
            "low": close - noise - 0.2,
            "close": close,
            "volume": np.random.randint(1_000_000, 5_000_000, len(idx)),
        },
        index=idx,
    )
    return df


def test_end_to_end_pipeline():
    """Full pipeline: clean → indicators → filter → metrics."""
    # 1. Generate raw data (simulating fetch)
    raw = generate_synthetic_ohlcv(n_bars=400)

    # 2. Clean
    cleaned = clean_data(raw)
    assert len(cleaned) > 0
    assert set(cleaned.columns) >= {"open", "high", "low", "close", "volume"}

    # 3. Filter session hours
    session = filter_session_hours(
        cleaned,
        skip_first_minutes=config.get("timeframe.skip_first_minutes", 30),
        skip_last_minutes=config.get("timeframe.skip_last_minutes", 30),
    )
    assert len(session) > 0

    # 4. Build indicators
    cfg = config.raw.get("indicators", {})
    df = build_all_indicators(session, cfg=cfg)
    expected_cols = {
        "adx", "hurst", "rsi", "bb_upper", "bb_mid", "bb_lower",
        "zscore", "vol_avg", "vol_confirm", "atr",
    }
    assert expected_cols.issubset(set(df.columns))

    # 5. Apply regime filter
    regime_cfg = config.raw.get("regime_filter", {})
    # Only pass keys that match the function signature
    regime_params = {
        k: v for k, v in regime_cfg.items()
        if k in {"adx_threshold", "hurst_threshold", "atr_relative_std_threshold", "atr_window"}
    }
    df = apply_regime_filter(df, **regime_params)
    assert "regime_ok" in df.columns
    cov = regime_coverage(df)
    assert 0.0 <= cov <= 100.0

    # 6. Simulate some fake trade returns for metrics
    n_trades = 20
    fake_returns = pd.Series(
        np.random.choice([0.008, -0.005, 0.012, -0.003, 0.006], size=n_trades)
    )
    equity = (1 + fake_returns).cumprod() * config.get("account.equity", 10_000)

    metrics = calculate_all_metrics(
        fake_returns, equity, periods_per_year=252 * 26  # ~26 bars/day at 15min
    )

    # Sanity checks
    assert metrics["total_trades"] == n_trades
    assert 0.0 <= metrics["win_rate"] <= 1.0
    assert metrics["max_drawdown"] <= 0.0
    assert "sharpe_ratio" in metrics
    assert "sortino_ratio" in metrics

    # Smoke test print_metrics (doesn't raise)
    print_metrics(metrics)


def test_pipeline_with_flat_prices():
    """Edge case: flat prices should not crash the pipeline."""
    idx = pd.date_range("2024-01-08 10:00", periods=100, freq="15min")
    df = pd.DataFrame(
        {
            "open": [100.0] * 100,
            "high": [100.2] * 100,
            "low": [99.8] * 100,
            "close": [100.0] * 100,
            "volume": [1000] * 100,
        },
        index=idx,
    )
    cleaned = clean_data(df)
    df = build_all_indicators(cleaned)
    df = apply_regime_filter(df)

    # With flat prices Hurst is NaN and zscore is 0 — should not crash
    assert "regime_ok" in df.columns
    # All regime_ok should be False because Hurst is NaN
    assert df["regime_ok"].isna().sum() > 0 or (df["regime_ok"] == False).any()

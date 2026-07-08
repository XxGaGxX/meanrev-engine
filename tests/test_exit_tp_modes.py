"""
Tests for signals.exit.simulate_exit tp_mode handling.

Three TP modes are exposed by ``simulate_exit`` (and propagated through
``simulate_all_trades`` via the ``exit`` config block):

* ``"zscore"`` (default) — original behavior: TP fires when z-score
  reverts to 0 on a bar close.
* ``"atr_target"`` — fixed profit target at +N*ATR from entry. The
  fill price is the target price (NOT the bar close), so callers
  always see the exact stop/target hit.
* ``"none"`` — no TP; rely on SL / time stop / regime stop.

Validation: ``simulate_all_trades`` rejects unknown ``tp_mode`` values
before iterating signals so a typo fails fast at the boundary.
"""
import numpy as np
import pandas as pd
import pytest

from signals.exit import simulate_all_trades, simulate_exit


@pytest.fixture
def trending_up_df():
    """30-bar synthetic uptrend: close 100 → 105, ADX always 30 (trending),
    zscore goes from -3 to +2 (crosses 0 around bar 18)."""
    n = 30
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = np.linspace(100.0, 105.0, n)
    return pd.DataFrame({
        "open": close.copy(),
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": np.full(n, 1000.0),
        "atr": np.full(n, 2.0, dtype=float),
        "adx": np.full(n, 30.0, dtype=float),
        "regime_ok": np.full(n, True, dtype=bool),
        "zscore": np.linspace(-3.0, 2.0, n),
    }, index=idx)


@pytest.fixture
def trending_down_df():
    """30-bar synthetic downtrend: close 105 → 100, ADX always 30,
    zscore goes from +2 to -3 (crosses 0 around bar 18)."""
    n = 30
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = np.linspace(105.0, 100.0, n)
    return pd.DataFrame({
        "open": close.copy(),
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": np.full(n, 1000.0),
        "atr": np.full(n, 2.0, dtype=float),
        "adx": np.full(n, 30.0, dtype=float),
        "regime_ok": np.full(n, True, dtype=bool),
        "zscore": np.linspace(2.0, -3.0, n),
    }, index=idx)


def test_tp_zscore_default_fires_when_zscore_crosses_zero(trending_up_df):
    """tp_mode='zscore' (default) — TP fires when zscore reverts to 0 on bar close."""
    result = simulate_exit(
        trending_up_df, entry_idx=0, direction=1,
        atr_multiplier=2.0, max_bars=30, adx_stop_threshold=40.0,
    )
    assert result["exit_reason"] == "tp"


def test_tp_atr_target_long_triggers_at_target_price(trending_up_df):
    """tp_mode='atr_target', tp_atr_target=1.0 → entry=T+1 open≈100.17, target≈102.17."""
    result = simulate_exit(
        trending_up_df, entry_idx=0, direction=1,
        atr_multiplier=2.0, max_bars=30, adx_stop_threshold=40.0,
        tp_mode="atr_target", tp_atr_target=1.0,
    )
    assert result["exit_reason"] == "tp"
    # Realistic-fill: entry_price = T+1 open (~100.17), not signal-bar close (100).
    # target = round(100.17 + 2.0 * 1.0, 1) ≈ 102.17
    assert result["exit_price"] == pytest.approx(102.17, abs=0.02)


def test_tp_atr_target_short_triggers_at_target_price(trending_down_df):
    """Short entry on downtrend: entry=T+1 open≈104.83, target≈102.83."""
    result = simulate_exit(
        trending_down_df, entry_idx=0, direction=-1,
        atr_multiplier=2.0, max_bars=30, adx_stop_threshold=40.0,
        tp_mode="atr_target", tp_atr_target=1.0,
    )
    assert result["exit_reason"] == "tp"
    # Realistic-fill: entry = T+1 open (~104.83), not signal-bar close (105).
    # target = round(104.83 - 2.0 * 1.0, 1) ≈ 102.83
    assert result["exit_price"] == pytest.approx(102.83, abs=0.02)


def test_tp_none_still_exits_via_time_stop(trending_up_df):
    """tp_mode='none', max_bars=10 → time stop fires (not TP)."""
    result = simulate_exit(
        trending_up_df, entry_idx=0, direction=1,
        atr_multiplier=2.0, max_bars=10, adx_stop_threshold=40.0,
        tp_mode="none",
    )
    assert result["exit_reason"] == "time"
    assert result["exit_idx"] == 10


def test_simulate_all_trades_rejects_invalid_tp_mode(trending_up_df):
    """``simulate_all_trades`` raises ValueError on unknown tp_mode values."""
    df = trending_up_df.copy()
    df["signal_long"] = False
    df["signal_short"] = False
    df.loc[df.index[0], "signal_long"] = True
    with pytest.raises(ValueError, match="tp_mode"):
        simulate_all_trades(df, cfg={"tp_mode": "invalid_mode"})


def test_tp_atr_target_propagates_through_simulate_all_trades(trending_up_df):
    """``simulate_all_trades`` reads tp_mode from cfg and forwards to ``simulate_exit``."""
    df = trending_up_df.copy()
    df["signal_long"] = False
    df["signal_short"] = False
    df.loc[df.index[0], "signal_long"] = True
    trades = simulate_all_trades(df, cfg={
        "tp_mode": "atr_target", "tp_atr_target": 1.0,
        "atr_multiplier": 2.0, "max_bars": 30, "adx_stop_threshold": 40.0,
    })
    assert len(trades) == 1
    assert trades["exit_reason"].iloc[0] == "tp"
    # Realistic-fill: entry = T+1 open (~100.17), target ≈ 102.17.
    assert trades["exit_price"].iloc[0] == pytest.approx(102.17, abs=0.02)


def test_tp_zscore_explicit_value_matches_default(trending_up_df):
    """Passing tp_mode='zscore' explicitly returns identical result to the default."""
    explicit = simulate_exit(
        trending_up_df, entry_idx=0, direction=1,
        atr_multiplier=2.0, max_bars=30, adx_stop_threshold=40.0,
        tp_mode="zscore",
    )
    default = simulate_exit(
        trending_up_df, entry_idx=0, direction=1,
        atr_multiplier=2.0, max_bars=30, adx_stop_threshold=40.0,
    )
    assert explicit["exit_reason"] == default["exit_reason"]
    assert explicit["exit_idx"] == default["exit_idx"]


def test_regime_stop_false_bypasses_regime_exit(trending_up_df):
    """With ``regime_stop=False``, ADX > adx_stop_threshold does NOT trigger exit.
    The fixture has ADX=30; passing ``adx_stop_threshold=20`` (well below 30)
    with ``regime_stop=False`` should still reach the time stop."""
    result = simulate_exit(
        trending_up_df, entry_idx=0, direction=1,
        atr_multiplier=2.0, max_bars=10, adx_stop_threshold=20.0,
        tp_mode="none", regime_stop=False,
    )
    assert result["exit_reason"] == "time"
    assert result["exit_idx"] == 10

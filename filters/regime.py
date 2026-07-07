"""
Regime Filter Module — Mean Reversion Intraday
===============================================
Level 1 of the strategy: decides WHETHER to trade.

A good regime filter eliminates ~80% of bad trades before the entry
even fires. This module combines three independent measures:

1. ADX < threshold       → weak trend (range-bound likely)
2. Hurst < 0.45          → statistically mean-reverting series
3. ATR relative < 2σ     → exclude anomalous volatility spikes

Usage:
    df = apply_regime_filter(df, adx_threshold=22, hurst_threshold=0.45)
    df["regime_ok"]  # True = safe to trade mean reversion
"""

import numpy as np
import pandas as pd


def apply_regime_filter(
    df: pd.DataFrame,
    adx_threshold: float = 22.0,
    hurst_threshold: float = 0.45,
    atr_relative_std_threshold: float = 2.0,
    atr_window: int = 20,
) -> pd.DataFrame:
    """
    Apply the combined regime filter to a DataFrame.

    Required columns in `df`:
        - 'adx'   (from indicators.adx.add_adx)
        - 'hurst' (from indicators.hurst.add_hurst)
        - 'atr'   (from indicators.atr.add_atr)
        - 'close'

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing indicator columns.
    adx_threshold : float
        Max ADX value allowed for mean-reversion regime.
    hurst_threshold : float
        Max Hurst exponent allowed (H < 0.5 = mean-reverting).
    atr_relative_std_threshold : float
        Exclude bars where ATR% exceeds this many std devs from rolling mean.
    atr_window : int
        Rolling window for ATR% mean/std calculation.

    Returns
    -------
    pd.DataFrame
        Copy of df with added columns:
            - 'atr_rel'    : ATR as % of close price
            - 'atr_rel_z'  : Z-score of ATR% relative to its rolling history
            - 'regime_ok'  : Boolean flag (True = trade allowed)
    """
    df = df.copy()

    # ATR relative = ATR / close (volatility as fraction of price)
    df["atr_rel"] = df["atr"] / df["close"]

    # Rolling z-score of ATR relative to detect anomalous volatility
    atr_rel_mean = df["atr_rel"].rolling(window=atr_window, min_periods=atr_window).mean()
    atr_rel_std = df["atr_rel"].rolling(window=atr_window, min_periods=atr_window).std()

    # Protect against division by zero when ATR is constant
    df["atr_rel_z"] = np.where(
        atr_rel_std != 0,
        (df["atr_rel"] - atr_rel_mean) / atr_rel_std,
        0.0,
    )

    # Combined regime filter
    df["regime_ok"] = (
        (df["adx"] < adx_threshold)
        & (df["hurst"] < hurst_threshold)
        & (df["atr_rel_z"] < atr_relative_std_threshold)
    )

    return df


def regime_coverage(df: pd.DataFrame) -> float:
    """
    Return the percentage of bars where regime_ok=True.
    Useful for validating that the filter is neither too restrictive
    nor too permissive.
    """
    return df["regime_ok"].mean() * 100

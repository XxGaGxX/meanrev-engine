"""
Entry Signal Module — Mean Reversion Intraday
==============================================
Level 2 of the strategy: decides WHEN to enter.

Generates long and short entry signals based on a triple confirmation:
1. Regime filter allows trading (regime_ok=True)
2. RSI extreme (oversold for long, overbought for short)
3. Price touches Bollinger Band outer band
4. Z-score extreme confirms statistical deviation
5. Volume spike confirms genuine interest (optional)

Usage:
    from signals.entry import generate_entry_signals
    df = generate_entry_signals(df)
    df["signal_long"]   # True at bars where a long entry fires
    df["signal_short"]  # True at bars where a short entry fires
"""

from typing import Dict, Any, Optional

import numpy as np
import pandas as pd

_REQUIRED_COLS = {
    "close",
    "rsi",
    "bb_upper",
    "bb_lower",
    "zscore",
    "vol_confirm",
    "regime_ok",
}


def generate_entry_signals(
    df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Generate long and short entry signal columns.

    Required columns in `df`:
        - 'close', 'rsi', 'bb_upper', 'bb_lower', 'zscore'
        - 'vol_confirm' (from indicators/volume.add_volume_filter)
        - 'regime_ok'   (from filters/regime.apply_regime_filter)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with all indicator and regime filter columns.
    cfg : dict, optional
        Configuration overrides for thresholds. If None, config.yaml defaults
        or sensible hard-coded defaults are used.

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'signal_long' and 'signal_short' boolean columns.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"generate_entry_signals missing required columns: {missing}")

    cfg = cfg or {}

    # Thresholds — allow config overrides, fall back to defaults
    oversold = cfg.get("oversold", 30)
    overbought = cfg.get("overbought", 70)
    z_threshold = cfg.get("z_threshold", 2.0)
    use_volume = cfg.get("use_volume_confirm", True)

    df = df.copy()

    # Long entry: oversold + below lower BB + zscore < -threshold + volume + regime
    long_cond = (
        df["regime_ok"]
        & (df["rsi"] < oversold)
        & (df["close"] < df["bb_lower"])
        & (df["zscore"] < -z_threshold)
    )
    if use_volume:
        long_cond = long_cond & df["vol_confirm"]

    # Short entry: overbought + above upper BB + zscore > threshold + volume + regime
    short_cond = (
        df["regime_ok"]
        & (df["rsi"] > overbought)
        & (df["close"] > df["bb_upper"])
        & (df["zscore"] > z_threshold)
    )
    if use_volume:
        short_cond = short_cond & df["vol_confirm"]

    # Explicitly treat NaN as False so signals never fire on missing data
    df["signal_long"] = long_cond.fillna(False)
    df["signal_short"] = short_cond.fillna(False)

    return df


def signal_counts(df: pd.DataFrame) -> Dict[str, int]:
    """
    Return the number of long and short signals in the DataFrame.
    """
    return {
        "long_signals": int(df["signal_long"].sum()),
        "short_signals": int(df["signal_short"].sum()),
        "total_signals": int(df["signal_long"].sum() + df["signal_short"].sum()),
    }


def validate_signal_count(
    df: pd.DataFrame, min_signals: int = 30, per_asset: bool = False
) -> bool:
    """
    Check whether the DataFrame contains enough signals for statistical validity.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'signal_long' and 'signal_short' columns.
    min_signals : int
        Minimum total signals required.
    per_asset : bool
        If True, min_signals applies per symbol (requires MultiIndex level 'symbol').

    Returns
    -------
    bool
        True if signal count meets the minimum threshold.
    """
    if per_asset and "symbol" in df.index.names:
        for symbol in df.index.get_level_values("symbol").unique():
            sym_df = df.xs(symbol, level="symbol")
            total = int(sym_df["signal_long"].sum() + sym_df["signal_short"].sum())
            if total < min_signals:
                return False
        return True

    total = int(df["signal_long"].sum() + df["signal_short"].sum())
    return total >= min_signals

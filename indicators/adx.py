"""
ADX Indicator Module
====================
Average Directional Index — measures trend strength (not direction).
Used in the regime filter to detect trending vs. range-bound markets.
"""

import pandas as pd
import talib

_REQUIRED_COLS = {"high", "low", "close"}


def add_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add ADX column to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'high', 'low', 'close' columns.
    period : int
        Lookback period (default 14).

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'adx' column.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"add_adx missing required columns: {missing}")
    df = df.copy()
    df["adx"] = talib.ADX(
        df["high"], df["low"], df["close"], timeperiod=period
    )
    return df

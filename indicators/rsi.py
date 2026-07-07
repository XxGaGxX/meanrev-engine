"""
RSI Indicator Module
====================
Relative Strength Index — momentum oscillator 0-100.
Identifies overbought (>70) and oversold (<30) conditions.
"""

import pandas as pd
import talib

_REQUIRED_COLS = {"close"}


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add RSI column to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'close' column.
    period : int
        Lookback period (default 14).

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'rsi' column.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"add_rsi missing required columns: {missing}")
    df = df.copy()
    df["rsi"] = talib.RSI(df["close"], timeperiod=period)
    return df

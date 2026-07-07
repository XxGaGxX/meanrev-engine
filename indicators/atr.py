"""
ATR Indicator Module
====================
Average True Range — measures recent volatility in absolute price terms.
Used for adaptive stop-loss placement and position sizing.
"""

import pandas as pd
import talib

_REQUIRED_COLS = {"high", "low", "close"}


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add ATR column to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'high', 'low', 'close' columns.
    period : int
        Lookback period (default 14).

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'atr' column.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"add_atr missing required columns: {missing}")
    df = df.copy()
    df["atr"] = talib.ATR(
        df["high"], df["low"], df["close"], timeperiod=period
    )
    return df

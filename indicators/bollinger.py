"""
Bollinger Bands Indicator Module
==================================
Quantifies how far price has deviated from the mean in absolute
statistical terms (±2σ). Second independent confirmation for entry signals.
"""

import pandas as pd
import talib

_REQUIRED_COLS = {"close"}


def add_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """
    Add Bollinger Bands columns to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'close' column.
    period : int
        SMA lookback period (default 20).
    std_dev : float
        Number of standard deviations (default 2.0).

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'bb_upper', 'bb_mid', 'bb_lower' columns.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"add_bollinger missing required columns: {missing}")
    df = df.copy()
    upper, middle, lower = talib.BBANDS(
        df["close"],
        timeperiod=period,
        nbdevup=std_dev,
        nbdevdn=std_dev,
    )
    df["bb_upper"] = upper
    df["bb_mid"] = middle
    df["bb_lower"] = lower
    return df

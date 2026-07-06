"""
Z-Score Indicator Module
========================
Normalizes price deviation from the rolling mean in terms of
standard deviations. Makes deviation comparable across assets
with different price levels. Also used as the take-profit criterion.
"""

import numpy as np
import pandas as pd

_REQUIRED_COLS = {"close"}


def add_zscore(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    Add rolling Z-score column to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'close' column.
    window : int
        Rolling window for mean and std (default 20).

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'zscore' column.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"add_zscore missing required columns: {missing}")
    df = df.copy()
    rolling_mean = df["close"].rolling(window=window, min_periods=window).mean()
    rolling_std = df["close"].rolling(window=window, min_periods=window).std()
    df["zscore"] = np.where(
        rolling_std != 0,
        (df["close"] - rolling_mean) / rolling_std,
        0.0,
    )
    return df

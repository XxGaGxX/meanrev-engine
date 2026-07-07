"""
Volume Filter Indicator Module
==============================
Flags bars where current volume exceeds a multiple of the rolling
average volume. Separates genuine overreactions from low-volume noise.
"""

import pandas as pd

_REQUIRED_COLS = {"volume"}


def add_volume_filter(
    df: pd.DataFrame, window: int = 20, multiplier: float = 1.5
) -> pd.DataFrame:
    """
    Add volume confirmation column to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'volume' column.
    window : int
        Rolling window for average volume (default 20).
    multiplier : float
        Current volume must exceed avg * multiplier (default 1.5).

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'vol_avg' and 'vol_confirm' columns.
    """
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"add_volume_filter missing required columns: {missing}")
    df = df.copy()
    df["vol_avg"] = df["volume"].rolling(window=window, min_periods=window).mean()
    df["vol_confirm"] = df["volume"] > (df["vol_avg"] * multiplier)
    return df

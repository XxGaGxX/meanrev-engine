"""
Data Clean & Align Module — Mean Reversion Intraday
====================================================
Utilities for cleaning, validating, and aligning multi-asset OHLCV data.
"""

from typing import Dict, List

import pandas as pd


REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a single OHLCV DataFrame.

    Steps:
    1. Validate required columns exist.
    2. Remove duplicate timestamps.
    3. Drop rows with NaN values.
    4. Remove rows with zero volume (market closed / halted).
    5. Sort by index (timestamp).
    """
    df = df.copy()

    # Validate columns
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Remove duplicate timestamps (keep first)
    df = df[~df.index.duplicated(keep="first")]

    # Drop incomplete rows
    df = df.dropna()

    # Remove zero-volume bars (halted / closed)
    df = df[df["volume"] > 0]

    # Sort by timestamp
    df = df.sort_index()

    return df


def align_data(data_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Align multiple DataFrames to a common timestamp index.

    This is essential for multi-asset risk management (correlation,
    aggregate exposure) where all series must share the same timestamps.
    """
    common_index = None
    for df in data_dict.values():
        common_index = df.index if common_index is None else common_index.intersection(df.index)

    if common_index is None or len(common_index) == 0:
        raise ValueError("No common timestamps found across assets.")

    return {sym: df.loc[common_index].copy() for sym, df in data_dict.items()}


def validate_data(data_dict: Dict[str, pd.DataFrame]) -> Dict[str, dict]:
    """
    Run validation checks on the full dataset and return a report.

    Returns a dict with per-asset stats: row count, date range, missing %.
    """
    report = {}
    for symbol, df in data_dict.items():
        report[symbol] = {
            "rows": len(df),
            "start": df.index.min(),
            "end": df.index.max(),
            "missing_pct": df.isna().mean().mean() * 100,
        }
    return report


def filter_session_hours(
    df: pd.DataFrame,
    skip_first_minutes: int = 30,
    skip_last_minutes: int = 30,
    market_open: str = "09:30",
    market_close: str = "16:00",
) -> pd.DataFrame:
    """
    Filter out the first and last N minutes of each trading session.

    Parameters
    ----------
    skip_first_minutes : int
        Minutes to skip after market open.
    skip_last_minutes : int
        Minutes to skip before market close.
    market_open : str
        Market open time (HH:MM, America/New_York assumed).
    market_close : str
        Market close time (HH:MM, America/New_York assumed).
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be a DatetimeIndex.")

    # Exclude weekends
    df = df[df.index.dayofweek < 5]

    # Exclude pre-market and after-hours (keep only regular hours 09:30–16:00)
    regular_open = pd.Timestamp(market_open).time()
    regular_close = pd.Timestamp(market_close).time()
    times = df.index.time
    in_regular_hours = (times >= regular_open) & (times <= regular_close)
    df = df.loc[in_regular_hours].copy()

    first_cutoff = (pd.Timestamp(market_open) + pd.Timedelta(minutes=skip_first_minutes)).time()
    last_cutoff = (pd.Timestamp(market_close) - pd.Timedelta(minutes=skip_last_minutes)).time()

    mask = (df.index.time >= first_cutoff) & (df.index.time <= last_cutoff)
    return df.loc[mask].copy()

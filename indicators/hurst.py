"""
Hurst Exponent Module
=====================
Measures whether a price series is mean-reverting (H < 0.5),
random walk (H ≈ 0.5), or trending/persistent (H > 0.5).
Used in the regime filter alongside ADX.

Note: Hurst is a regime indicator, not an entry signal.
It should be recalculated periodically, not on every tick.

Performance note:
    The rolling Hurst calculation is CPU-intensive because each window
    re-runs the R/S analysis in pure Python. For large datasets consider
    computing Hurst only every N bars and forward-filling, or using
    a vectorized implementation (e.g., numba, Cython).
"""

import numpy as np
import pandas as pd

_REQUIRED_COLS = {"close"}


def _hurst_single(ts: np.ndarray, min_lag: int = 2, max_lag: int = 100) -> float:
    """Calculate Hurst exponent for a single 1-D array."""
    lags = range(min_lag, min(max_lag, len(ts) // 2))
    tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
    # Filter out zero std values to avoid log(0) = -inf
    valid = [(lag, t) for lag, t in zip(lags, tau) if t > 0]
    if len(valid) < 2:
        return np.nan
    valid_lags, valid_tau = zip(*valid)
    poly = np.polyfit(np.log(valid_lags), np.log(valid_tau), 1)
    return poly[0] * 2.0


def _add_hurst_col(
    df: pd.DataFrame,
    col_name: str,
    window: int,
    min_lag: int,
    max_lag: int,
) -> pd.DataFrame:
    """Internal helper: add a rolling Hurst column with given window."""
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Hurst calculation missing required columns: {missing}")
    df = df.copy()
    df[col_name] = (
        df["close"]
        .rolling(window=window, min_periods=window)
        .apply(lambda x: _hurst_single(x.values, min_lag, max_lag), raw=False)
    )
    return df


def add_hurst(
    df: pd.DataFrame, window: int = 252, min_lag: int = 2, max_lag: int = 100
) -> pd.DataFrame:
    """
    Add rolling Hurst Exponent column to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'close' column.
    window : int
        Rolling window size (default 252 ~ 9 trading days at 15-min bars).
    min_lag : int
        Minimum lag for the R/S calculation.
    max_lag : int
        Maximum lag for the R/S calculation.

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'hurst' column.
    """
    return _add_hurst_col(df, "hurst", window, min_lag, max_lag)


def add_hurst_fast(
    df: pd.DataFrame,
    window: int = 50,
    min_lag: int = 2,
    max_lag: int = 20,
) -> pd.DataFrame:
    """
    Add a fast Hurst Exponent column for intraday micro-structure.

    ``window=50`` (~2 trading days at 15-min bars) captures short-term
    mean-reverting behaviour that the slow Hurst (window=252, ~9 days)
    may miss inside a broader trending regime.

    Use ``hurst_fast`` as the entry-gate filter; keep ``hurst`` as a
    structural-regime diagnostic.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'close' column.
    window : int
        Rolling window size (default 50 ~ 2 trading days at 15-min bars).
    min_lag : int
        Minimum lag for the R/S calculation.
    max_lag : int
        Maximum lag for the R/S calculation (reduced for shorter window).

    Returns
    -------
    pd.DataFrame
        Copy of df with added 'hurst_fast' column.
    """
    return _add_hurst_col(df, "hurst_fast", window, min_lag, max_lag)

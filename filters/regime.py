"""
Regime Filter Module — Mean Reversion Intraday
===============================================
Level 1 of the strategy: decides WHETHER to trade.

A good regime filter eliminates ~80% of bad trades before the entry
even fires. This module combines three independent measures:

1. ADX < threshold       → weak trend (range-bound likely)
2. Hurst < 0.5           → statistically mean-reverting series
3. ATR relative < 2σ     → exclude anomalous volatility spikes

Usage:
    df = apply_regime_filter(df, adx_threshold=25, hurst_threshold=0.55)
    df["regime_ok"]  # True = safe to trade mean reversion
"""

from typing import Dict

import numpy as np
import pandas as pd


def _score_component(value: pd.Series, threshold) -> pd.Series:
    """
    Normalize a component to [0, 1] where 1 = perfect and 0 = at or
    beyond the threshold. Lower raw values = better (all three regime
    components are upper-bound filters).

    ``threshold`` can be a float or a per-bar ``pd.Series`` (used by
    adaptive Hurst).
    """
    return (1.0 - value / threshold).clip(0.0, 1.0)


def _adaptive_hurst_threshold(
    hurst_slow: pd.Series,
    base_threshold: float,
    strong_trend_h: float,
    tight_threshold: float,
    range_h: float,
    relax_threshold: float,
) -> pd.Series:
    """
    Compute a per-bar Hurst threshold driven by the slow (structural)
    Hurst exponent.

    * ``hurst_slow > strong_trend_h``  → strong trend   → tighten
    * ``hurst_slow < range_h``        → range-bound    → relax
    * otherwise                       → use ``base_threshold``

    Parameters
    ----------
    hurst_slow : pd.Series
        Slow Hurst (window=252) values per bar.
    base_threshold : float
        Default Hurst threshold (e.g. 0.55).
    strong_trend_h : float
        Hurst slow above this value triggers tightening.
    tight_threshold : float
        Threshold applied when Hurst slow > strong_trend_h.
    range_h : float
        Hurst slow below this value triggers relaxation.
    relax_threshold : float
        Threshold applied when Hurst slow < range_h.

    Returns
    -------
    pd.Series
        Per-bar threshold, same index as ``hurst_slow``.
    """
    thr = pd.Series(base_threshold, index=hurst_slow.index, dtype=float)
    thr[hurst_slow > strong_trend_h] = tight_threshold
    thr[hurst_slow < range_h] = relax_threshold
    return thr


def apply_regime_filter(
    df: pd.DataFrame,
    adx_threshold: float = 22.0,
    hurst_threshold: float = 0.45,
    atr_relative_std_threshold: float = 2.0,
    atr_window: int = 20,
    use_fast_hurst: bool = True,
    soft_scoring: bool = False,
    score_adx_weight: float = 0.40,
    score_hurst_weight: float = 0.40,
    score_atr_weight: float = 0.20,
    score_threshold: float = 0.50,
    adaptive_hurst: bool = False,
    adaptive_strong_trend_h: float = 0.60,
    adaptive_tight_threshold: float = 0.45,
    adaptive_range_h: float = 0.50,
    adaptive_relax_threshold: float = 0.55,
) -> pd.DataFrame:
    """
    Apply the combined regime filter to a DataFrame.

    Supports two modes:

    **Binary mode** (``soft_scoring=False``, default):
        ``regime_ok`` = True only when ALL three components pass
        their individual thresholds (AND logic).

    **Soft scoring mode** (``soft_scoring=True``):
        Each component is normalised to [0, 1] and combined via
        weighted sum::

            regime_score = w_adx × adx_score
                         + w_hurst × hurst_score
                         + w_atr × atr_score

        ``regime_ok`` = True when ``regime_score ≥ score_threshold``.
        This allows strong ADX (score ≈ 1) to compensate for a
        marginal Hurst (score ≈ 0.4) — a setup the binary AND
        would reject.

    **Adaptive Hurst mode** (``adaptive_hurst=True``):
        The Hurst threshold becomes per-bar, driven by the slow
        (structural) Hurst exponent (window=252). This couples the
        two Hurst windows intelligently:

        * ``hurst_slow > strong_trend_h`` → tighten to ``tight_threshold``
        * ``hurst_slow < range_h``       → relax to ``relax_threshold``
        * otherwise                      → use ``hurst_threshold``

        In a strong macro trend you want to be *more* selective about
        intraday pullbacks (tighten).  In a range-bound regime you can
        afford to be *less* selective (relax).

    Required columns in `df`:
        - 'adx'         (from indicators.adx.add_adx)
        - 'hurst'       (from indicators.hurst.add_hurst, window=252)
        - 'hurst_fast'  (from indicators.hurst.add_hurst_fast, window=50)
        - 'atr'         (from indicators.atr.add_atr)
        - 'close'

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing indicator columns.
    adx_threshold : float
        Max ADX value allowed (default 22, relaxed to 25).
    hurst_threshold : float
        Max Hurst exponent allowed (default 0.45, relaxed to 0.55).
    atr_relative_std_threshold : float
        Exclude bars where ATR% exceeds this many std devs.
    atr_window : int
        Rolling window for ATR% mean/std calculation.
    use_fast_hurst : bool
        Use ``hurst_fast`` (window=50) for the entry gate.
    soft_scoring : bool
        When True, use weighted scoring instead of binary AND.
    score_adx_weight : float
        Weight for ADX component in soft scoring (default 0.40).
    score_hurst_weight : float
        Weight for Hurst component in soft scoring (default 0.40).
    score_atr_weight : float
        Weight for ATR component in soft scoring (default 0.20).
    score_threshold : float
        Minimum aggregated score to set ``regime_ok`` (default 0.50).
    adaptive_hurst : bool
        When True, the Hurst threshold becomes per-bar, driven by the
        slow Hurst (window=252).
    adaptive_strong_trend_h : float
        Slow Hurst above this value triggers tightening (default 0.60).
    adaptive_tight_threshold : float
        Fast Hurst threshold when slow Hurst > strong_trend_h (default 0.45).
    adaptive_range_h : float
        Slow Hurst below this value triggers relaxation (default 0.50).
    adaptive_relax_threshold : float
        Fast Hurst threshold when slow Hurst < range_h (default 0.55).

    Returns
    -------
    pd.DataFrame
        Copy of df with added columns:
            - 'atr_rel'       : ATR as % of close price
            - 'atr_rel_z'     : Z-score of ATR% relative to history
            - 'regime_ok'     : Boolean flag
        When ``soft_scoring=True``, also adds:
            - 'regime_score'  : Aggregated score [0, 1]
            - 'adx_score'     : ADX component score [0, 1]
            - 'hurst_score'   : Hurst component score [0, 1]
            - 'atr_score'     : ATR component score [0, 1]
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

    # Select Hurst column
    hurst_col = "hurst_fast" if (use_fast_hurst and "hurst_fast" in df.columns) else "hurst"

    # Adaptive Hurst threshold: couple fast (intraday) and slow (structural)
    # Hurst so the entry gate tightens in strong trends and relaxes in ranges.
    if adaptive_hurst and "hurst" in df.columns:
        hurst_thr = _adaptive_hurst_threshold(
            df["hurst"],
            base_threshold=hurst_threshold,
            strong_trend_h=adaptive_strong_trend_h,
            tight_threshold=adaptive_tight_threshold,
            range_h=adaptive_range_h,
            relax_threshold=adaptive_relax_threshold,
        )
    else:
        hurst_thr = hurst_threshold

    if soft_scoring:
        # ── Soft (weighted) scoring ──────────────────────────────
        df["adx_score"] = _score_component(df["adx"], adx_threshold)
        df["hurst_score"] = _score_component(df[hurst_col], hurst_thr)
        df["atr_score"] = _score_component(
            df["atr_rel_z"], atr_relative_std_threshold
        )
        df["regime_score"] = (
            score_adx_weight * df["adx_score"]
            + score_hurst_weight * df["hurst_score"]
            + score_atr_weight * df["atr_score"]
        )
        df["regime_ok"] = df["regime_score"] >= score_threshold
    else:
        # ── Binary (AND) scoring — original logic ───────────────
        df["regime_ok"] = (
            (df["adx"] < adx_threshold)
            & (df[hurst_col] < hurst_thr)
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


def regime_component_breakdown(
    df: pd.DataFrame,
    adx_threshold: float = 22.0,
    hurst_threshold: float = 0.45,
    atr_relative_std_threshold: float = 2.0,
) -> Dict[str, float]:
    """
    Return the pass rate of each regime filter component.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns ``adx``, ``hurst``, ``hurst_fast``
        (optional), ``atr_rel_z``, and ``regime_ok``. Typically the
        output of :func:`apply_regime_filter`.
    adx_threshold : float
        The same threshold used when ``regime_ok`` was computed.
    hurst_threshold : float
        The same threshold used when ``regime_ok`` was computed.
    atr_relative_std_threshold : float
        The same threshold used when ``regime_ok`` was computed.

    Returns
    -------
    dict
        {
            "adx_pass_pct": float,          # % bars where ADX < threshold
            "hurst_pass_pct": float,        # % bars where slow Hurst < threshold
            "hurst_fast_pass_pct": float,   # % bars where fast Hurst < threshold
                                            # (only present when hurst_fast exists)
            "atr_rel_z_pass_pct": float,    # % bars where ATR z-score < threshold
            "all_pass_pct": float,          # % bars where ALL three pass (= regime_ok)
            "n_bars": int,                  # total bars evaluated
        }

    Raises
    ------
    ValueError
        If required columns are missing from ``df``.
    """
    needed = {"adx", "hurst", "atr_rel_z", "regime_ok"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing columns for regime breakdown: {sorted(missing)}"
        )

    n = len(df)
    if n == 0:
        result: Dict[str, float] = {
            "adx_pass_pct": 0.0,
            "hurst_pass_pct": 0.0,
            "atr_rel_z_pass_pct": 0.0,
            "all_pass_pct": 0.0,
            "n_bars": 0,
        }
        if "hurst_fast" in df.columns:
            result["hurst_fast_pass_pct"] = 0.0
        return result

    result = {
        "adx_pass_pct": float((df["adx"] < adx_threshold).mean() * 100),
        "hurst_pass_pct": float((df["hurst"] < hurst_threshold).mean() * 100),
        "atr_rel_z_pass_pct": float(
            (df["atr_rel_z"] < atr_relative_std_threshold).mean() * 100
        ),
        "all_pass_pct": float(df["regime_ok"].mean() * 100),
        "n_bars": n,
    }
    # Fast Hurst breakdown — present when the column exists
    if "hurst_fast" in df.columns:
        result["hurst_fast_pass_pct"] = float(
            (df["hurst_fast"] < hurst_threshold).mean() * 100
        )
    # Soft scoring diagnostics — present when regime_score column exists
    if "regime_score" in df.columns:
        result["mean_regime_score"] = float(
            df["regime_score"].mean()
        )
        for col, key in (
            ("adx_score", "mean_adx_score"),
            ("hurst_score", "mean_hurst_score"),
            ("atr_score", "mean_atr_score"),
        ):
            if col in df.columns:
                result[key] = float(df[col].mean())
    return result

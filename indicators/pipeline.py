"""
Indicators Pipeline — Mean Reversion Intraday
==============================================
Single entry point to compute all indicators in the correct order.

Usage:
    from indicators.pipeline import build_all_indicators
    df = build_all_indicators(df, cfg=config.raw.get("indicators"))
"""

from typing import Any, Dict, Optional

import pandas as pd

from .adx import add_adx
from .atr import add_atr
from .bollinger import add_bollinger
from .hurst import add_hurst
from .rsi import add_rsi
from .volume import add_volume_filter
from .zscore import add_zscore


def build_all_indicators(
    df: pd.DataFrame, cfg: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Compute all indicators in the correct dependency order.

    Parameters
    ----------
    df : pd.DataFrame
        Clean OHLCV data.
    cfg : dict, optional
        Indicator parameters (e.g., from config.yaml). If None, defaults are used.

    Returns
    -------
    pd.DataFrame
        DataFrame with all indicator columns appended.
    """
    cfg = cfg or {}

    adx_cfg = {k: v for k, v in cfg.get("adx", {}).items() if k in {"period"}}
    hurst_cfg = {k: v for k, v in cfg.get("hurst", {}).items() if k in {"window", "min_lag", "max_lag"}}
    rsi_cfg = {k: v for k, v in cfg.get("rsi", {}).items() if k in {"period"}}
    bb_cfg = {k: v for k, v in cfg.get("bollinger", {}).items() if k in {"period", "std_dev"}}
    z_cfg = {k: v for k, v in cfg.get("zscore", {}).items() if k in {"window"}}
    vol_cfg = {k: v for k, v in cfg.get("volume", {}).items() if k in {"window", "multiplier"}}
    atr_cfg = {k: v for k, v in cfg.get("atr", {}).items() if k in {"period"}}

    df = add_adx(df, **adx_cfg)
    df = add_hurst(df, **hurst_cfg)
    df = add_rsi(df, **rsi_cfg)
    df = add_bollinger(df, **bb_cfg)
    df = add_zscore(df, **z_cfg)
    df = add_volume_filter(df, **vol_cfg)
    df = add_atr(df, **atr_cfg)

    return df

"""
Metrics Module — Mean Reversion Intraday
=========================================
Performance metrics for backtest and live trade evaluation.

Key metrics:
- Win Rate
- Profit Factor
- Sharpe Ratio
- Sortino Ratio
- Expectancy
- Max Drawdown
- Kelly Criterion
"""

from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd


def win_rate(trade_returns: pd.Series) -> float:
    """Percentage of winning trades."""
    if len(trade_returns) == 0:
        return 0.0
    return (trade_returns > 0).mean()


def profit_factor(trade_returns: pd.Series) -> float:
    """Gross profit / gross loss. Must be > 1.3–1.5 after costs."""
    gross_profit = trade_returns[trade_returns > 0].sum()
    gross_loss = abs(trade_returns[trade_returns < 0].sum())
    if gross_loss == 0:
        return np.inf if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """
    Annualized Sharpe Ratio.

    Parameters
    ----------
    returns : pd.Series
        Period returns (e.g., daily trade returns or equity curve diffs).
    risk_free_rate : float
        Annual risk-free rate.
    periods_per_year : int
        Number of periods in a year (252 for daily, ~1008 for 15-min bars).
    """
    if returns.std() == 0:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    return excess.mean() / excess.std() * np.sqrt(periods_per_year)


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """
    Annualized Sortino Ratio (penalizes only downside volatility).
    More relevant for mean-reversion strategies.
    """
    downside = returns[returns < 0]
    if len(downside) == 0 or downside.std() == 0:
        return np.inf
    excess = returns.mean() - risk_free_rate / periods_per_year
    return excess / downside.std() * np.sqrt(periods_per_year)


def expectancy(trade_returns: pd.Series) -> float:
    """
    Expected profit per trade:
    E = (Win% × Avg Win) − (Loss% × Avg Loss)
    """
    if len(trade_returns) == 0:
        return 0.0
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]
    wr = win_rate(trade_returns)
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    return wr * avg_win - (1 - wr) * avg_loss


def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Maximum peak-to-trough decline (as a negative fraction).
    """
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    return drawdown.min()


def max_drawdown_bars(equity_curve: pd.Series) -> int:
    """
    Maximum number of consecutive bars (index positions) in drawdown.

    Note: This counts index positions, not elapsed time. For time-based
    duration, use the datetime index directly.
    """
    running_max = equity_curve.cummax()
    in_drawdown = equity_curve < running_max
    if not in_drawdown.any():
        return 0

    # Group consecutive True values and count max length
    groups = (in_drawdown != in_drawdown.shift()).cumsum()
    durations = in_drawdown.groupby(groups).sum()
    return int(durations.max())


def max_drawdown_duration(*args, **kwargs) -> int:
    """Deprecated — use max_drawdown_bars instead."""
    import warnings
    warnings.warn(
        "max_drawdown_duration is deprecated; use max_drawdown_bars",
        DeprecationWarning,
        stacklevel=2,
    )
    return max_drawdown_bars(*args, **kwargs)


def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float, fraction: float = 0.25) -> float:
    """
    Fractional Kelly Criterion.

    Parameters
    ----------
    win_rate : float
        Probability of winning.
    avg_win : float
        Average win amount.
    avg_loss : float
        Average loss amount (positive value).
    fraction : float
        Kelly fraction (1/4 or 1/2 Kelly recommended).
    """
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    kelly_pct = win_rate - ((1 - win_rate) / b)
    return max(0.0, kelly_pct * fraction)


def calculate_all_metrics(
    trade_returns: pd.Series,
    equity: pd.Series,
    periods_per_year: Optional[int] = None,
    equity_mtm: Optional[pd.Series] = None,
) -> Dict[str, Any]:
    """
    Compute the full metrics suite from a trade log.

    Trade-level metrics (win rate, profit factor, expectancy) are always computed.
    Time-series metrics (Sharpe, Sortino) require `periods_per_year` to be set.
    When `equity_mtm` (per-bar mark-to-market curve) is provided, it is used
    for Sharpe/Sortino and drawdown; otherwise the trade-exit `equity` curve is
    used for backward compatibility.

    Parameters
    ----------
    trade_returns : pd.Series
        Per-trade or periodic returns (as fractions, e.g., 0.01 = 1%).
    equity : pd.Series
        Equity curve (cumulative value over time, trade-exit points).
    periods_per_year : int, optional
        Number of periods per year. Required for Sharpe/Sortino.
        Examples: 252 (daily), ~5500 (15-min bars).
    equity_mtm : pd.Series, optional
        Per-bar mark-to-market equity curve. When provided, Sharpe/Sortino
        and max_drawdown are computed from this curve, capturing intra-trade
        drawdown and realistic periodic returns.

    Returns
    -------
    dict
        Dictionary of all computed metrics.
    """
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]

    metrics = {
        "total_trades": len(trade_returns),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": win_rate(trade_returns),
        "profit_factor": profit_factor(trade_returns),
        "avg_win": wins.mean() if len(wins) > 0 else 0.0,
        "avg_loss": abs(losses.mean()) if len(losses) > 0 else 0.0,
        "expectancy": expectancy(trade_returns),
        # max_drawdown, max_drawdown_bars, total_return are set below
        # from curve_for_dd (MTM when available, else trade-exit equity).
    }

    # Drawdown: prefer per-bar MTM curve when available (captures intra-trade
    # drawdown), otherwise fall back to trade-exit equity curve.
    curve_for_dd = equity_mtm if (equity_mtm is not None and len(equity_mtm) > 1) else equity
    metrics["max_drawdown"] = max_drawdown(curve_for_dd)
    metrics["max_drawdown_bars"] = max_drawdown_bars(curve_for_dd)
    metrics["total_return"] = (
        curve_for_dd.iloc[-1] / curve_for_dd.iloc[0] - 1
        if len(curve_for_dd) > 1 else 0.0
    )

    # Time-series metrics (Sharpe/Sortino): prefer MTM curve when available,
    # fall back to trade-exit equity curve for backward compatibility.
    # Guard: only compute when trades actually occurred — a flat MTM curve
    # with no P&L variation should not produce spurious Sharpe/Sortino.
    curve_for_ts = equity_mtm if (equity_mtm is not None and len(equity_mtm) > 1) else equity
    if periods_per_year is not None and len(curve_for_ts) > 1 and metrics["total_trades"] > 0:
        periodic_returns = curve_for_ts.pct_change().dropna()
        if len(periodic_returns) > 0 and periodic_returns.std() > 0:
            metrics["sharpe_ratio"] = sharpe_ratio(periodic_returns, periods_per_year=periods_per_year)
            metrics["sortino_ratio"] = sortino_ratio(periodic_returns, periods_per_year=periods_per_year)

    if metrics["avg_loss"] > 0:
        metrics["kelly_fraction"] = kelly_criterion(
            metrics["win_rate"], metrics["avg_win"], metrics["avg_loss"]
        )

    return metrics


def print_metrics(metrics: Dict[str, Any]) -> None:
    """Pretty-print metrics to console."""
    print("=" * 50)
    print("STRATEGY PERFORMANCE METRICS")
    print("=" * 50)
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key:<25}: {value:>12.4f}")
        else:
            print(f"  {key:<25}: {value:>12}")
    print("=" * 50)

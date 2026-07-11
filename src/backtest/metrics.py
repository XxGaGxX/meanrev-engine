"""Phase 5 — Backtest metrics (pure functions over a trade list).

Computes the MVP-success metrics from ROADMAP_MVP.md:
  - win_rate, profit_factor, total_pnl, n_trades
  - sharpe (annualized, std-based; 0 if <2 trades)

All inputs are TradeResult from src.backtest.engine. No IO, no state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import math


@dataclass(frozen=True)
class Metrics:
    n_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    sharpe: float
    avg_pnl: float
    equity_curve: List[float]      # equity = initial_capital + cumsum(pnl)
    max_drawdown: float            # max peak-to-trough decline (0..1+)


def compute_metrics(trades: Sequence["object"], initial_capital: float = 0.0) -> Metrics:
    """Aggregate a list of TradeResult into Metrics.

    trades: iterable of objects with a numeric `.pnl` attribute.
    initial_capital: starting equity; the curve is capital + cumsum(pnl),
        so max_drawdown is a real peak-to-trough % on equity (not on P&L
        from zero, which is undefined when equity goes negative).
    """
    pnls = [float(t.pnl) for t in trades]
    n = len(pnls)
    if n == 0:
        return Metrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, [initial_capital], 0.0)

    total = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    win_rate = len(wins) / n if n else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )
    avg = total / n

    # Annualized Sharpe: mean/std * sqrt(252). Single trade -> 0.
    if n >= 2:
        mean = total / n
        var = sum((p - mean) ** 2 for p in pnls) / (n - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        sharpe = (mean / std) * math.sqrt(252.0) if std > 0 else 0.0
    else:
        sharpe = 0.0

    # Equity curve + max drawdown on capital (not P&L from zero)
    equity: List[float] = []
    peak = initial_capital
    max_dd = 0.0
    running = initial_capital
    for p in pnls:
        running += p
        equity.append(running)
        peak = max(peak, running)
        dd = (peak - running) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    return Metrics(
        n_trades=n,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_pnl=total,
        sharpe=sharpe,
        avg_pnl=avg,
        equity_curve=equity,
        max_drawdown=max_dd,
    )

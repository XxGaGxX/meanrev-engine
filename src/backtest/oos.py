"""Fase 6 OOS — statistical significance + in/out-sample comparison.

Why this module exists (quant algorithmic best practice, gaps in Fase 5):
  Fase 5 reported point-estimate Sharpe / PF. Those can be lucky noise on
  a few trades. A real OOS gate needs:
    - a confidence interval on Sharpe (bootstrap), not just the point est
    - a p-value (P(bootstrapped Sharpe <= 0)) so we reject "no edge"
    - an explicit overfitting flag: OOS Sharpe < degrade_threshold *
      in-sample Sharpe (the roadmap's "OOS much worse => overfit" rule)

All pure, numpy only, deterministic via `seed`. No IO, no state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np

from src.backtest.engine import TradeResult


@dataclass(frozen=True)
class Significance:
    sharpe: float
    sharpe_ci_low: float
    sharpe_ci_high: float
    p_value: float           # P(bootstrap sharpe <= 0)
    n_trades: int
    n_bootstrap: int


@dataclass(frozen=True)
class OOSSummary:
    in_sample: Significance
    out_of_sample: Significance
    degrade_threshold: float = 0.5
    overfit_flag: bool = False
    passed: bool = False


def _annualized_sharpe(pnls: np.ndarray) -> float:
    n = len(pnls)
    if n < 2:
        return 0.0
    mean = pnls.mean()
    std = pnls.std(ddof=1)
    if std == 0:
        return 0.0
    return float((mean / std) * np.sqrt(252.0))


def significance(
    trades: Sequence[TradeResult],
    n_bootstrap: int = 500,
    seed: int = 0,
) -> Significance:
    """Bootstrap the per-trade P&L to get a Sharpe CI + p-value.

    trades: sequence of TradeResult (uses .pnl).
    n_bootstrap: number of resamples (with replacement).
    seed: RNG seed for reproducibility.
    """
    pnls = np.array([float(t.pnl) for t in trades], dtype=float)
    n = len(pnls)
    if n == 0:
        return Significance(0.0, 0.0, 0.0, 1.0, 0, n_bootstrap)

    base_sharpe = _annualized_sharpe(pnls)
    rng = np.random.default_rng(seed)
    boot = np.empty(n_bootstrap, dtype=float)
    for b in range(n_bootstrap):
        sample = rng.choice(pnls, size=n, replace=True)
        boot[b] = _annualized_sharpe(sample)
    ci_low = float(np.percentile(boot, 2.5))
    ci_high = float(np.percentile(boot, 97.5))
    p_value = float(np.mean(boot <= 0.0))
    return Significance(base_sharpe, ci_low, ci_high, p_value, n, n_bootstrap)


def aggregate_trades(per_ticker: Sequence[Sequence[TradeResult]]) -> List[TradeResult]:
    """Flatten per-ticker trade lists into one combined list (portfolio
    level equity / DD). Order within a ticker is preserved; tickers are
    concatenated. Per-trade pnl sign is untouched."""
    out: List[TradeResult] = []
    for lst in per_ticker:
        out.extend(lst)
    return out


def summarize(
    in_sample: Significance,
    out_of_sample: Significance,
    degrade_threshold: float = 0.5,
) -> OOSSummary:
    """Apply the roadmap OOS gate:
      - passed  = OOS Sharpe > 0 AND p_value < 0.05 AND not overfit
      - overfit = OOS Sharpe < degrade_threshold * in-sample Sharpe
    """
    overfit = out_of_sample.sharpe < degrade_threshold * in_sample.sharpe
    passed = (
        out_of_sample.sharpe > 0
        and out_of_sample.p_value < 0.05
        and not overfit
    )
    return OOSSummary(in_sample, out_of_sample, degrade_threshold, overfit, passed)

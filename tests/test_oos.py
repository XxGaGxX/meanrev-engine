"""Tests for Fase 6 OOS metrics extensions: statistical significance.

Contract (quant algorithmic best practice, added for Fase 6):
  - significance(trades, n_bootstrap) returns a dataclass with:
      sharpe, sharpe_ci_low, sharpe_ci_high (95% bootstrap perc),
      p_value (frac of bootstrap Sharpe <= 0),
      n_trades
  - The OOS gate is Sharpe>0 AND p_value<0.05 (not just point estimate),
    so a lucky few-trade run cannot fake an edge.
  - aggregate_trades(list_of_lists) flattens per-ticker trades into one
    equity curve (portfolio-level DD), preserving per-trade pnl sign.

Pure, numpy only for the bootstrap; no IO.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.backtest.metrics import compute_metrics
from src.backtest.engine import TradeResult, ExitReason
from src.backtest.oos import significance, aggregate_trades, OOSSummary, summarize


def _trades(pnls):
    return [TradeResult(p, ExitReason.TP_FULL, 100.0, 3) for p in pnls]


def test_significance_positive_edge() -> None:
    # clearly positive edge -> CI above 0, p<0.05
    rng = np.random.default_rng(42)
    pnls = rng.normal(0.4, 1.0, 400).tolist()
    s = significance(_trades(pnls), n_bootstrap=200, seed=1)
    assert s.sharpe > 0
    assert s.sharpe_ci_low > 0          # whole CI above zero
    assert s.p_value < 0.05
    assert s.n_trades == 400


def test_significance_zero_edge() -> None:
    # pure noise -> NOT statistically significant (p >= 0.05)
    rng = np.random.default_rng(7)
    pnls = rng.normal(0.0, 1.0, 400).tolist()
    s = significance(_trades(pnls), n_bootstrap=200, seed=2)
    assert s.p_value >= 0.05  # cannot reject "no edge"


def test_significance_reproducible() -> None:
    rng = np.random.default_rng(0)
    pnls = rng.normal(0.3, 1.0, 300).tolist()
    a = significance(_trades(pnls), n_bootstrap=100, seed=99)
    b = significance(_trades(pnls), n_bootstrap=100, seed=99)
    assert a.sharpe == pytest.approx(b.sharpe)
    assert a.p_value == pytest.approx(b.p_value)


def test_aggregate_trades_flattens() -> None:
    # two tickers, disjoint trade lists -> one combined list
    t1 = _trades([1.0, -0.5, 2.0])
    t2 = _trades([0.5, -1.0])
    combined = aggregate_trades([t1, t2])
    assert len(combined) == 5
    # metrics on combined must equal per-trade pnl sum
    m = compute_metrics(combined, initial_capital=100.0)
    assert m.total_pnl == pytest.approx(1.0 - 0.5 + 2.0 + 0.5 - 1.0)


def test_oos_summary_compares_in_and_out() -> None:
    """OOSSummary must flag overfitting when OOS Sharpe < half in-sample.
    Use noisy P&L (std>0) so Sharpe is well-defined."""
    rng = np.random.default_rng(3)
    ins = significance(_trades((rng.normal(0.5, 1.0, 300)).tolist()), n_bootstrap=50, seed=1)   # +edge
    oos = significance(_trades((rng.normal(-0.1, 1.0, 300)).tolist()), n_bootstrap=50, seed=1)  # -edge
    summ = summarize(ins, oos, degrade_threshold=0.5)
    assert summ.out_of_sample.sharpe < summ.in_sample.sharpe * 0.5
    assert summ.overfit_flag is True
    assert summ.passed is False  # gate fails

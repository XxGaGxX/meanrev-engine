"""Unit tests for metrics module."""

import numpy as np
import pandas as pd
import pytest

from utils.metrics import (
    calculate_all_metrics,
    expectancy,
    kelly_criterion,
    max_drawdown,
    max_drawdown_bars,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)


class TestWinRate:
    def test_all_wins(self):
        s = pd.Series([0.01, 0.02, 0.01])
        assert win_rate(s) == 1.0

    def test_empty(self):
        assert win_rate(pd.Series([], dtype=float)) == 0.0


class TestProfitFactor:
    def test_positive(self):
        s = pd.Series([0.01, -0.005, 0.02])
        assert profit_factor(s) == 0.03 / 0.005

    def test_no_losses(self):
        s = pd.Series([0.01, 0.02])
        assert profit_factor(s) == np.inf


class TestExpectancy:
    def test_positive(self):
        s = pd.Series([0.01, -0.005, 0.02])
        assert expectancy(s) > 0

    def test_empty(self):
        assert expectancy(pd.Series([], dtype=float)) == 0.0


class TestMaxDrawdown:
    def test_known_curve(self):
        equity = pd.Series([100, 110, 105, 120])
        assert max_drawdown(equity) == (105 - 110) / 110

    def test_no_drawdown(self):
        equity = pd.Series([100, 110, 120])
        assert max_drawdown(equity) == 0.0


class TestMaxDrawdownBars:
    def test_known_curve(self):
        equity = pd.Series([100, 110, 105, 104, 120])
        assert max_drawdown_bars(equity) == 2  # 110 -> 105 -> 104


class TestSharpeRatio:
    def test_zero_std(self):
        s = pd.Series([0.0, 0.0, 0.0])
        assert sharpe_ratio(s) == 0.0

    def test_positive(self):
        np.random.seed(0)
        s = pd.Series(np.random.normal(0.001, 0.01, 100))
        assert sharpe_ratio(s) > -5  # loose sanity check


class TestSortinoRatio:
    def test_no_downside(self):
        s = pd.Series([0.01, 0.02, 0.01])
        assert sortino_ratio(s) == np.inf


class TestKelly:
    def test_typical(self):
        k = kelly_criterion(win_rate=0.6, avg_win=100, avg_loss=50)
        assert 0 < k < 1

    def test_zero_loss(self):
        assert kelly_criterion(0.6, 100, 0) == 0.0


class TestCalculateAllMetrics:
    def test_basic(self):
        trade_returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.015])
        equity = (1 + trade_returns).cumprod() * 10000
        metrics = calculate_all_metrics(trade_returns, equity)
        assert metrics["total_trades"] == 5
        assert metrics["win_rate"] == 0.6
        assert "max_drawdown" in metrics
        assert "max_drawdown_bars" in metrics

    def test_with_periods_per_year(self):
        np.random.seed(1)
        trade_returns = pd.Series(np.random.normal(0.001, 0.01, 50))
        equity = (1 + trade_returns).cumprod() * 10000
        metrics = calculate_all_metrics(trade_returns, equity, periods_per_year=252)
        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        # Sharpe should be computed from equity pct_change, not trade returns
        assert not np.isnan(metrics["sharpe_ratio"])

    def test_backward_compat_without_mtm(self):
        """equity_mtm=None must preserve existing behavior."""
        trade_returns = pd.Series([0.01, -0.005, 0.02])
        equity = pd.Series([10000, 10100, 10050, 10251])
        metrics = calculate_all_metrics(
            trade_returns, equity, periods_per_year=252, equity_mtm=None,
        )
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        # Total return computed from equity (not MTM)
        assert metrics["total_return"] == pytest.approx(
            equity.iloc[-1] / equity.iloc[0] - 1, rel=1e-9,
        )

    def test_with_mtm_changes_sharpe_sortino(self):
        """Providing equity_mtm must produce different (more realistic) Sharpe."""
        trade_returns = pd.Series([0.03, -0.01, 0.02])
        # Sparse equity: only 4 points (3 trade exits)
        equity = pd.Series([10000, 10300, 10197, 10401])
        # Dense MTM: 10 bars showing intra-trade drawdown
        equity_mtm = pd.Series([
            10000, 10050, 9500, 10000, 10300,  # massive drawdown mid-trade
            10200, 10197, 10100, 10300, 10401,
        ])

        metrics_no_mtm = calculate_all_metrics(
            trade_returns, equity, periods_per_year=252, equity_mtm=None,
        )
        metrics_with_mtm = calculate_all_metrics(
            trade_returns, equity, periods_per_year=252, equity_mtm=equity_mtm,
        )
        # MTM curve captures intra-trade drawdown → lower Sharpe
        assert metrics_with_mtm["sharpe_ratio"] < metrics_no_mtm["sharpe_ratio"]
        # MTM drawdown includes intra-trade decline
        assert metrics_with_mtm["max_drawdown"] < metrics_no_mtm["max_drawdown"]

    def test_no_trades_omits_sharpe_even_with_mtm(self):
        """With zero trades, Sharpe/Sortino must be omitted even if MTM present."""
        trade_returns = pd.Series(dtype=float)  # empty
        equity = pd.Series([10000.0])
        equity_mtm = pd.Series([10000.0] * 10)  # flat MTM, but no trades
        metrics = calculate_all_metrics(
            trade_returns, equity, periods_per_year=252, equity_mtm=equity_mtm,
        )
        assert "sharpe_ratio" not in metrics
        assert "sortino_ratio" not in metrics

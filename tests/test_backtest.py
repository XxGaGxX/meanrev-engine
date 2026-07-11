"""Tests for Phase 5 backtest engine — trade simulation + metrics (TDD).

Contract (docs/specs §3.2, §5 + ROADMAP_MVP.md Phase 5):
  - simulate_trade builds the exit decision from a PositionPlan + the
    bars AFTER entry (chronological). Order of checks per bar:
      1. partial TP (tp_partial_price) -> take partial_tp_frac out
      2. full TP (tp_price) -> remaining closes at tp
      3. SL (sl_price) -> full stop
      4. time_stop_bars reached -> exit at that bar's close (caps loss)
      5. end of data -> forced exit at last close (EOD, no overnight)
  - No look-ahead: only bars strictly after entry are consumed.
  - metrics: win_rate, profit_factor, total_return, n_trades, sharpe.

Pure functions, no IO. Uses src.strategy.risk.PositionPlan.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.strategy.risk import PositionPlan, Direction
from src.backtest.engine import simulate_trade, TradeResult, ExitReason
from src.backtest.metrics import compute_metrics


def _plan(direction="LONG", entry=99.85, sl=99.2, tp=100.0, tpp=100.1,
          frac=0.5, time_stop=None, size=100):
    return PositionPlan(
        direction=Direction(direction), entry_price=entry, sl_price=sl,
        tp_price=tp, tp_partial_price=tpp, partial_tp_frac=frac,
        time_stop_bars=time_stop, size=size,
    )


def _bars(*closes):
    return pd.DataFrame({"close": list(closes)})


# --- simulate_trade: exit reasons ---


def test_simulate_tp_full_reached() -> None:
    plan = _plan()
    bars = _bars(99.9, 100.05, 100.2)  # hits tp 100.0 at bar 2
    res = simulate_trade(plan, bars)
    assert res.exit_reason is ExitReason.TP_FULL
    # partial at 100.1? no, 100.1 not reached before tp 100.0
    assert res.exit_price == pytest.approx(100.0)


def test_simulate_partial_then_full() -> None:
    plan = _plan()  # tp_partial 100.1, tp 100.0
    # bar1 reaches partial 100.1 first, bar2 reaches full 100.0
    bars = _bars(100.15, 100.05)
    res = simulate_trade(plan, bars)
    assert res.exit_reason is ExitReason.TP_FULL
    # eff price: 0.5*100.1 + 0.5*100.0
    assert res.exit_price == pytest.approx(100.05)


def test_simulate_sl_hit() -> None:
    plan = _plan()
    bars = _bars(99.5, 99.0)  # hits sl 99.2 at bar1
    res = simulate_trade(plan, bars)
    assert res.exit_reason is ExitReason.SL
    assert res.exit_price == pytest.approx(99.2)


def test_simulate_time_stop_caps_loss() -> None:
    # price drifts but never hits TP or SL; time_stop=2 -> exit at bar2 close
    plan = _plan(time_stop=2)
    bars = _bars(99.6, 99.55)  # between sl(99.2) and tp(100), no trigger
    res = simulate_trade(plan, bars)
    assert res.exit_reason is ExitReason.TIME_STOP
    assert res.exit_price == pytest.approx(99.55)
    assert res.bars_held == 2


def test_simulate_eod_forced_exit() -> None:
    plan = _plan(time_stop=None)
    bars = _bars(99.7, 99.75)  # no trigger, no time stop -> EOD
    res = simulate_trade(plan, bars)
    assert res.exit_reason is ExitReason.EOD
    assert res.exit_price == pytest.approx(99.75)


def test_simulate_short_mirrors() -> None:
    plan = _plan(direction="SHORT", entry=100.15, sl=100.8, tp=100.0,
                 tpp=99.9, frac=0.5)
    # price rises to sl 100.8
    bars = _bars(100.5, 100.9)
    res = simulate_trade(plan, bars)
    assert res.exit_reason is ExitReason.SL
    assert res.exit_price == pytest.approx(100.8)


def test_simulate_no_look_ahead() -> None:
    # The result must not depend on bars BEFORE entry. We pass only
    # post-entry bars, so this is structural; just assert it runs and
    # exits per the post-entry sequence.
    plan = _plan(time_stop=1)
    bars = _bars(99.6)
    res = simulate_trade(plan, bars)
    assert res.exit_reason is ExitReason.TIME_STOP


# --- metrics ---


def test_metrics_win_rate_and_pf() -> None:
    trades = [
        TradeResult(10.0, ExitReason.TP_FULL, 100.0, 3),
        TradeResult(-5.0, ExitReason.SL, 99.2, 2),
        TradeResult(8.0, ExitReason.TP_FULL, 100.0, 4),
    ]
    m = compute_metrics(trades)
    assert m.n_trades == 3
    assert m.win_rate == pytest.approx(2 / 3)
    # PF = gross_profit / gross_loss = 18 / 5 = 3.6
    assert m.profit_factor == pytest.approx(3.6)
    assert m.total_pnl == pytest.approx(13.0)


def test_metrics_empty() -> None:
    m = compute_metrics([])
    assert m.n_trades == 0
    assert m.win_rate == 0.0
    assert m.profit_factor == 0.0


def test_metrics_sharpe_zero_when_single() -> None:
    trades = [TradeResult(5.0, ExitReason.TP_FULL, 100.0, 2)]
    m = compute_metrics(trades)
    assert m.sharpe == 0.0  # single trade -> std undefined

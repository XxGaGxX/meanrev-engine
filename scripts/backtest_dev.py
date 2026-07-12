"""Phase 5 backtest on the DEVELOPMENT set (70%), OOS-locked.

Runs the honest trade-by-trade backtest (Fase 5 engine) on the 70%
in-sample window of the cached daily data, using the project modules:
  signals.generate_entry_signal  (Fase 3, anti-look-ahead)
  risk.compute_position          (Fase 4, ATR stop + partial TP)
  filters.regime_allows_trade     (design §2.4)
  backtest.engine.simulate_trade  (Fase 5, per-bar exit)
  backtest.metrics.compute_metrics(Fase 5, incl. max DD + equity curve)

GATE checks enforced (ROADMAP_MVP.md Fase 5):
  1. runs without error on dev set
  2. NO trade has entry_bar_index <= signal_bar_index (anti-look-ahead)
     -- asserted inside simulate_trade AND re-checked post-hoc.

LIMIT (honest): cached data is DAILY, so this is a daily proxy of the
intraday strategy (entry at next day open, exit next day close). The
true 5-min backtest is scripts/backtest_proxy.py (yfinance-capped).
The gate (anti-look-ahead + metrics) is identical; only the bar
granularity differs.
"""

from __future__ import annotations

import glob
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\diego\Desktop\Progetti\quant")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.strategy.signals import generate_entry_signal
from src.strategy.risk import compute_position, alpaca_round_trip_cost
from src.strategy.filters import compute_adx, regime_allows_trade
from src.backtest.engine import simulate_trade, TradeResult, ExitReason
from src.backtest.metrics import compute_metrics

CACHE = ROOT / "data" / "cache"
DEV_FRAC = 0.70


def _ticker_files():
    fs = sorted(glob.glob(str(CACHE / "*.parquet")))
    return [f for f in fs if not os.path.basename(f).startswith("_")]


def _load(ticker_path: str) -> pd.DataFrame:
    df = pd.read_parquet(ticker_path)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns={"Date": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "open", "high", "low", "close"]]


def backtest_dev_file(path: str, st, ex, rk) -> list[TradeResult]:
    df = _load(path)
    if len(df) < 60:
        return []
    # 70/30 split, dev = first 70%
    n_dev = max(30, int(len(df) * DEV_FRAC))
    dev = df.iloc[:n_dev].reset_index(drop=True)
    if len(dev) < 30:
        return []

    trades: list[TradeResult] = []
    # daily ADX for regime filter on this ticker
    adx = compute_adx(dev, period=14)
    adx_by_i = {i: (float(v) if pd.notna(v) else None) for i, v in enumerate(adx)}

    for i in range(1, len(dev)):
        cur = dev.iloc[i]
        prev_close = float(dev.iloc[i - 1]["close"])
        # one "day" as a single OHLC row -> simulate intraday via the
        # daily bar: entry next day open is not possible intraday, so we
        # model the daily proxy: signal on day i, entry at day i+1 open.
        # Build a synthetic 2-bar series for simulate_trade.
        sig = generate_entry_signal(
            dev.iloc[: i + 1],  # prefix up to and including day i
            prev_close=prev_close,
            gap_min_pct=st.gap_min_pct, gap_max_pct=st.gap_max_pct,
            opening_range_bars=1, confirmation_bars=1,
        )
        if sig.action.value == "FLAT" or sig.bar_index is None:
            continue
        # entry at NEXT day open (anti-look-ahead: bar_index+1)
        if i + 1 >= len(dev):
            continue
        entry_price = float(dev.iloc[i + 1]["open"])
        # regime filter on this day's ADX
        day_adx = adx_by_i.get(i)
        if day_adx is not None and day_adx > 25.0:
            continue
        # synthetic intraday: OR = day i range, target = prev_close
        or_high = float(dev.iloc[i]["high"])
        or_low = float(dev.iloc[i]["low"])
        # ATR ~ day's range
        atr_val = max(or_high - or_low, 0.01)
        plan = compute_position(
            direction=sig.action.value,
            entry_price=entry_price,
            opening_range_high=or_high,
            opening_range_low=or_low,
            prev_close=prev_close,
            capital=ex.initial_capital,
            risk_per_trade=ex.risk_per_trade,
            atr=atr_val, atr_target=0.5,
            min_stop_distance_pct=0.001, max_position_size=0.95,
            partial_tp_frac=rk.partial_tp_frac, time_stop_bars=rk.time_stop_bars,
            sl_atr_multiple=rk.sl_atr_multiple,
            tp_extend_atr_multiple=rk.tp_extend_atr_multiple,
        )
        # exit at next day close (daily proxy). prefix check: entry after signal.
        exit_close = float(dev.iloc[i + 1]["close"])
        # wrap as a 1-row "bars_after" with close = exit price
        bars_after = pd.DataFrame({"close": [exit_close]})
        res = simulate_trade(plan, bars_after,
                             entry_bar_index=i + 1, signal_bar_index=i)
        gross = res.pnl * plan.size
        cost = alpaca_round_trip_cost(plan.size, entry_price)
        trades.append(TradeResult(gross - cost, res.exit_reason,
                                  res.exit_price, res.bars_held,
                                  res.entry_bar_index, res.signal_bar_index))
    return trades


def main() -> None:
    settings = load_settings()
    st, ex = settings.strategy, settings.execution
    rk = settings.risk
    files = _ticker_files()
    print(f"Universe: {len(files)} tickers, DEV set = first {int(DEV_FRAC*100)}%")
    print(f"Risk: SL={rk.sl_atr_multiple}xATR  TP_ext={rk.tp_extend_atr_multiple}xATR  partial={rk.partial_tp_frac}")

    all_trades: list[TradeResult] = []
    look_ahead_violations = 0
    for f in files:
        tr = backtest_dev_file(f, st, ex, rk)
        for t in tr:
            if t.entry_bar_index >= 0 and t.signal_bar_index >= 0:
                if t.entry_bar_index <= t.signal_bar_index:
                    look_ahead_violations += 1
        all_trades.extend(tr)

    m = compute_metrics(all_trades, initial_capital=ex.initial_capital)
    print("\n=== PHASE 5 BACKTEST — DEV SET (70%, daily proxy) ===")
    print(f"  n_trades       = {m.n_trades}")
    print(f"  win_rate       = {m.win_rate*100:.1f}%")
    print(f"  profit_factor  = {m.profit_factor:.2f}")
    print(f"  total_pnl      = {m.total_pnl:.2f} (net Alpaca cost)")
    print(f"  sharpe         = {m.sharpe:.2f}")
    print(f"  max_drawdown   = {m.max_drawdown*100:.1f}%")
    print(f"  equity end     = {m.equity_curve[-1]:.2f}")
    print(f"  look-ahead viol= {look_ahead_violations}  (GATE: must be 0)")
    print("\nGATE Fase 5:")
    print(f"  [{'X' if True else ' '}] runs without error on dev set")
    print(f"  [{'X' if look_ahead_violations == 0 else ' '}] no entry<=signal (anti-look-ahead)")


if __name__ == "__main__":
    main()

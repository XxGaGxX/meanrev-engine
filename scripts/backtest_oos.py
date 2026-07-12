"""Phase 6 — Out-of-Sample checkpoint (the moment of truth).

Runs the SAME honest backtest engine as Fase 5, but on data the dev
backtest never touched:
  (A) the 30% OOS window of the cached daily data (OOS-LOCKED until Fase 6)
  (B) a SECOND, independent OOS sample: 5-min bars from yfinance (~60d,
      a different period/regime than the cached daily OOS)

Both must pass the quant OOS gate (added in Fase 6):
  - OOS Sharpe > 0  AND  bootstrap p-value < 0.05  (edge is real, not noise)
  - OOS Sharpe >= 50% of in-sample Sharpe  (no severe overfit)

The OOS lock from src/data/ohlcv.py is enforced: assert_oos_locked
raises if this script is run before Fase 6.

LIMIT (honest): cached data is DAILY (proxy); the 5-min yfinance sample
is capped ~60d and lands in a regime where mean-reversion is known to
struggle (see Fase 5 report). A clean multi-year 5-min OOS needs
Polygon/Alpaca (maintenance today — not required for THIS checkpoint).
"""

from __future__ import annotations

import glob
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(r"C:\Users\diego\Desktop\Progetti\quant")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.data.ohlcv import compute_split, assert_oos_locked
from src.strategy.signals import generate_entry_signal
from src.strategy.risk import compute_position, alpaca_round_trip_cost
from src.strategy.filters import compute_adx
from src.backtest.engine import simulate_trade, TradeResult, ExitReason
from src.backtest.metrics import compute_metrics
from src.backtest.oos import significance, aggregate_trades, summarize

CACHE = ROOT / "data" / "cache"


def _load(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns={"Date": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date").reset_index(drop=True)[
        ["date", "open", "high", "low", "close"]
    ]


def _ticker_files():
    fs = sorted(glob.glob(str(CACHE / "*.parquet")))
    return [f for f in fs if not os.path.basename(f).startswith("_")]


def backtest_oos_daily_file(path: str, st, ex, split, rk) -> list[TradeResult]:
    """Backtest ONLY the OOS window of one cached daily file."""
    df = _load(path)
    if len(df) < 60:
        return []
    oos = df[df["date"].apply(lambda d: split.in_oos_window(d))].reset_index(drop=True)
    if len(oos) < 20:
        return []

    trades: list[TradeResult] = []
    adx = compute_adx(oos, period=14)
    adx_by_i = {i: (float(v) if pd.notna(v) else None) for i, v in enumerate(adx)}
    for i in range(1, len(oos)):
        prev_close = float(oos.iloc[i - 1]["close"])
        sig = generate_entry_signal(
            oos.iloc[: i + 1], prev_close=prev_close,
            gap_min_pct=st.gap_min_pct, gap_max_pct=st.gap_max_pct,
            opening_range_bars=1, confirmation_bars=1,
        )
        if sig.action.value == "FLAT" or sig.bar_index is None:
            continue
        if i + 1 >= len(oos):
            continue
        entry_price = float(oos.iloc[i + 1]["open"])
        if (adx_by_i.get(i) or 0) > 25.0:
            continue
        or_high = float(oos.iloc[i]["high"]); or_low = float(oos.iloc[i]["low"])
        atr_val = max(or_high - or_low, 0.01)
        plan = compute_position(
            direction=sig.action.value, entry_price=entry_price,
            opening_range_high=or_high, opening_range_low=or_low,
            prev_close=prev_close, capital=ex.initial_capital,
            risk_per_trade=ex.risk_per_trade, atr=atr_val, atr_target=0.5,
            min_stop_distance_pct=0.001, max_position_size=0.95,
            partial_tp_frac=rk.partial_tp_frac, time_stop_bars=rk.time_stop_bars,
            sl_atr_multiple=rk.sl_atr_multiple,
            tp_extend_atr_multiple=rk.tp_extend_atr_multiple,
        )
        exit_close = float(oos.iloc[i + 1]["close"])
        res = simulate_trade(plan, pd.DataFrame({"close": [exit_close]}),
                             entry_bar_index=i + 1, signal_bar_index=i)
        gross = res.pnl * plan.size
        cost = alpaca_round_trip_cost(plan.size, entry_price)
        trades.append(TradeResult(gross - cost, res.exit_reason, res.exit_price,
                                  res.bars_held, res.entry_bar_index, res.signal_bar_index))
    return trades


def backtest_oos_5min(ticker: str, st, ex, rk, days: int = 59) -> list[TradeResult]:
    """Independent OOS sample: 5-min bars from yfinance (different period)."""
    df = yf.download(ticker, period=f"{days}d", interval="5m",
                    progress=False, auto_adjust=False)
    if df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    df = df.rename(columns={"datetime": "datetime"})[
        ["datetime", "open", "high", "low", "close"]
    ].copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["day"] = df["datetime"].dt.date
    trades: list[TradeResult] = []
    for d, g in df.groupby("day"):
        g = g.sort_values("datetime").reset_index(drop=True)
        if len(g) < 3:
            continue
        prev_close = float(g["close"].iloc[-1]) if False else None
        # prev_close = last close of the PREVIOUS available day
    # build prev_close map
    days_sorted = sorted(df["day"].unique())
    prev_map = {}
    last = None
    for d in days_sorted:
        sub = df[df["day"] == d].sort_values("datetime")
        if last is not None:
            prev_map[d] = last
        last = float(sub["close"].iloc[-1])
    for d, g in df.groupby("day"):
        if d not in prev_map:
            continue
        prev_close = prev_map[d]
        sig = generate_entry_signal(
            g, prev_close=prev_close,
            gap_min_pct=st.gap_min_pct, gap_max_pct=st.gap_max_pct,
            opening_range_bars=st.opening_range_bars,
            confirmation_bars=st.confirmation_bars,
        )
        if sig.action.value == "FLAT" or sig.bar_index is None:
            continue
        ei = sig.bar_index + 1
        if ei >= len(g):
            continue
        entry_price = float(g.iloc[ei]["open"])
        or_high = float(g.iloc[:st.opening_range_bars]["high"].max())
        or_low = float(g.iloc[:st.opening_range_bars]["low"].min())
        tr = (g["high"] - g["low"]).combine(
            (g["high"] - g["close"].shift()).abs(), max).combine(
            (g["low"] - g["close"].shift()).abs(), max)
        atr_val = float(tr.iloc[:ei].mean()) if ei > 0 else 0.5
        if atr_val <= 0:
            atr_val = float((g["high"] - g["low"]).iloc[:ei].mean()) if ei > 0 else 0.5
        plan = compute_position(
            direction=sig.action.value, entry_price=entry_price,
            opening_range_high=or_high, opening_range_low=or_low,
            prev_close=prev_close, capital=ex.initial_capital,
            risk_per_trade=ex.risk_per_trade, atr=atr_val, atr_target=0.5,
            min_stop_distance_pct=0.001, max_position_size=0.95,
            partial_tp_frac=rk.partial_tp_frac, time_stop_bars=rk.time_stop_bars or 30,
            sl_atr_multiple=rk.sl_atr_multiple,
            tp_extend_atr_multiple=rk.tp_extend_atr_multiple,
        )
        after = g.iloc[ei + 1:].reset_index(drop=True)
        if len(after) == 0:
            continue
        res = simulate_trade(plan, after[["close"]])
        gross = res.pnl * plan.size
        cost = alpaca_round_trip_cost(plan.size, entry_price)
        trades.append(TradeResult(gross - cost, res.exit_reason, res.exit_price,
                                  res.bars_held, res.entry_bar_index, res.signal_bar_index))
    return trades


def main() -> None:
    from scripts.backtest_dev import backtest_dev_file  # reuse dev backtest
    settings = load_settings()
    st, ex = settings.strategy, settings.execution
    rk = settings.risk
    split = compute_split(settings.data)
    # ENFORCE OOS lock: fails if run before Fase 6
    assert_oos_locked("Fase 6", split)
    print(f"OOS window: {split.oos_start} -> {split.oos_end}")
    print(f"Risk: SL={rk.sl_atr_multiple}xATR  TP_ext={rk.tp_extend_atr_multiple}xATR  partial={rk.partial_tp_frac}")

    # --- DEV (in-sample) for comparison ---
    dev_trades: list[TradeResult] = []
    for f in _ticker_files():
        dev_trades.extend(backtest_dev_file(f, st, ex, rk))
    dev_sig = significance(dev_trades, n_bootstrap=300, seed=11)

    # --- OOS (A) daily cached 30% ---
    oos_daily: list[TradeResult] = []
    for f in _ticker_files():
        oos_daily.extend(backtest_oos_daily_file(f, st, ex, split, rk))
    oos_daily_sig = significance(oos_daily, n_bootstrap=300, seed=12)

    # --- OOS (B) 5-min yfinance independent sample ---
    oos_5min: list[TradeResult] = []
    for t in ["AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN", "META", "GOOGL"]:
        oos_5min.extend(backtest_oos_5min(t, st, ex, rk, days=59))
    oos_5min_sig = significance(oos_5min, n_bootstrap=300, seed=13)

    print("\n=== PHASE 6 OOS CHECKPOINT ===")
    print(f"  IN-SAMPLE (dev) : Sharpe={dev_sig.sharpe:+.2f} "
          f"CI[{dev_sig.sharpe_ci_low:+.2f},{dev_sig.sharpe_ci_high:+.2f}] "
          f"p={dev_sig.p_value:.3f} n={dev_sig.n_trades}")
    print(f"  OOS daily 30%  : Sharpe={oos_daily_sig.sharpe:+.2f} "
          f"CI[{oos_daily_sig.sharpe_ci_low:+.2f},{oos_daily_sig.sharpe_ci_high:+.2f}] "
          f"p={oos_daily_sig.p_value:.3f} n={oos_daily_sig.n_trades}")
    print(f"  OOS 5min indep : Sharpe={oos_5min_sig.sharpe:+.2f} "
          f"CI[{oos_5min_sig.sharpe_ci_low:+.2f},{oos_5min_sig.sharpe_ci_high:+.2f}] "
          f"p={oos_5min_sig.p_value:.3f} n={oos_5min_sig.n_trades}")

    summ_daily = summarize(dev_sig, oos_daily_sig)
    summ_5min = summarize(dev_sig, oos_5min_sig)
    gate_pass = summ_daily.passed and summ_5min.passed

    print("\n  GATE (Sharpe>0 & p<0.05 & no overfit), both OOS samples:")
    print(f"    OOS daily  : {'PASS' if summ_daily.passed else 'FAIL'} "
          f"(overfit={summ_daily.overfit_flag})")
    print(f"    OOS 5min  : {'PASS' if summ_5min.passed else 'FAIL'} "
          f"(overfit={summ_5min.overfit_flag})")
    print(f"\n  >>> PHASE 6 GATE: {'PASS — edge holds OOS' if gate_pass else 'FAIL — stop or revisit filters'}")


if __name__ == "__main__":
    main()

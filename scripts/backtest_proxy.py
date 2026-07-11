"""Phase 5 backtest orchestrator (REAL 5-min data via yfinance, 60d cap).

End-to-end honest-ish backtest using the project's own modules:
  src.strategy.signals.generate_entry_signal  (Fase 3, anti-look-ahead)
  src.strategy.risk.compute_position         (Fase 4, R:R fix)
  src.backtest.engine.simulate_trade          (Fase 5 exit logic)
  src.backtest.metrics.compute_metrics        (Fase 5 metrics)

Per trading day with >= opening_range_bars 5-min bars:
  1. gap = (open_bar0 - prev_close)/prev_close ; filter [min,max] (Fase 3)
  2. opening range = first `opening_range_bars` bars
  3. confirmation = `confirmation_bars` closes breaking OR (Fase 3)
  4. on confirm at bar k -> entry at bar k+1 open (anti-look-ahead)
  5. build PositionPlan (risk) with time_stop + partial TP
  6. simulate exit on bars after entry (engine)
  7. net P&L with Alpaca cost (risk.alpaca_round_trip_cost)

LIMITS (honest):
  - yfinance 5-min capped ~60 days -> this is a SHORT window sanity
    check, NOT the Fase 6 OOS proof. Use it to measure whether the
    time-stop + partial-TP fix raises R:R / PF above the daily proxy.
  - No VIX/news/regime filter yet (Fase 3 note): those are Fase 5+
    enhancements; we measure the bare signal+risk first.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(r"C:\Users\diego\Desktop\Progetti\quant")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.strategy.signals import generate_entry_signal
from src.strategy.risk import compute_position, alpaca_round_trip_cost
from src.backtest.engine import simulate_trade, TradeResult


def fetch_5min(ticker: str, days: int = 59) -> pd.DataFrame:
    end = date.today()
    df = yf.download(ticker, period=f"{days}d", interval="5m",
                    progress=False, auto_adjust=False)
    if df.empty:
        return pd.DataFrame()
    # flatten MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    # keep 'datetime' + OHLC
    out = df.rename(columns={"datetime": "datetime"})[
        ["datetime", "open", "high", "low", "close"]
    ].copy()
    out["datetime"] = pd.to_datetime(out["datetime"])
    # assign a trading date (date part)
    out["day"] = out["datetime"].dt.date
    return out


def daily_groups(df: pd.DataFrame):
    for d, g in df.groupby("day"):
        g = g.sort_values("datetime").reset_index(drop=True)
        if len(g) < 3:
            continue
        yield d, g


def backtest_ticker(ticker: str, settings, days: int = 59,
                     spy_adx_by_day: dict | None = None) -> list[TradeResult]:
    st = settings.strategy
    ex = settings.execution
    df = fetch_5min(ticker, days)
    if df.empty:
        return []

    trades: list[TradeResult] = []
    # need prev_close: use prior day's last close per ticker
    days_sorted = sorted(df["day"].unique())
    # map day -> prior day close (use last close of previous available day)
    prev_close_by_day = {}
    last_close = None
    for d in days_sorted:
        day_bars = df[df["day"] == d].sort_values("datetime")
        if last_close is not None:
            prev_close_by_day[d] = last_close
        last_close = float(day_bars["close"].iloc[-1])

    for d, g in daily_groups(df):
        if d not in prev_close_by_day:
            continue
        prev_close = prev_close_by_day[d]
        # day bars need 'open'/'high'/'low'/'close' cols (already)
        sig = generate_entry_signal(
            g, prev_close=prev_close,
            gap_min_pct=st.gap_min_pct, gap_max_pct=st.gap_max_pct,
            opening_range_bars=st.opening_range_bars,
            confirmation_bars=st.confirmation_bars,
        )
        if sig.action.value == "FLAT" or sig.bar_index is None:
            continue
        # --- QUANT FIX: regime filter (design §2.4) ---
        # Skip trades in strong-trend regimes where mean reversion fails.
        spy_adx = spy_adx_by_day.get(d)
        if spy_adx is not None and spy_adx > 25.0:
            continue
        # entry at NEXT bar open (bar_index+1)
        entry_idx = sig.bar_index + 1
        if entry_idx >= len(g):
            continue
        entry_price = float(g.iloc[entry_idx]["open"])
        or_high = float(g.iloc[:st.opening_range_bars]["high"].max())
        or_low = float(g.iloc[:st.opening_range_bars]["low"].min())
        # ATR(14) on the available 5-min bars up to entry (simple true-range mean)
        tr = (g["high"] - g["low"]).combine((g["high"] - g["close"].shift()).abs(), max).combine(
            (g["low"] - g["close"].shift()).abs(), max)
        atr_val = float(tr.iloc[:entry_idx].mean()) if entry_idx > 0 else 0.5
        if atr_val <= 0 or entry_idx == 0:
            atr_val = float((g["high"] - g["low"]).iloc[:entry_idx].mean()) if entry_idx > 0 else 0.5
        plan = compute_position(
            direction=sig.action.value,
            entry_price=entry_price,
            opening_range_high=or_high,
            opening_range_low=or_low,
            prev_close=prev_close,
            capital=ex.initial_capital,
            risk_per_trade=ex.risk_per_trade,
            atr=atr_val,
            atr_target=0.5,
            min_stop_distance_pct=0.001,
            max_position_size=0.95,
            partial_tp_frac=0.5,
            time_stop_bars=30,
            sl_atr_multiple=2.0,  # QUANT FIX: volatility stop, not wide OR-low
        )
        # bars after entry
        after = g.iloc[entry_idx + 1:].reset_index(drop=True)
        if len(after) == 0:
            continue
        res = simulate_trade(plan, after[["close"]])
        # net pnl with cost
        gross = res.pnl * plan.size
        cost = alpaca_round_trip_cost(plan.size, entry_price)
        net = gross - cost
        trades.append(TradeResult(net, res.exit_reason, res.exit_price, res.bars_held))
    return trades


def main() -> None:
    from src.backtest.metrics import compute_metrics
    from src.strategy.filters import compute_adx
    settings = load_settings()
    # small smoke universe (5min download is rate-limited)
    tickers = ["AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN", "META", "GOOGL"]

    # --- Regime filter: SPY daily ADX(14) per day ---
    spy = yf.download("SPY", period="75d", interval="1d",
                      progress=False, auto_adjust=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    spy = spy.reset_index()
    spy.columns = [str(c).lower() for c in spy.columns]
    # yfinance daily reset_index yields 'date'; rename to datetime for compute_adx
    if "date" in spy.columns:
        spy = spy.rename(columns={"date": "datetime"})
    spy_adx = compute_adx(spy, period=14)
    spy_adx_by_day = {}
    for dt, v in zip(spy["datetime"], spy_adx):
        try:
            spy_adx_by_day[pd.to_datetime(dt).date()] = float(v)
        except Exception:
            pass

    all_trades: list[TradeResult] = []
    for t in tickers:
        tr = backtest_ticker(t, settings, days=59, spy_adx_by_day=spy_adx_by_day)
        print(f"  {t:<6} trades={len(tr)}")
        all_trades.extend(tr)
    m = compute_metrics(all_trades)
    print("\n=== PHASE 5 BACKTEST (5-min, ~60d, 8 ticker, +regime filter) ===")
    print(f"  n_trades     = {m.n_trades}")
    print(f"  win_rate     = {m.win_rate*100:.1f}%")
    print(f"  profit_factor= {m.profit_factor:.2f}")
    print(f"  total_pnl    = {m.total_pnl:.2f} (per-share net of Alpaca cost)")
    print(f"  sharpe       = {m.sharpe:.2f}")
    print(f"  avg_pnl      = {m.avg_pnl:.4f}")
    print("\nNOTE: 60d window is a sanity check, NOT the Fase 6 OOS proof.")
    print("      yfinance 5-min is capped; for Fase 6 use Polygon/Alpaca.")


if __name__ == "__main__":
    main()

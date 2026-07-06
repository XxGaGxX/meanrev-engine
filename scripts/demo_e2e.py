"""
End-to-End Demo for Mean Reversion Intraday Strategy
=====================================================

Runs the FULL pipeline against LIVE Alpaca paper-account data:
  1. Fetch historical SPY 15-min bars from Alpaca
  2. Clean + filter session hours
  3. Compute all indicators (ADX, Hurst, RSI, BB, Z-score, Volume, ATR)
  4. Apply regime filter
  5. Generate entry signals
  6. Simulate exits (trade log)
  7. Compute performance metrics
  8. Save a plot with regime zones, signals, P&L, equity curve

The demo deliberately uses permissive regime / entry thresholds (hardcoded)
so the live pipeline produces trades you can inspect rather than zero trades.
Without overrides, production thresholds on any given window may legitimately
reject all bars — that is a feature of the regime filter, not a bug.

Usage:
    python scripts/demo_e2e.py [--n-bars 1500] [--symbol SPY] [--no-plot]
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.config import config
from utils.metrics import calculate_all_metrics, print_metrics, kelly_criterion

from data.clean import clean_data, filter_session_hours
from filters.regime import apply_regime_filter
from indicators.pipeline import build_all_indicators
from signals.entry import generate_entry_signals, signal_counts
from signals.exit import simulate_all_trades, exit_reason_stats


# ──────────────────────────────────────────────────────────────────
# 1. Data — live Alpaca paper-account only
# ──────────────────────────────────────────────────────────────────

def fetch_data(symbol: str, n_bars: int) -> tuple[pd.DataFrame, str]:
    """Fetch live OHLCV from Alpaca paper account. Returns (df, source_label).

    Raises
    ------
    RuntimeError
        If Alpaca creds are missing, the API call fails, or no bars are
        returned. The demo does NOT silently fall back to synthetic data.
    """
    required = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")
    missing_creds = [k for k in required if not os.getenv(k)]
    if missing_creds:
        raise RuntimeError(
            f"Alpaca credentials missing: {missing_creds}. "
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in your environment "
            "or in a .env file (see .env.example)."
        )

    from data.fetch import AlpacaDataClient
    client = AlpacaDataClient()
    end = pd.Timestamp.today() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=int(n_bars * 15 / (60 * 6.5)) + 30)

    result = client.fetch_historical_bars(
        symbols=[symbol],
        timeframe="15Min",
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )
    df = result.get(symbol)
    if df is None or df.empty:
        raise RuntimeError(
            f"Alpaca returned no bars for {symbol} (n_bars={n_bars}). "
            "Check that the paper account has historical data for the requested range."
        )
    # Drop symbol level if present (alpaca-py can return MultiIndex)
    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values(-1)
    df.index = pd.DatetimeIndex(df.index)
    return df, "Alpaca (paper account, live)"


# ──────────────────────────────────────────────────────────────────
# 2. Pipeline stages (each prints a one-liner summary)
# ──────────────────────────────────────────────────────────────────

def step(name: str) -> None:
    print(f"\n{'─' * 60}\n▶ {name}\n{'─' * 60}")


def run_pipeline(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg_indicators = config.raw["indicators"]
    step("Clean raw OHLCV")
    df = clean_data(df)
    df = filter_session_hours(
        df,
        skip_first_minutes=config.get("timeframe.skip_first_minutes", 30),
        skip_last_minutes=config.get("timeframe.skip_last_minutes", 30),
        market_open=config.get("timeframe.market_open", "09:30"),
        market_close=config.get("timeframe.market_close", "16:00"),
    )
    print(f"  → {len(df)} bars after cleaning")

    step("Compute indicators (ADX, Hurst, RSI, BB, Z-score, Volume, ATR)")
    df = build_all_indicators(df, cfg=cfg_indicators)
    print(f"  → columns: {[c for c in df.columns if c not in ('open','high','low','close','volume')]}")

    step("Apply regime filter (Level 1)")
    # Demo uses permissive thresholds so live data, which often trends,
    # still produces some tradeable regime_ok windows for inspection.
    # Hardcoded to bypass config.yaml defaults (22 / 0.45 / 2.0).
    df = apply_regime_filter(
        df,
        adx_threshold=30.0,
        hurst_threshold=0.6,
        atr_relative_std_threshold=3.0,
    )
    regime_pct = df["regime_ok"].mean() * 100
    print(f"  → regime_ok: {df['regime_ok'].sum()} bars ({regime_pct:.1f}%)")

    step("Generate entry signals (Level 2)")
    # Demo: slightly relaxed RSI / Z-score so signals fire on live data
    # which rarely hits the strict production thresholds at single-bar freq.
    # Volume confirmation kept ON to preserve one of the strategy's pillars.
    entry_cfg = {
        "oversold": 40,
        "overbought": 60,
        "z_threshold": 1.5,
        "use_volume_confirm": True,
    }
    df = generate_entry_signals(df, cfg=entry_cfg)
    counts = signal_counts(df)
    print(f"  → long: {counts['long_signals']}, short: {counts['short_signals']}, total: {counts['total_signals']}")

    step("Simulate exits (Level 3)")
    exit_cfg = {
        "atr_multiplier": config.get("exit.atr_multiplier", 1.5),
        "max_bars": config.get("exit.max_bars", 25),
        "adx_stop_threshold": config.get("exit.adx_stop_threshold", 25),
    }
    trades = simulate_all_trades(df, cfg=exit_cfg)
    print(f"  → {len(trades)} trades simulated")

    return df, trades


def build_equity_curve(trades: pd.DataFrame, df: pd.DataFrame, initial: float = 10_000.0) -> pd.Series:
    """Build a simple equity curve assuming equal-sized positions."""
    equity = [initial]
    timestamps = [df.index[0]]
    for _, t in trades.iterrows():
        equity.append(equity[-1] * (1 + t["pnl_pct"]))
        # Map exit_idx to actual timestamp
        idx_pos = min(int(t["exit_idx"]), len(df) - 1)
        timestamps.append(df.index[idx_pos])
    return pd.Series(equity, index=timestamps, name="equity")


# ──────────────────────────────────────────────────────────────────
# 3. Plotting (optional, safe to skip with --no-plot)
# ──────────────────────────────────────────────────────────────────

def plot_results(df: pd.DataFrame, trades: pd.DataFrame, symbol: str) -> str:
    """
    Save a 4-panel figure to scripts/output/:
      1. Close + regime_ok background + entry markers
      2. ADX + Hurst
      3. Trade P&L bars
      4. Equity curve
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return "matplotlib not installed; skipping plot"

    out_dir = PROJECT_ROOT / "scripts" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f"Mean Reversion Intraday — Live Alpaca Demo — {symbol}", fontsize=14, fontweight="bold")

    # Panel 1: Price + regime + signals
    axes[0].plot(df.index, df["close"], color="black", lw=0.8, label="close")
    axes[0].fill_between(df.index, df["close"].min(), df["close"].max(),
                          where=df["regime_ok"], alpha=0.15, color="green", label="regime_ok")
    long_idx = df.index[df["signal_long"]]
    short_idx = df.index[df["signal_short"]]
    axes[0].scatter(long_idx, df.loc[long_idx, "close"], marker="^", color="blue",
                     s=60, label="long entry", zorder=5)
    axes[0].scatter(short_idx, df.loc[short_idx, "close"], marker="v", color="red",
                     s=60, label="short entry", zorder=5)
    axes[0].set_ylabel("Price ($)")
    axes[0].legend(loc="upper left", fontsize=8)

    # Panel 2: ADX + Hurst
    axes[1].plot(df.index, df["adx"], color="purple", lw=0.8, label="ADX")
    axes[1].axhline(config.get("regime_filter.adx_threshold", 22), color="purple",
                     ls="--", lw=0.7, alpha=0.5)
    axes[1].plot(df.index, df["hurst"], color="orange", lw=0.8, label="Hurst")
    axes[1].axhline(config.get("regime_filter.hurst_threshold", 0.45), color="orange",
                     ls="--", lw=0.7, alpha=0.5)
    axes[1].axhline(0.5, color="grey", ls=":", lw=0.5, alpha=0.5)
    axes[1].set_ylabel("Indicator")
    axes[1].legend(loc="upper left", fontsize=8)

    # Panel 3: Trade P&L bars
    if not trades.empty:
        # Map entry_idx / exit_idx to timestamps
        ts_entry = df.index.to_series().iloc[trades["entry_idx"].values].values
        axes[2].bar(ts_entry, trades["pnl_pct"] * 100, width=0.8,
                     color=["green" if p > 0 else "red" for p in trades["pnl_pct"]])
    axes[2].axhline(0, color="black", lw=0.5)
    axes[2].set_ylabel("Trade P&L (%)")

    # Panel 4: Equity curve
    equity = build_equity_curve(trades, df)
    axes[3].plot(equity.index, equity.values, color="navy", lw=1.2)
    axes[3].set_ylabel("Equity ($)")
    axes[3].set_xlabel("Date")

    plt.tight_layout()
    out_path = out_dir / f"demo_{symbol}.png"
    plt.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


# ──────────────────────────────────────────────────────────────────
# 4. Main
# ──────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="E2E demo for mean reversion intraday strategy")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--n-bars", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  MEAN REVERSION INTRADAY — END-TO-END DEMO")
    print("=" * 60)
    print(f"  Symbol     : {args.symbol}")
    print(f"  N bars     : {args.n_bars}")
    print(f"  Initial eq : ${config.get('account.equity', 10_000):,.0f}")
    print("=" * 60)

    # 1. Fetch (live Alpaca paper-account data only)
    step(f"Fetch live Alpaca data for {args.symbol}")
    raw_df, source = fetch_data(args.symbol, args.n_bars)
    print(f"  → {len(raw_df)} bars from {source}")
    print(f"  → date range: {raw_df.index.min()} → {raw_df.index.max()}")

    # 2. Run pipeline
    df, trades = run_pipeline(raw_df)

    # 3. Build equity curve + compute metrics
    step("Compute performance metrics")
    initial = config.get("account.equity", 10_000)
    equity = build_equity_curve(trades, df, initial=initial)
    trade_returns = pd.Series([t["pnl_pct"] for _, t in trades.iterrows()])
    # Annual periods for 15-min bars (252 trading days × ~22 bars/day after skip)
    periods_per_year = config.get("timeframe.bars_per_year", 5544)
    metrics = calculate_all_metrics(trade_returns, equity, periods_per_year=periods_per_year)
    print_metrics(metrics)

    # Exit reason breakdown
    if not trades.empty:
        print("\nExit reasons:")
        stats = exit_reason_stats(trades)
        print(stats.to_string())

    # Optional plot
    if not args.no_plot:
        step("Plot results")
        path = plot_results(df, trades, args.symbol)
        print(f"  → saved to {path}")

    print("\n✓ Demo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
End-to-End Demo for Mean Reversion Intraday Strategy
=====================================================

Runs the FULL pipeline against LIVE Alpaca paper-account data:
  1. Fetch historical SPY 15-min bars from Alpaca
  2. Delegate to backtest.engine.run_backtest with demo-mode permissive
     overrides (regime adx=30/hurst=0.6/atr=3.0, entry
     oversold=40/overbought=60/z=1.5) so live data still produces
     inspectable trades rather than zero trades
  3. Save a 4-panel plot (regime, indicators, P&L, equity curve) to
     scripts/output/demo_<symbol>.png

The demo deliberately uses permissive regime / entry thresholds so the
live pipeline produces trades you can inspect rather than zero trades.
Without overrides, production thresholds on any given window may
legitimately reject all bars -- that is a feature of the regime filter,
not a bug. ``run_pipeline`` is a thin wrapper that delegates to the
engine -- see :mod:`backtest.engine` for the actual pipeline code.

Usage:
    python scripts/demo_e2e.py [--n-bars 1500] [--symbol SPY] [--no-plot]
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.config import config
from utils.metrics import max_drawdown, print_metrics

from backtest.engine import BacktestResult, run_backtest
from risk.sizing import build_equity_curve, build_pct_curve
from signals.exit import exit_reason_stats


# ──────────────────────────────────────────────────────────────────
# 1. Data -- live Alpaca paper-account only
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
    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values(-1)
    df.index = pd.DatetimeIndex(df.index)
    return df, "Alpaca (paper account, live)"


# ──────────────────────────────────────────────────────────────────
# 2. Pipeline -- delegates to backtest.engine.run_backtest
# ──────────────────────────────────────────────────────────────────

def step(name: str) -> None:
    print(f"\n{'─' * 60}\n▶ {name}\n{'─' * 60}")


def run_pipeline(df: pd.DataFrame) -> BacktestResult:
    """
    Compose the full pipeline by delegating to
    :func:`backtest.engine.run_backtest`.

    Demo-mode permissive overrides on regime + entry thresholds so live
    Alpaca data (which often trends) still produces inspectable trades
    rather than zero trades. These overrides are demo-only -- the engine's
    production defaults (config.yaml) are stricter, which means any
    direct ``run_backtest`` call without overrides may yield zero trades
    on the same live data.

    Returns
    -------
    BacktestResult
        Bundles ``df`` (post-pipeline OHLCV + indicators + signals),
        ``trades`` (post-sizing trade log with $ P&L), both equity
        curves (sized + naive), the metrics dict, the merged config and
        the signal counts.
    """
    step("Run backtest pipeline "
         "(engine: clean -> indicators -> regime -> entry -> exit -> sizing -> metrics)")
    result = run_backtest(
        df,
        cfg={
            # Demo-mode permissive overrides -- see function docstring.
            "regime_filter": {
                "adx_threshold": 30.0,
                "hurst_threshold": 0.6,
                "atr_relative_std_threshold": 3.0,
            },
            "entry_signal": {
                "oversold": 40,
                "overbought": 60,
                "z_threshold": 1.5,
                "use_volume_confirm": True,
            },
        },
    )
    print(f"  -- bars post-pipeline: {len(result.df)}")
    if "regime_ok" in result.df.columns:
        regime_pct = result.df["regime_ok"].mean() * 100
        print(
            f"  -- regime_ok bars:    "
            f"{result.df['regime_ok'].sum()} ({regime_pct:.1f}%)"
        )
    print(
        f"  -- signals fired:     "
        f"{result.signals['long_signals']} long, "
        f"{result.signals['short_signals']} short"
    )
    print(f"  -- trades simulated:  {len(result.trades)}")
    print(f"  -- final equity:      ${result.equity.iloc[-1]:,.2f}")
    return result


# ──────────────────────────────────────────────────────────────────
# 3. Plotting (optional, safe to skip with --no-plot)
# ──────────────────────────────────────────────────────────────────

def plot_results(
    df: pd.DataFrame,
    trades: pd.DataFrame,
    symbol: str,
    regime_filter_cfg: Optional[dict] = None,
) -> str:
    """
    Save a 4-panel figure to scripts/output/:
      1. Close + regime_ok background + entry markers
      2. ADX + Hurst
      3. Trade P&L bars
      4. Equity curve

    Parameters
    ----------
    regime_filter_cfg : dict, optional
        ``regime_filter`` block from the merged cfg actually applied to
        the run (typically ``result.config_used["regime_filter"]``). Its
        ``adx_threshold`` and ``hurst_threshold`` drive the Panel 2
        axhline reference lines so the reference matches the filter
        that produced the regime_ok band on Panel 1. If ``None``, falls
        back to ``config.yaml`` defaults (production 22 / 0.45).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return "matplotlib not installed; skipping plot"

    if regime_filter_cfg is None:
        regime_filter_cfg = (config.raw.get("regime_filter") or {})
    adx_th = float(regime_filter_cfg.get("adx_threshold", 22.0))
    hurst_th = float(regime_filter_cfg.get("hurst_threshold", 0.45))

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
    axes[1].axhline(adx_th, color="purple", ls="--", lw=0.7, alpha=0.5)
    axes[1].plot(df.index, df["hurst"], color="orange", lw=0.8, label="Hurst")
    axes[1].axhline(hurst_th, color="orange", ls="--", lw=0.7, alpha=0.5)
    axes[1].axhline(0.5, color="grey", ls=":", lw=0.5, alpha=0.5)
    axes[1].set_ylabel("Indicator")
    axes[1].legend(loc="upper left", fontsize=8)

    # Panel 3: Trade P&L bars -- prefer the cost-aware pnl_pct_slip when
    # risk sizing was applied so the bars agree with Panel 4. Fall back
    # to the raw exit-derived pnl_pct for un-sized trade logs.
    if not trades.empty:
        ts_entry = df.index.to_series().iloc[trades["entry_idx"].values].values
        if "pnl_pct_slip" in trades.columns and trades["pnl_pct_slip"].notna().any():
            pnl_col = trades["pnl_pct_slip"]
            bar_label = "cost-aware"
        else:
            pnl_col = trades["pnl_pct"]
            bar_label = "exit-derived"
        axes[2].bar(ts_entry, pnl_col * 100, width=0.8,
                     color=["green" if p > 0 else "red" for p in pnl_col])
    axes[2].axhline(0, color="black", lw=0.5)
    axes[2].set_ylabel(f"Trade P&L (% — {bar_label})")

    # Panel 4: Equity curve -- overlay Sized vs Equal-weight Naive
    # The divergence between the two curves is the visual proof that
    # FASE 3 risk sizing changes the equity dynamics rather than just
    # re-scaling a single normalized return curve.
    sized = build_equity_curve(trades, df)
    naive = build_pct_curve(trades, df)
    initial = float(config.get("account.equity", 10_000))
    axes[3].axhline(initial, color="grey", lw=0.5, ls=":", alpha=0.7, label=f"initial ({initial:,.0f})")
    axes[3].plot(sized.index, sized.values, color="navy", lw=1.4,
                  label="Sized (vol-targeted, FASE 3)")
    if not trades.empty:
        axes[3].plot(naive.index, naive.values, color="darkorange", lw=1.0, ls="--",
                      label="Equal-weight naive (legacy)")
    axes[3].set_ylabel("Equity ($)")
    axes[3].set_xlabel("Date")
    axes[3].legend(loc="lower right", fontsize=8)

    # Inset legend of headline stats -- the DD delta is the headline because
    # FASE 3's whole reason to exist is making tail losses less catastrophic.
    if not trades.empty:
        sized_final = float(sized.iloc[-1])
        naive_final = float(naive.iloc[-1])
        sized_dd = float(max_drawdown(sized))
        naive_dd = float(max_drawdown(naive))
        dd_delta = sized_dd - naive_dd    # more negative = Sized more conservative
        text = (
            f"Δ max DD: {dd_delta * 100:+.2f}%   (Sized {sized_dd * 100:.2f}%  "
            f"vs  Naive {naive_dd * 100:.2f}%)\n"
            f"Sized  final: ${sized_final:,.0f}\n"
            f"Naive  final: ${naive_final:,.0f}  "
            f"(Δ ${sized_final - naive_final:+,.0f})"
        )
        axes[3].text(
            0.02, 0.95, text, transform=axes[3].transAxes,
            fontsize=8.5, va="top", family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="grey", alpha=0.9),
        )

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
    print(f"  -- {len(raw_df)} bars from {source}")
    print(f"  -- date range: {raw_df.index.min()} -> {raw_df.index.max()}")

    # 2. Run pipeline (delegates to backtest.engine.run_backtest).
    result = run_pipeline(raw_df)
    df = result.df
    trades = result.trades

    # 3. Performance metrics -- engine already populated ``result.metrics``.
    step("Engine metrics (computed by run_backtest)")
    print_metrics(result.metrics)

    # Exit reason breakdown
    if not trades.empty:
        print("\nExit reasons:")
        stats = exit_reason_stats(trades)
        print(stats.to_string())

    # Optional plot
    if not args.no_plot:
        step("Plot results")
        path = plot_results(
            df, trades, args.symbol,
            regime_filter_cfg=result.config_used.get("regime_filter"),
        )
        print(f"  -- saved to {path}")

    print("\n✓ Demo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Quick historical-period backtest runner.

Usage:
    python scripts/historical_test.py SPY "2023-10-01" "2023-12-31"
    python scripts/historical_test.py SPY "2024-01-01" "2024-03-31"
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(override=True)

import pandas as pd
from data.fetch import AlpacaDataClient
from backtest.engine import run_backtest
from filters.regime import regime_component_breakdown
from signals.exit import exit_reason_stats
from utils.metrics import print_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    parser.add_argument("start", help="YYYY-MM-DD")
    parser.add_argument("end", help="YYYY-MM-DD")
    args = parser.parse_args()

    print(f"Fetching {args.symbol} 15-min bars: {args.start} -> {args.end}")
    client = AlpacaDataClient()
    result = client.fetch_historical_bars(
        symbols=[args.symbol],
        timeframe="15Min",
        start=args.start,
        end=args.end,
    )
    df = result.get(args.symbol)
    if df is None or df.empty:
        print(f"No data for {args.symbol} in {args.start} -> {args.end}")
        return 1
    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values(-1)
    df.index = pd.DatetimeIndex(df.index)
    print(f"  Fetched {len(df)} bars, {df.index.min()} -> {df.index.max()}")

    bt = run_backtest(df)
    df_out = bt.df
    trades = bt.trades

    print(f"\n  Bars post-pipeline:   {len(df_out)}")
    if "regime_ok" in df_out.columns:
        regime_pct = df_out["regime_ok"].mean() * 100
        print(
            f"  regime_ok:             {df_out['regime_ok'].sum()} "
            f"({regime_pct:.1f}%)"
        )
    print(
        f"  Signals:               {bt.signals['long_signals']}L / "
        f"{bt.signals['short_signals']}S"
    )
    print(f"  Trades:                {len(trades)}")
    if bt.signals_skipped > 0:
        print(f"  Skipped (overlap):     {bt.signals_skipped}")

    print("\n--- Metrics ---")
    print_metrics(bt.metrics)

    # Regime breakdown
    if "regime_ok" in df_out.columns:
        regime_cfg = bt.config_used.get("regime_filter", {})
        bd = regime_component_breakdown(
            df_out,
            adx_threshold=float(regime_cfg.get("adx_threshold", 22.0)),
            hurst_threshold=float(regime_cfg.get("hurst_threshold", 0.45)),
            atr_relative_std_threshold=float(
                regime_cfg.get("atr_relative_std_threshold", 2.0)
            ),
        )
        print(f"\nRegime breakdown ({bd['n_bars']} bars):")
        print(f"  ADX pass:         {bd['adx_pass_pct']:5.1f}%")
        print(f"  Hurst fast pass:  {bd.get('hurst_fast_pass_pct', 0):5.1f}%")
        print(f"  Hurst slow pass:  {bd['hurst_pass_pct']:5.1f}%")
        print(f"  ATR z pass:       {bd['atr_rel_z_pass_pct']:5.1f}%")
        print(f"  Combined:         {bd['all_pass_pct']:5.1f}%")
        if "mean_regime_score" in bd:
            print(f"  Mean score:       {bd['mean_regime_score']:.3f}")

    # Exit reasons
    if not trades.empty:
        print("\nExit reasons:")
        print(exit_reason_stats(trades).to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())

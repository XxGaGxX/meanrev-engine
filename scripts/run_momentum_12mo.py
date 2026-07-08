"""
Run momentum (Donchian breakout) backtest on SPY 12-month window.

Used to validate Opzione D (pivot in-place): does a Donchian breakout
strategy capture edge in trending regimes where mean-reversion failed?

Exit rules are momentum-specific: no zscore TP, wider SL (2x ATR vs
mean-reversion's 1.5x), longer time stop (25 bars vs MR's 12),
regime stop disabled (momentum stays in trends).

Output
------
Stdout summary + log file in ``scripts/output/run_momentum_12mo.log``
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from dotenv import load_dotenv

load_dotenv(override=True)

from backtest.engine import run_backtest_for_symbol  # noqa: E402
from utils.metrics import print_metrics  # noqa: E402


def main() -> int:
    end = pd.Timestamp.now(tz="America/New_York").normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=370)  # ~12 months

    print("=" * 70)
    print("Momentum (Donchian breakout) Backtest -- PATH 3 pilot")
    print("=" * 70)
    print(f"Symbol:        SPY")
    print(f"Window:        {start.date()} -> {end.date()}")
    print(f"Strategy:      breakout_lookback=20, ADX>=25, mode=long_only")
    print(f"Exit:          SL=2xATR, time_stop=25 bars, regime_stop=OFF, tp_mode=none")
    print()

    # Compute approximate n_bars for 12 months of 15-min data.
    # 252 trading days * ~22 bars/day = ~5544 bars/year.
    n_bars = 5544

    result = run_backtest_for_symbol("SPY", cfg={
        "engine": {"strategy_type": "momentum"},
        "momentum_entry": {
            "breakout_lookback": 20,
            "adx_min": 25.0,
            "use_volume_confirm": True,
            "direction_mode": "long_only",
            "atr_multiplier": 2.0,
            "max_bars": 25,
            "adx_stop_threshold": 20.0,
            "tp_mode": "none",
            "tp_atr_target": 4.0,
        },
    }, n_bars=n_bars)
    print(f"Fetched {len(result.df)} 15-min bars")
    print()

    print("=== Signals ===")
    print(f"Long:  {result.signals['long_signals']}")
    print(f"Short: {result.signals['short_signals']}")
    print(f"Total: {result.signals['total_signals']}")
    print()

    print(f"=== Trades ({len(result.trades)}) ===")
    if not result.trades.empty:
        cols = ["entry_idx", "exit_idx", "direction", "pnl_pct", "bars_held", "exit_reason"]
        print(result.trades[cols].head(20).to_string())
    print()

    print("=== Metrics ===")
    print_metrics(result.metrics)

    final_equity = result.equity.iloc[-1]
    print()
    print(f"Final equity:   ${final_equity:,.2f}  (initial: $10,000)")
    print(f"Total return:   {(final_equity / 10_000 - 1) * 100:.2f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())

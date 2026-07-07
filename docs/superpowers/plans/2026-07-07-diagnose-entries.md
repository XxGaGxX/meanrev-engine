# Diagnose Entries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone diagnostic script that analyses the entry signal pipeline to identify why trade frequency is near-zero with production thresholds.

**Architecture:** Single-file script `scripts/diagnose_entries.py` that imports from existing modules (`data.fetch`, `backtest.engine`, `signals.entry`), fetches historical bars via Alpaca, runs `run_backtest()`, then prints three diagnostic sections: (1) entry condition frequency, (2) per-trade diagnostics, (3) win/loss aggregate comparison.

**Tech Stack:** Python 3.14, pandas, numpy, alpaca-py, argparse, python-dotenv. No new dependencies.

## Global Constraints

- Script must be a single file in `scripts/` — no new modules
- Must not modify any production code outside `scripts/`
- Must reuse `run_backtest()` exactly as-is, reading `result.config_used` for actual thresholds applied
- Must handle zero-trade and zero-signal cases gracefully (print "No trades to analyse", don't crash)
- Terminal output only — no CSV, JSON, or plot exports
- Follow existing project patterns: `fetch_historical_bars()` for data, ASCII-safe output for Windows terminals

---

### Task 1: Script skeleton — fetch, parse, run backtest

**Files:**
- Create: `scripts/diagnose_entries.py`

**Interfaces:**
- Consumes: `data.fetch.AlpacaDataClient.fetch_historical_bars()`, `backtest.engine.run_backtest(df, cfg=None)`, `dotenv.load_dotenv(override=True)`
- Produces: `BacktestResult` from `run_backtest()` — used by Tasks 2, 3, 4

- [ ] **Step 1: Write the CLI and fetch skeleton**

```python
"""Entry signal diagnostic script. Usage:
    python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01"
    python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01" --cfg '{"entry_signal":{"z_threshold":1.5}}'
"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(override=True)

import pandas as pd
from data.fetch import AlpacaDataClient
from backtest.engine import run_backtest


def parse_cfg(raw: str | None) -> dict | None:
    """Parse --cfg JSON string into a dict, or return None."""
    if raw is None:
        return None
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose entry signal bottlenecks"
    )
    parser.add_argument("symbol", help="Ticker (e.g., SPY)")
    parser.add_argument("start", help="Start date YYYY-MM-DD")
    parser.add_argument("end", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--cfg", default=None,
        help='Config overrides as JSON, e.g. \'{"entry_signal":{"z_threshold":1.5}}\''
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="Show top N trades by P&L for each direction (default 20)"
    )
    args = parser.parse_args()

    # Fetch
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

    # Run backtest
    cfg = parse_cfg(args.cfg)
    bt = run_backtest(df, cfg=cfg)
    df_post = bt.df
    trades = bt.trades
    cfg_used = bt.config_used

    n_bars = len(df_post)
    if n_bars == 0:
        print("No bars after pipeline — check your date range.")
        return 1

    print(f"  Bars post-pipeline: {n_bars}")
    print(f"  Signals: {bt.signals['long_signals']}L / {bt.signals['short_signals']}S")
    print(f"  Trades: {len(trades)}")

    # Read thresholds actually applied
    entry_cfg = cfg_used.get("entry_signal", {})
    oversold = entry_cfg.get("oversold", 30)
    overbought = entry_cfg.get("overbought", 70)
    z_thr = entry_cfg.get("z_threshold", 2.0)
    use_volume = entry_cfg.get("use_volume_confirm", True)

    print(f"\n  Thresholds: RSI oversold={oversold}, overbought={overbought}, "
          f"z={z_thr}, volume_confirm={use_volume}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run skeleton to verify it fetches and runs**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01"`
Expected: Prints "Fetching... Fetched N bars... Bars post-pipeline: M... Signals: ... Trades: ... Thresholds: ..."

- [ ] **Step 3: Commit**

```bash
git add scripts/diagnose_entries.py
git commit -m "feat: add diagnose_entries skeleton (CLI, fetch, backtest)"
```

---

### Task 2: Section 1 — Entry Condition Frequency

**Files:**
- Modify: `scripts/diagnose_entries.py` (add `_print_condition_frequency()`)

**Interfaces:**
- Consumes: `df_post` (pd.DataFrame), `oversold`, `overbought`, `z_thr`, `use_volume`, `n_bars`
- Produces: terminal output (Section 1)

- [ ] **Step 1: Write the frequency function**

Add this function after `parse_cfg`:

```python
def _print_condition_frequency(
    df: pd.DataFrame,
    oversold: float,
    overbought: float,
    z_thr: float,
    use_volume: bool,
    n_bars: int,
) -> None:
    """Print how many bars satisfy each entry condition individually."""
    print(f"\n=== ENTRY CONDITION FREQUENCY ({n_bars} bars) ===")
    print(f"{'Condition':<28} {'Bars':>6}  {'%':>6}")
    print("-" * 42)

    rows = [
        ("regime_ok", df["regime_ok"]),
        (f"RSI < oversold ({oversold:.0f})", df["rsi"] < oversold),
        (f"RSI > overbought ({overbought:.0f})", df["rsi"] > overbought),
        ("close < bb_lower", df["close"] < df["bb_lower"]),
        ("close > bb_upper", df["close"] > df["bb_upper"]),
        (f"zscore < -{z_thr}", df["zscore"] < -z_thr),
        (f"zscore > +{z_thr}", df["zscore"] > z_thr),
    ]
    if use_volume:
        rows.append(("vol_confirm", df["vol_confirm"]))

    for label, cond in rows:
        count = int(cond.fillna(False).sum())
        pct = count / n_bars * 100
        print(f"{label:<28} {count:>6}  {pct:>5.1f}%")

    # Combined: all long conditions
    long_cond = (
        df["regime_ok"]
        & (df["rsi"] < oversold)
        & (df["close"] < df["bb_lower"])
        & (df["zscore"] < -z_thr)
    )
    if use_volume:
        long_cond = long_cond & df["vol_confirm"]
    lc = int(long_cond.fillna(False).sum())
    print("-" * 42)
    print(f"{'ALL long conditions':<28} {lc:>6}  {lc/n_bars*100:>5.1f}%")

    # Combined: all short conditions
    short_cond = (
        df["regime_ok"]
        & (df["rsi"] > overbought)
        & (df["close"] > df["bb_upper"])
        & (df["zscore"] > z_thr)
    )
    if use_volume:
        short_cond = short_cond & df["vol_confirm"]
    sc = int(short_cond.fillna(False).sum())
    print(f"{'ALL short conditions':<28} {sc:>6}  {sc/n_bars*100:>5.1f}%")
```

- [ ] **Step 2: Wire it into `main()`**

Add these lines just before `return 0` in `main()`:

```python
    _print_condition_frequency(
        df_post, oversold, overbought, z_thr, use_volume, n_bars,
    )
```

- [ ] **Step 3: Run to verify output**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01"`
Expected: Section 1 prints with all 8 condition rows + ALL long + ALL short. The BB and z-score columns must exist in `df_post` (they do — `run_backtest` includes them).

- [ ] **Step 4: Commit**

```bash
git add scripts/diagnose_entries.py
git commit -m "feat: add entry condition frequency table (Section 1)"
```

---

### Task 3: Section 2 — Per-Trade Diagnostics

**Files:**
- Modify: `scripts/diagnose_entries.py` (add `_print_trade_diagnostics()`)

**Interfaces:**
- Consumes: `trades` (pd.DataFrame), `df_post` (pd.DataFrame)
- Produces: terminal output (Section 2)

- [ ] **Step 1: Write the trade diagnostics function**

Add this function:

```python
def _print_trade_diagnostics(
    trades: pd.DataFrame,
    df: pd.DataFrame,
    top_n: int,
) -> None:
    """Print per-trade entry-bar values sorted by P&L."""
    if trades.empty:
        print("\n=== TRADE DIAGNOSTICS ===\n  No trades to analyse.")
        return

    n = len(trades)
    print(f"\n=== TRADE DIAGNOSTICS ({n} trades) ===")

    # Collect per-trade data
    rows: list[dict] = []
    for i, t in trades.iterrows():
        entry_idx = int(t["entry_idx"])
        if entry_idx >= len(df):
            continue
        bar = df.iloc[entry_idx]
        # BB position: 0 = at lower band, 1 = at upper band
        bb_range = bar["bb_upper"] - bar["bb_lower"]
        bb_pos = (
            (bar["close"] - bar["bb_lower"]) / bb_range * 100
            if bb_range > 0 else 50.0
        )
        # Volume multiplier
        vol_mult = (
            bar["close"] / bar.get("vol_avg", bar["close"])
            if bar.get("vol_avg", 1) > 0 else 1.0
        )
        # Actually: volume_confirm is a bool; compute raw volume / vol_avg
        # vol_avg is in df from indicators/volume.py
        raw_vol_mult = (
            bar["close"] / df["vol_avg"].iloc[entry_idx]
            if "vol_avg" in df.columns and df["vol_avg"].iloc[entry_idx] > 0
            else float("nan")
        )
        rows.append({
            "idx": i + 1,
            "entry_ts": str(df.index[entry_idx])[:10],
            "exit_ts": str(df.index[int(t["exit_idx"])])[:10] if int(t["exit_idx"]) < len(df) else "end",
            "pnl_pct": float(t.get("pnl_pct_slip", t.get("pnl_pct", 0))) * 100,
            "dir": "LONG" if int(t["direction"]) == 1 else "SHORT",
            "rsi": float(bar["rsi"]),
            "z": float(bar["zscore"]),
            "bb_pos": bb_pos,
            "vol_mult": raw_vol_mult,
            "regime": bool(bar["regime_ok"]),
            "reason": str(t.get("exit_reason", "?")),
        })

    # Sort by P&L worst to best
    rows.sort(key=lambda r: r["pnl_pct"])

    # Print table
    header = (
        f"{'#':<3} {'Entry':>10} {'Exit':>10} {'P&L%':>8} {'Dir':>6} "
        f"{'RSI':>6} {'Z':>7} {'BB%':>6} {'Vol':>6} {'Reg':>5} {'Exit reason':>12}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        vol_str = f"{r['vol_mult']:.1f}x" if not pd.isna(r['vol_mult']) else "N/A"
        print(
            f"{r['idx']:<3} {r['entry_ts']:>10} {r['exit_ts']:>10} "
            f"{r['pnl_pct']:>7.2f}% {r['dir']:>6} "
            f"{r['rsi']:>5.1f} {r['z']:>6.2f} {r['bb_pos']:>5.1f}% "
            f"{vol_str:>6} {str(r['regime']):>5} {r['reason']:>12}"
        )
```

- [ ] **Step 2: Wire it into `main()`**

Add after the Section 1 call:

```python
    _print_trade_diagnostics(trades, df_post, args.top)
```

- [ ] **Step 3: Run on Q2 2026 to verify**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01"`
Expected: Table with 5 rows (from Sprint 3 demo), sorted by P&L. Columns: Entry, Exit, P&L%, Dir, RSI, Z, BB%, Vol, Reg, Exit reason.

- [ ] **Step 4: Run on Q4 2023 to verify zero-trade case**

Run: `python scripts/diagnose_entries.py SPY "2023-10-01" "2023-12-31"`
Expected: "No trades to analyse." — no crash.

- [ ] **Step 5: Commit**

```bash
git add scripts/diagnose_entries.py
git commit -m "feat: add per-trade diagnostics table (Section 2)"
```

---

### Task 4: Section 3 — Win/Loss Aggregate Comparison

**Files:**
- Modify: `scripts/diagnose_entries.py` (add `_print_win_loss_comparison()`)

**Interfaces:**
- Consumes: `trades` (pd.DataFrame), `df_post` (pd.DataFrame)
- Produces: terminal output (Section 3)

- [ ] **Step 1: Write the win/loss comparison function**

Add this function:

```python
def _print_win_loss_comparison(trades: pd.DataFrame, df: pd.DataFrame) -> None:
    """Compare entry conditions between winning and losing trades."""
    if trades.empty:
        return  # already handled by Section 2

    # Split into winners (P&L > 0) and losers
    winners = trades[
        trades.get("pnl_pct_slip", trades.get("pnl_pct", 0)) > 0
    ]
    losers = trades[
        trades.get("pnl_pct_slip", trades.get("pnl_pct", 0)) <= 0
    ]

    nw, nl = len(winners), len(losers)
    if nw == 0 and nl == 0:
        return

    print(f"\n=== WIN VS LOSS COMPARISON ===")
    print(f"{'Metric':<18} {'Winners (n=' + str(nw) + ')':<22} {'Losers (n=' + str(nl) + ')':<22}")
    print("-" * 62)

    pnl_col = "pnl_pct_slip" if "pnl_pct_slip" in trades.columns else "pnl_pct"

    def _mean_std_str(group: pd.DataFrame, col: str, fmt: str = ".1f") -> str:
        """Return 'mean / mean_of_abs' for a group, handling NaN."""
        vals = []
        for _, t in group.iterrows():
            ei = int(t["entry_idx"])
            if ei < len(df):
                v = df[col].iloc[ei]
                if not pd.isna(v):
                    vals.append(float(v))
        if not vals:
            return "N/A"
        import numpy as np
        return f"{np.mean(vals):{fmt}}"

    def _bb_pos_str(group: pd.DataFrame) -> str:
        vals = []
        for _, t in group.iterrows():
            ei = int(t["entry_idx"])
            if ei < len(df):
                bar = df.iloc[ei]
                bb_range = bar["bb_upper"] - bar["bb_lower"]
                if bb_range > 0:
                    vals.append(float((bar["close"] - bar["bb_lower"]) / bb_range * 100))
        if not vals:
            return "N/A"
        import numpy as np
        return f"{np.mean(vals):.1f}%"

    def _pnl_str(group: pd.DataFrame) -> str:
        vals = group[pnl_col].dropna() * 100
        if len(vals) == 0:
            return "N/A"
        import numpy as np
        return f"{np.mean(vals):.2f}%"

    def _bars_str(group: pd.DataFrame) -> str:
        if "bars_held" not in group.columns:
            return "N/A"
        vals = group["bars_held"].dropna()
        if len(vals) == 0:
            return "N/A"
        import numpy as np
        return f"{np.mean(vals):.1f}"

    metrics = [
        ("RSI", "rsi"),
        ("Z-score", "zscore"),
        ("BB_pos", None),      # special
        ("Vol(x)", None),       # special — skip for simplicity
        ("Bars held", None),    # special
        ("P&L %", None),        # special
    ]

    for label, col in metrics:
        if col == "rsi":
            w_str = _mean_std_str(winners, "rsi")
            l_str = _mean_std_str(losers, "rsi")
        elif col == "zscore":
            w_str = _mean_std_str(winners, "zscore", ".2f")
            l_str = _mean_std_str(losers, "zscore", ".2f")
        elif label == "BB_pos":
            w_str = _bb_pos_str(winners)
            l_str = _bb_pos_str(losers)
        elif label == "Bars held":
            w_str = _bars_str(winners)
            l_str = _bars_str(losers)
        elif label == "P&L %":
            w_str = _pnl_str(winners)
            l_str = _pnl_str(losers)
        else:
            w_str, l_str = "N/A", "N/A"

        print(f"{label:<18} {w_str:<22} {l_str:<22}")
```

- [ ] **Step 2: Wire it into `main()`**

Add after the Section 2 call:

```python
    _print_win_loss_comparison(trades, df_post)
```

- [ ] **Step 3: Run on Q2 2026 to verify**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01"`
Expected: Section 3 shows winners (n=2) vs losers (n=3) with RSI, Z-score, BB_pos, Bars held, P&L %.

- [ ] **Step 4: Run with --cfg override**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01" --cfg '{"entry_signal":{"z_threshold":1.5,"oversold":40,"overbought":60}}'`
Expected: Section 1 shows updated thresholds (z=1.5, oversold=40, overbought=60). More signals may fire.

- [ ] **Step 5: Commit**

```bash
git add scripts/diagnose_entries.py
git commit -m "feat: add win/loss aggregate comparison (Section 3)"
```

---

### Task 5: Final polish — edge cases and cleanup

**Files:**
- Modify: `scripts/diagnose_entries.py`

**Interfaces:**
- Produces: final, production-ready script

- [ ] **Step 1: Add zero-signal graceful handling**

In `main()`, after `bt.signals`, add:

```python
    if bt.signals["total_signals"] == 0:
        _print_condition_frequency(
            df_post, oversold, overbought, z_thr, use_volume, n_bars,
        )
        print("\n  No signals fired — skipping trade diagnostics.")
        return 0
```

This ensures Section 1 always prints even when there are no signals.

- [ ] **Step 2: Add missing-column guard**

At the top of `main()`, after `df_post = bt.df`:

```python
    required = {"rsi", "bb_upper", "bb_lower", "zscore", "regime_ok", "vol_confirm"}
    missing = required - set(df_post.columns)
    if missing:
        print(f"Missing required columns in post-pipeline df: {sorted(missing)}")
        print("The pipeline may have changed. Check indicators/pipeline.py")
        return 1
```

- [ ] **Step 3: Run final validation**

Run all three scenarios:
- `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01"` → full output
- `python scripts/diagnose_entries.py SPY "2023-10-01" "2023-12-31"` → "No trades to analyse"
- `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01" --cfg '{"entry_signal":{"z_threshold":1.5}}'` → updated thresholds

- [ ] **Step 4: Commit**

```bash
git add scripts/diagnose_entries.py
git commit -m "chore: polish diagnose_entries edge cases and zero-signal path"
```

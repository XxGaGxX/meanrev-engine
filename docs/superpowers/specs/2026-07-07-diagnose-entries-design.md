# Entry Signal Diagnostic Script — Design Spec

**Date:** 2026-07-07
**Status:** Approved
**Context:** Post-Sprint 3 (Adaptive Hurst), entry signal is the next bottleneck.
  Win rate is 40% with 5 trades on Q2 2026. Historical periods produce 0 trades
  with production thresholds. Need to understand WHY before proposing fixes.

---

## Purpose

A standalone diagnostic script (`scripts/diagnose_entries.py`) that analyses
the entry signal pipeline to answer three questions:

1. **Which condition is the bottleneck?** — How many bars satisfy each of the
   5 entry conditions individually, and how many satisfy all 5 simultaneously?
2. **What do winning vs losing trades look like?** — At the entry bar, what
   were the exact RSI, z-score, BB position, volume, and regime values for
   winners vs losers?
3. **Is there a pattern?** — Can we identify which conditions separate
   winners from losers?

The script does NOT modify any production code. It imports from the existing
modules, runs a backtest, and prints diagnostics.

---

## Architecture

Single-file script: `scripts/diagnose_entries.py`

### Dependencies (imports)
- `data.fetch.AlpacaDataClient` — fetch historical bars
- `backtest.engine.run_backtest` — run the full pipeline
- `utils.config.config` — read config defaults
- `pandas`, `numpy`, `argparse`, `dotenv`

### Data Flow

```
Alpaca (fetch) → run_backtest(df) → df_post (with signals) + trades
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             Section 1              Section 2            Section 3
        Entry condition          Per-trade table       Win/Loss aggregate
          frequency                 + P&L               comparison
```

The script reuses `run_backtest()` exactly as-is. It reads `df.signal_long`
and `df.signal_short` for signal counts, and `trades` for trade-level P&L.

---

## Output Sections

### Section 1 — Entry Condition Frequency

For each of the 5 conditions, count bars (post-pipeline, non-NaN) where the
condition is true, using the **actual thresholds applied** (read from
`result.config_used`).

```
=== ENTRY CONDITION FREQUENCY (1334 bars) ===
Condition              Bars     %
────────────────────────────────────────
regime_ok              275    20.6%
RSI < oversold (30)     82     6.1%
RSI > overbought (70)   45     3.4%
close < bb_lower         27     2.0%
close > bb_upper         18     1.3%
zscore < -2.0            35     2.6%
zscore > +2.0            31     2.3%
vol_confirm             412    30.9%
────────────────────────────────────────
ALL long conditions       0     0.0%
ALL short conditions      6     0.4%
```

This section answers: **which single condition is the rarest?** The rarest
condition is the primary bottleneck.

### Section 2 — Per-Trade Diagnostics

For every trade in the trade log, show the entry-bar values for all
conditions. Rows sorted by P&L (worst to best).

```
=== TRADE DIAGNOSTICS (5 trades) ===
#  Entry    Exit    P&L%    Dir   RSI   Z      BB_pos    Vol(×)  Regime  Exit reason
── ──────── ─────── ─────── ──── ───── ────── ───────── ─────── ─────── ───────────
1  2026-04  2026-04 -0.42%  LONG  28.3  -2.14  -1.8%     2.1×    True    sl
2  2026-05  2026-05 -0.31%  SHORT 68.7  +1.82  +1.2%     1.8×    True    regime
3  2026-05  2026-05 -0.15%  LONG  32.1  -1.95  -0.9%     1.6×    True    regime
4  2026-06  2026-06 +0.12%  SHORT 71.2  +2.31  +2.5%     2.3×    True    tp
5  2026-06  2026-06 +0.28%  LONG  26.5  -2.45  -2.1%     2.5×    True    tp
```

Columns:
- `BB_pos` = (close - bb_lower) / (bb_upper - bb_lower) — position within bands, 0 = at lower, 1 = at upper
- `Vol(×)` = volume / vol_avg — volume multiplier
- `Regime` = regime_ok at entry bar

### Section 3 — Win/Loss Aggregate Comparison

Group trades by win (P&L > 0) vs loss and show mean + std for each metric.

```
=== WIN VS LOSS COMPARISON ===
Metric          Winners (n=2)    Losers (n=3)
─────────────────────────────────────────────
RSI             26.5 / 71.2      29.7 / 68.7
Z-score         -2.45 / +2.31    -2.03 / +1.82
BB_pos           2.3% / 97.7%     1.4% / 98.8%
Vol(×)           2.4×             1.7×
Bars held        8.5              12.3
```

This section answers: **are winners systematically different from losers?**

---

## CLI Interface

```
usage: diagnose_entries.py SYMBOL START END [--cfg CFG_JSON]

positional arguments:
  SYMBOL      Ticker (e.g., SPY)
  START       Start date YYYY-MM-DD
  END         End date YYYY-MM-DD

optional:
  --cfg JSON  Config overrides, e.g. '{"entry_signal":{"z_threshold":1.5}}'
  --top N     Show top N trades by P&L for each direction (default 20)
```

---

## Edge Cases

| Case | Behaviour |
|------|-----------|
| Zero trades | Sections 2 and 3 show "No trades to analyse" |
| Zero signals | Section 1 still prints frequency. Sections 2-3 skipped |
| NaN in conditions | Excluded from frequency counts with note |
| Missing columns | Raise ValueError with list of missing columns |
| Alpaca returns no data | Raise RuntimeError (same as historical_test.py) |
| Different timeframe | Script reads timeframe from config, works with any |

---

## Testing

No new test file required — the script is diagnostic-only and doesn't modify
production code. Validation:

1. Run on Q2 2026 (known 5 trades) → verify output matches known metrics
2. Run on Q4 2023 (0 trades) → verify graceful "no trades" message
3. Run with `--cfg` override → verify thresholds in Section 1 reflect overrides

---

## Non-Goals (YAGNI)

- No integration into `BacktestResult` or the engine
- No CSV/JSON export (terminal output only — can pipe to file)
- No plotting/charts
- No modification of existing code outside `scripts/`

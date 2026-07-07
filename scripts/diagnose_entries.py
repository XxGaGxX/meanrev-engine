"""
Entry signal diagnostic script.

Analyses the entry signal pipeline to answer three questions:
  1. Which condition is the bottleneck? (Section 1 — frequency)
  2. What do winning vs losing trades look like? (Section 2 — per-trade)
  3. Is there a pattern? (Section 3 — win/loss comparison)

Usage:
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

import numpy as np
import pandas as pd
from data.fetch import AlpacaDataClient
from backtest.engine import run_backtest


# ── Helpers ──────────────────────────────────────────────────────────────

def parse_cfg(raw: str | None) -> dict | None:
    """Parse --cfg JSON string into a dict, or return None."""
    if raw is None:
        return None
    return json.loads(raw)


def _entry_date(df: pd.DataFrame, idx: int) -> str:
    """Return YYYY-MM-DD string for a row index, or 'N/A' if out of bounds."""
    if idx < 0 or idx >= len(df):
        return "N/A"
    try:
        return df.index[idx].strftime("%Y-%m-%d")  # type: ignore[union-attr]
    except AttributeError:
        return str(df.index[idx])[:10]


# ── Section 1 — Entry Condition Frequency ──────────────────────────────

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
    print(f"{'ALL long conditions':<28} {lc:>6}  {lc / n_bars * 100:>5.1f}%")

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
    print(f"{'ALL short conditions':<28} {sc:>6}  {sc / n_bars * 100:>5.1f}%")


# ── Section 2 — Per-Trade Diagnostics ─────────────────────────────────

def _print_trade_diagnostics(
    trades: pd.DataFrame,
    df: pd.DataFrame,
    top_n: int,
) -> None:
    """Print per-trade entry-bar values sorted by P&L worst to best."""
    if trades.empty:
        print("\n=== TRADE DIAGNOSTICS ===\n  No trades to analyse.")
        return

    n = len(trades)
    print(f"\n=== TRADE DIAGNOSTICS ({n} trades, top {min(n, top_n)}) ===")

    # Pick the P&L column (cost-aware if available, else exit-derived)
    pnl_col = (
        "pnl_pct_slip"
        if "pnl_pct_slip" in trades.columns and trades["pnl_pct_slip"].notna().any()
        else "pnl_pct"
    )

    # Collect per-trade data
    rows: list[dict] = []
    for _, t in trades.iterrows():
        entry_idx = int(t["entry_idx"])
        exit_idx = int(t["exit_idx"])
        if entry_idx >= len(df):
            continue
        bar = df.iloc[entry_idx]

        # BB position: 0 = at lower band, 100 = at upper band
        bb_range = bar["bb_upper"] - bar["bb_lower"]
        bb_pos = (
            (bar["close"] - bar["bb_lower"]) / bb_range * 100
            if bb_range > 0 else 50.0
        )

        # Volume multiplier: raw volume / vol_avg
        vol_avg = df["vol_avg"].iloc[entry_idx] if "vol_avg" in df.columns else np.nan
        raw_vol = df["volume"].iloc[entry_idx] if "volume" in df.columns else np.nan
        vol_mult = raw_vol / vol_avg if (not np.isnan(vol_avg) and vol_avg > 0) else np.nan

        rows.append({
            "entry_ts": _entry_date(df, entry_idx),
            "exit_ts": _entry_date(df, exit_idx),
            "pnl_pct": float(t[pnl_col]) * 100,
            "dir": "LONG" if int(t["direction"]) == 1 else "SHORT",
            "rsi": float(bar["rsi"]),
            "z": float(bar["zscore"]),
            "bb_pos": bb_pos,
            "vol_mult": vol_mult,
            "regime": bool(bar["regime_ok"]),
            "reason": str(t.get("exit_reason", "?")),
        })

    # Sort by P&L worst to best, then show top N
    rows.sort(key=lambda r: r["pnl_pct"])
    rows = rows[:top_n]

    # Print table
    header = (
        f"{'#':<3} {'Entry':>10} {'Exit':>10} {'P&L%':>8} {'Dir':>6} "
        f"{'RSI':>6} {'Z':>7} {'BB%':>6} {'Vol':>6} {'Reg':>5} {'Exit reason':>12}"
    )
    print(header)
    print("-" * len(header))
    for i, r in enumerate(rows, 1):
        vol_str = f"{r['vol_mult']:.1f}x" if not np.isnan(r['vol_mult']) else "N/A"
        print(
            f"{i:<3} {r['entry_ts']:>10} {r['exit_ts']:>10} "
            f"{r['pnl_pct']:>7.2f}% {r['dir']:>6} "
            f"{r['rsi']:>5.1f} {r['z']:>6.2f} {r['bb_pos']:>5.1f}% "
            f"{vol_str:>6} {str(r['regime']):>5} {r['reason']:>12}"
        )


# ── Section 3 — Win/Loss Aggregate Comparison ────────────────────────

def _print_win_loss_comparison(
    trades: pd.DataFrame,
    df: pd.DataFrame,
) -> None:
    """Compare entry conditions between winning and losing trades."""
    if trades.empty:
        return  # already handled by Section 2

    pnl_col = (
        "pnl_pct_slip"
        if "pnl_pct_slip" in trades.columns and trades["pnl_pct_slip"].notna().any()
        else "pnl_pct"
    )

    # Split into winners (P&L > 0) and losers
    winners = trades[trades[pnl_col] > 0]
    losers = trades[trades[pnl_col] <= 0]

    nw, nl = len(winners), len(losers)
    if nw == 0 and nl == 0:
        return

    print(f"\n=== WIN VS LOSS COMPARISON ===")
    print(
        f"{'Metric':<18} {'Winners (n=' + str(nw) + ')':<22} "
        f"{'Losers (n=' + str(nl) + ')':<22}"
    )
    print("-" * 62)

    def _extract(group: pd.DataFrame, col: str) -> list[float]:
        """Pull non-NaN column values at entry bars for a trade group."""
        vals = []
        for _, t in group.iterrows():
            ei = int(t["entry_idx"])
            if ei < len(df):
                v = df[col].iloc[ei]
                if not pd.isna(v):
                    vals.append(float(v))
        return vals

    def _fmt(vals: list[float], fmt: str = ".1f") -> str:
        if not vals:
            return "N/A"
        return f"{np.mean(vals):{fmt}}"

    def _bb_mean(group: pd.DataFrame) -> list[float]:
        vals = []
        for _, t in group.iterrows():
            ei = int(t["entry_idx"])
            if ei < len(df):
                bar = df.iloc[ei]
                bb_range = bar["bb_upper"] - bar["bb_lower"]
                if bb_range > 0:
                    vals.append(
                        float((bar["close"] - bar["bb_lower"]) / bb_range * 100)
                    )
        return vals

    def _vol_mean(group: pd.DataFrame) -> list[float]:
        vals = []
        for _, t in group.iterrows():
            ei = int(t["entry_idx"])
            if ei < len(df):
                vol_avg = df["vol_avg"].iloc[ei] if "vol_avg" in df.columns else np.nan
                raw = df["volume"].iloc[ei] if "volume" in df.columns else np.nan
                if not np.isnan(vol_avg) and vol_avg > 0:
                    vals.append(float(raw / vol_avg))
        return vals

    def _pnl_mean(group: pd.DataFrame) -> list[float]:
        return (group[pnl_col].dropna() * 100).tolist()

    def _bars_mean(group: pd.DataFrame) -> list[float]:
        if "bars_held" not in group.columns:
            return []
        return group["bars_held"].dropna().tolist()

    w_rsi = _extract(winners, "rsi")
    l_rsi = _extract(losers, "rsi")
    w_z = _extract(winners, "zscore")
    l_z = _extract(losers, "zscore")
    w_bb = _bb_mean(winners)
    l_bb = _bb_mean(losers)
    w_vol = _vol_mean(winners)
    l_vol = _vol_mean(losers)
    w_bars = _bars_mean(winners)
    l_bars = _bars_mean(losers)
    w_pnl = _pnl_mean(winners)
    l_pnl = _pnl_mean(losers)

    # Long/short mix
    w_dir = winners["direction"].astype(int)
    l_dir = losers["direction"].astype(int)

    print(f"{'RSI':<18} {_fmt(w_rsi):<22} {_fmt(l_rsi):<22}")
    print(f"{'Z-score':<18} {_fmt(w_z, '.2f'):<22} {_fmt(l_z, '.2f'):<22}")
    print(f"{'BB_pos (%)':<18} {_fmt(w_bb):<22} {_fmt(l_bb):<22}")
    print(f"{'Vol(x)':<18} {_fmt(w_vol):<22} {_fmt(l_vol):<22}")
    print(f"{'Bars held':<18} {_fmt(w_bars):<22} {_fmt(l_bars):<22}")
    print(f"{'P&L %':<18} {_fmt(w_pnl, '.2f'):<22} {_fmt(l_pnl, '.2f'):<22}")
    print(
        f"{'Long/Short mix':<18} "
        f"{str((w_dir == 1).sum()) + 'L/' + str((w_dir == -1).sum()) + 'S':<22} "
        f"{str((l_dir == 1).sum()) + 'L/' + str((l_dir == -1).sum()) + 'S':<22}"
    )

    # Entry score row (Sprint 4: soft entry scoring)
    if "entry_score" in df.columns:
        w_entry = [
            float(df["entry_score"].iloc[int(t["entry_idx"])])
            for _, t in winners.iterrows()
            if int(t["entry_idx"]) < len(df)
            and not pd.isna(df["entry_score"].iloc[int(t["entry_idx"])])
        ]
        l_entry = [
            float(df["entry_score"].iloc[int(t["entry_idx"])])
            for _, t in losers.iterrows()
            if int(t["entry_idx"]) < len(df)
            and not pd.isna(df["entry_score"].iloc[int(t["entry_idx"])])
        ]
        print(
            f"{'Entry score':<18} {_fmt(w_entry, '.3f'):<22} "
            f"{_fmt(l_entry, '.3f'):<22}"
        )


# ── Main ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose entry signal bottlenecks"
    )
    parser.add_argument("symbol", help="Ticker (e.g., SPY)")
    parser.add_argument("start", help="Start date YYYY-MM-DD")
    parser.add_argument("end", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--cfg", default=None,
        help='Config overrides as JSON, e.g. \'{"entry_signal":{"z_threshold":1.5}}\'',
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="Show top N trades by P&L in the per-trade table (default 20)",
    )
    args = parser.parse_args()

    # Fetch
    print(f"Fetching {args.symbol} 15-min bars: {args.start} -> {args.end}")
    client = AlpacaDataClient()
    fetched = client.fetch_historical_bars(
        symbols=[args.symbol],
        timeframe="15Min",
        start=args.start,
        end=args.end,
    )
    df_raw = fetched.get(args.symbol)
    if df_raw is None or df_raw.empty:
        print(f"No data for {args.symbol} in {args.start} -> {args.end}")
        return 1
    if isinstance(df_raw.index, pd.MultiIndex):
        df_raw.index = df_raw.index.get_level_values(-1)
    df_raw.index = pd.DatetimeIndex(df_raw.index)
    print(f"  Fetched {len(df_raw)} bars, {df_raw.index.min()} -> {df_raw.index.max()}")

    # Run backtest (honours global config + --cfg overrides)
    bt = run_backtest(df_raw, cfg=parse_cfg(args.cfg))
    df_post = bt.df
    trades = bt.trades
    cfg_used = bt.config_used
    n_bars = len(df_post)

    print(f"  Bars post-pipeline: {n_bars}")

    # Column guard
    required = {"rsi", "bb_upper", "bb_lower", "zscore", "regime_ok", "vol_confirm"}
    missing = required - set(df_post.columns)
    if missing:
        print(f"Missing required columns in post-pipeline df: {sorted(missing)}")
        print("The pipeline may have changed. Check indicators/pipeline.py")
        return 1

    # Read thresholds actually applied
    entry_cfg = cfg_used.get("entry_signal", {})
    oversold = entry_cfg.get("oversold", 30)
    overbought = entry_cfg.get("overbought", 70)
    z_thr = entry_cfg.get("z_threshold", 2.0)
    use_volume = entry_cfg.get("use_volume_confirm", True)

    print(f"  Thresholds: RSI oversold={oversold}, overbought={overbought}, "
          f"z={z_thr}, volume_confirm={use_volume}")

    # Section 1 — always print, even with zero signals
    _print_condition_frequency(
        df_post, oversold, overbought, z_thr, use_volume, n_bars,
    )

    if bt.signals["total_signals"] == 0:
        print(f"\n  Signals: {bt.signals['long_signals']}L / "
              f"{bt.signals['short_signals']}S")
        print("  No signals fired -- skipping trade diagnostics.")
        return 0

    print(f"  Signals: {bt.signals['long_signals']}L / "
          f"{bt.signals['short_signals']}S")
    print(f"  Trades: {len(trades)}")

    if getattr(bt, "signals_skipped", 0) > 0:
        print(f"  Skipped (overlap): {bt.signals_skipped}")

    # Section 2 — per-trade diagnostics
    _print_trade_diagnostics(trades, df_post, args.top)

    # Section 3 — win/loss comparison
    _print_win_loss_comparison(trades, df_post)

    return 0


if __name__ == "__main__":
    sys.exit(main())

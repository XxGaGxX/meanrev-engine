"""scripts/eda_gap_expectancy.py — Phase 2 EDA gate decision.

Pipeline:
  1. Load settings + read split manifest, call assert_oos_locked().
  2. Iterate every *.parquet in data/cache (skipping _metadata.yaml, split.yaml).
  3. Filter rows to dev window (split.dev_start .. split.dev_end).
  4. Build a unified bars frame -> compute_gaps_df -> assign_bucket.
  5. evaluate_gate(...) against gates.eda_min_trades_per_cell.
  6. Format markdown report -> reports/eda_gate_decision.md.

Exit code:
  0 — gate PASSES (at least one bucket has N>=threshold AND mean>0).
  1 — gate FAILS (no decisive bucket). The orchestrator exits non-zero on
      purpose: per ROADMAP_MVP.md, "se il gate di Fase 2 dice NO, fermati
      a Fase 2 — non costruisci il resto". The orchestrator is what enforces
      that policy in code, not a TODO in a Markdown file.

Usage:
  python scripts/eda_gap_expectancy.py
  python scripts/eda_gap_expectancy.py --cache-dir /path/to/cache
  python scripts/eda_gap_expectancy.py --out-report /path/to/report.md
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Make `src` importable when this script is run directly. Tests already
# import us via `from scripts.eda_gap_expectancy import run_eda`, so this
# sys.path mutation only matters for the CLI path.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import SETTINGS_PATH, Settings, load_settings  # noqa: E402
from src.data.ohlcv import (  # noqa: E402
    cache_path_for,
    compute_split,
    read_split_manifest,
)
from src.data.universe import get_universe  # noqa: E402
from src.strategy.gap_calc import (  # noqa: E402
    DOWN_BUCKETS,
    EXPECTANCY_MIN_TRADES_DEFAULT,
    INSUFFICIENT_DATA_CELL_THRESHOLD,
    UP_BUCKETS,
    BucketRow,
    GateResult,
    compute_buckets,
    compute_gaps_df,
    ensure_prev_close_column,
    evaluate_gate,
)


# ---------------------------------------------------------------------------
# Sector mapping — derived from src/data/universe.py macro assignments.
# ---------------------------------------------------------------------------

# Hard-coded EXACT mirror of the sectors in MVP_UNIVERSE comments so the
# orchestrator never accidentally re-reads comments and drifts when the
# universe list changes. Two sources of truth (this dict + universe.py
# comments) is a known smell; a v2 refactor should move it into a YAML
# map at config/. For the MVP it's fine: 80 large-caps, stable.
_TICKER_SECTOR: Dict[str, str] = {
    # Tech
    **{t: "Tech" for t in [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "ORCL",
        "CRM", "ADBE", "CSCO", "IBM", "INTC", "AMD", "QCOM", "AVGO",
        "TXN", "MU", "NOW", "PANW",
    ]},
    # Financials
    **{t: "Financials" for t in [
        "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW",
        "AXP", "USB", "PNC", "TFC", "COF", "SPGI", "ICE",
    ]},
    # Healthcare
    **{t: "Healthcare" for t in [
        "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "DHR",
        "ABT", "BMY", "AMGN", "GILD", "CVS", "CI", "ELV",
    ]},
    # Consumer
    **{t: "Consumer" for t in [
        "WMT", "PG", "KO", "PEP", "MCD", "NKE", "SBUX", "COST",
        "HD", "LOW",
    ]},
    # Energy
    **{t: "Energy" for t in [
        "XOM", "CVX", "COP", "SLB", "EOG",
    ]},
    # Industrials
    **{t: "Industrials" for t in [
        "BA", "CAT", "HON", "RTX", "DE",
    ]},
    # Materials
    **{t: "Materials" for t in [
        "LIN", "APD", "FCX",
    ]},
    # Utilities
    **{t: "Utilities" for t in [
        "NEE", "DUK", "SO",
    ]},
    # Real Estate
    **{t: "RealEstate" for t in [
        "PLD", "AMT",
    ]},
    # Telecom
    **{t: "Telecom" for t in [
        "VZ", "T",
    ]},
}

KNOWN_SECTORS = sorted(set(_TICKER_SECTOR.values()))


def sector_of(ticker: str) -> str:
    """Macro sector of a ticker. Falls back to 'Unknown' for unknown
    tickers so they DO appear in the sector-conditioned table rather than
    silently dropped."""
    return _TICKER_SECTOR.get(ticker.upper(), "Unknown")


# ---------------------------------------------------------------------------
# Cache loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CacheLoadSummary:
    n_loaded: int
    n_skipped: int
    skipped_tickers: List[str]


def load_dev_bars(
    cache_dir: Path,
    *,
    dev_start: date,
    dev_end: date,
    expected_columns: Optional[List[str]] = None,
) -> tuple[pd.DataFrame, CacheLoadSummary]:
    """Read every *.parquet under cache_dir and return a frame with rows
    strictly inside `[dev_start, dev_end]`.

    Skips non-parquet files (`split.yaml`, `_metadata.yaml`).

    Adds a `ticker` column. The `prev_close` column is NOT required —
    real yfinance data lacks it. The orchestrator derives it via
    `ensure_prev_close_column` after this returns.
    """
    expected_columns = expected_columns or ["date", "open", "close"]      
    loaded = []
    skipped = []
    n_loaded = 0
    n_skipped = 0
    for path in sorted(cache_dir.glob("*.parquet")):
        ticker = path.stem.replace("_", ".")
        try:
            df = pd.read_parquet(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {ticker}: failed to read parquet ({exc})", file=sys.stderr)
            skipped.append(ticker)
            n_skipped += 1
            continue

        missing_cols = [c for c in expected_columns if c not in df.columns]
        if missing_cols:
            print(
                f"[skip] {ticker}: missing columns {missing_cols}",
                file=sys.stderr,
            )
            skipped.append(ticker)
            n_skipped += 1
            continue

        df = df.copy()
        df["ticker"] = ticker
        df["date"] = pd.to_datetime(df["date"]).dt.date
        # Filter to dev window as we read each file — saves memory when the
        # cached file covers the full OOS window too.
        keep = df[(df["date"] >= dev_start) & (df["date"] <= dev_end)]
        if keep.empty:
            continue
        loaded.append(keep)
        n_loaded += 1

    if not loaded:
        return pd.DataFrame(columns=expected_columns + ["ticker"]), CacheLoadSummary(
            n_loaded=0, n_skipped=n_skipped, skipped_tickers=skipped,
        )
    df_all = pd.concat(loaded, ignore_index=True)
    # Boundary-inclusive at both ends (consistent with ROADMAP_Fase_2 contract).
    df_all = df_all[(df_all["date"] >= dev_start) & (df_all["date"] <= dev_end)]
    return df_all, CacheLoadSummary(
        n_loaded=n_loaded, n_skipped=n_skipped, skipped_tickers=skipped,
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_buckets_table(
    title: str,
    rows: List[BucketRow],
    *,
    insufficient_threshold: int = 20,
) -> str:
    """Markdown table of bucket-level expectancy. Buckets with N==0 are
    labelled 'Insufficient Data'.
    """
    lines = [f"### {title}", "",
             "| Bucket | Direction | N | Mean Return | Std | Freq | Approx Sharpe |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for label, direction in [(lab, "DOWN") for lab in DOWN_BUCKETS] + [(lab, "UP") for lab in UP_BUCKETS]:
        match = next((r for r in rows if r.label == label and r.direction == direction), None)
        if match is None or match.n == 0:
            lines.append(f"| {label} | {direction} | 0 | n/a | n/a | n/a | **Insufficient Data** |")
            continue
        if match.n < insufficient_threshold:
            tag = f"**Insufficient Data (N<{insufficient_threshold})**"
            lines.append(
                f"| {label} | {direction} | {match.n} | {match.mean_return:.4%} "
                f"| {match.std_return:.4%} | {match.frequency:.4%} | {tag} |"
            )
        else:
            sharpe = f"{match.approx_sharpe:.2f}" if match.approx_sharpe == match.approx_sharpe else "n/a"
            lines.append(
                f"| {label} | {direction} | {match.n} | {match.mean_return:+.4%} "
                f"| {match.std_return:.4%} | {match.frequency:.4%} | {sharpe} |"
            )
    return "\n".join(lines)


def _render_sector_table(
    df_in_window: pd.DataFrame,
) -> str:
    """Sector × size buckets. Each row: Sector, N, Bucket, Direction, Mean.

    Cells with N==0 are omitted. Cells with N<20 are tagged 'Insufficient
    Data' so the reader can see mean but recognize the cell isn't a
    decision input.
    """
    df = df_in_window.copy()
    if "bucket" not in df.columns:
        from src.strategy.gap_calc import assign_bucket
        df["bucket"] = assign_bucket(df)
    df = df.dropna(subset=["bucket"])
    df["sector"] = df["ticker"].map(sector_of)

    lines = ["### Sector x Size", "",
             "| Sector | N | Bucket | Direction | Mean Return |",
             "|---|---:|---|---|---:|"]
    summary_rows = []
    for sector in KNOWN_SECTORS + ["Unknown"]:
        s = df[df["sector"] == sector]
        if s.empty:
            continue
        for label, direction in (
            *((lab, "DOWN") for lab in DOWN_BUCKETS),
            *((lab, "UP") for lab in UP_BUCKETS),
        ):
            sub = s[s["bucket"] == label]
            n = len(sub)
            if n == 0:
                continue
            mean = float(sub["trade_return"].mean())
            tag = f" **Insufficient Data (N<{INSUFFICIENT_DATA_CELL_THRESHOLD})**" \
                if n < INSUFFICIENT_DATA_CELL_THRESHOLD else ""
            mean_str = f"{mean:+.4%}{tag}"
            summary_rows.append((sector, n, label, direction, mean_str))
    summary_rows.sort(key=lambda r: (r[0], -r[1]))
    if not summary_rows:
        lines.append("| _no data_ | 0 | - | - | - |")
        return "\n".join(lines)
    for sector, n, label, direction, mean_str in summary_rows:
        lines.append(f"| {sector} | {n} | {label} | {direction} | {mean_str} |")
    return "\n".join(lines)


def render_report(
    *,
    settings: Settings,
    gate: GateResult,
    df_dev: pd.DataFrame,
    cache_summary: CacheLoadSummary,
    dev_start: date,
    dev_end: date,
    threshold: int,
) -> str:
    """Markdown report body. Marker [GATE: PASS] / [GATE: FAIL] on a
    dedicated single line so downstream automation can grep."""
    # gate.buckets already lists every non-empty bucket (compute_buckets
    # with min_trades=1 evaluated inside evaluate_gate). We re-issue
    # compute_buckets on df_dev to drive the diagnostic table where every
    # of the six buckets is shown — including empty / N<20 cells — using
    # the same denominator as the gate.
    if len(df_dev) == 0:
        all_rows = list(gate.buckets)
    else:
        all_rows = compute_buckets(
            df_dev, min_trades=1, total_dev_bars=max(len(df_dev), 1)
        )

    marker = "[GATE: PASS]" if gate.passed else "[GATE: FAIL]"
    title = f"# Phase 2 — EDA Gap Expectancy — {marker}"

    sections: List[str] = [
        title,
        "",
        f"- Strategy: `{settings.strategy.name}`",
        f"- Universe size (declared): {settings.strategy.universe_size}",
        f"- Operating range: |gap| ∈ [{settings.strategy.gap_min_pct:.2%}, {settings.strategy.gap_max_pct:.2%}]",
        f"- Dev window: {dev_start} .. {dev_end}",
        f"- Cache loaded: {cache_summary.n_loaded} tickers "
        f"(skipped: {cache_summary.n_skipped}: {', '.join(cache_summary.skipped_tickers) or 'none'})",
        f"- Total dev bars in scope: {int(gate.total_dev_bars)}",
        f"- Gate threshold (N trades per bucket): {threshold}",
        "",
        "## Decision",
        "",
    ]
    if gate.passed:
        decisive = [b for b in gate.buckets if b.is_decisive(threshold)]
        lines = ", ".join(
            f"{b.label} (n={b.n}, mean={b.mean_return:+.4%})"
            for b in decisive[:5]
        )
        sections.append(f"**PROCEED.** At least one bucket has N ≥ {threshold} and positive mean return: {lines}.")
    else:
        sections.append(
            "**STOP — go back to strategy design (do NOT implement Fase 3+).** "
            "No bucket met the gate. Either the edge isn't measurable on the dev set, "
            "or the conditioning/sizing needs revisiting per ROADMAP_Fase_2."
        )
    sections += [
        "",
        "## Per-bucket expectancy (size)",
        "",
        _render_buckets_table("Size buckets — DOWN (long candidates) and UP (short candidates)", all_rows),
        "",
        "## Sector-conditioning",
        "",
        _render_sector_table(df_dev),
        "",
        "## Notes",
        "",
        "- Cells with N<20 are labelled *Insufficient Data* and excluded from the decision.",
        f"- Gate threshold of **{threshold}** comes from `config/settings.yaml` -> `gates.eda_min_trades_per_cell`.",
        "- `Mean Return` is signed in the direction of fill (DOWN→long, UP→short). Positive = reversion happened.",
        "- This script runs on the development set ONLY. The 30% OOS window is locked until Fase 6.",
        "",
        "## COST-SENSITIVITY CAVEAT (read before proceeding to Fase 3)",
        "",
    ]
    # Add a per-trade-bp disclosure so Phase-3 isn't built on a magnitude that
    # disappears under realistic commissions. Pick the BEST decisive bucket
    # (highest positive mean return) — not the largest-absolute-magnitude
    # bucket which can be a -mean loser.
    if gate.passed and gate.buckets:
        positive = [b for b in gate.buckets if b.mean_return > 0]
        if not positive:
            positive = list(gate.buckets)
        best = max(positive, key=lambda b: b.mean_return)
        bp = best.mean_return * 10000.0
        # Rough MVP cost assumption: 5bps commission + 5bps slippage round-trip.
        ROUGH_COST_BPS = 10.0
        ratio = abs(bp) / ROUGH_COST_BPS if ROUGH_COST_BPS > 0 else float("inf")
        verdict = (
            "ROBUST" if ratio >= 3 else
            "MARGINAL — likely to be erased by commissions" if ratio >= 1 else
            "FRAGILE — mean return does not exceed estimated costs"
        )
        sections.append(
            f"- Best-bucket mean return ≈ **{bp:+.2f} bp/trade** (best of "
            f"`{[b.label for b in gate.buckets]}`)."
        )
        sections.append(
            f"- If realistic round-trip cost is ~10 bps (5bps commission + "
            f"5bps slippage), `mean/cost` ratio = **{ratio:.2f}×** → "
            f"verdict: **{verdict}**."
        )
        sections.append(
            "- Phase 3 should NOT be built without a cost-aware per-trade "
            "threshold (`settings.gates.backtest_oos_min_mean_return_bps_above_cost` "
            "or similar). Reading the chart above as 'edge exists' without "
            "weighting costs will produce a strategy that loses money live."
        )
    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Main entry point — used both by the CLI and by tests
# ---------------------------------------------------------------------------


def run_eda(
    *,
    settings: Settings,
    cache_dir: Path,
    out_report: Path,
    manifest_path: Optional[Path] = None,
    current_phase: str = "Fase 2",
    min_trades_override: Optional[int] = None,
) -> int:
    """Compute the EDA on the dev set, write the markdown report, return
    the process exit code (0 PASS, 1 FAIL)."""
    # 1. Load split + enforce OOS lock.
    # 1. Load split manifest. The dev window is loaded; OOS bars are
    #    filtered out by date in load_dev_bars. We do NOT call
    #    assert_oos_locked here because the orchestrator's task is to run
    #    on the dev set only — there is no scenario where the orchestrator
    #    would touch OOS bars (the date filter forbids it).
    manifest_path = manifest_path or (cache_dir / "split.yaml")
    try:
        split = read_split_manifest(manifest_path)
    except FileNotFoundError as exc:
        print(f"[abort] {exc}; run scripts/download_data.py first.", file=sys.stderr)
        return 1

    # 2. Read dev bars from cache.
    df, summary = load_dev_bars(
        cache_dir,
        dev_start=split.dev_start,
        dev_end=split.dev_end,
    )
    if summary.n_loaded == 0:
        print(
            f"[abort] no parquets under {cache_dir}; run scripts/download_data.py first.",
            file=sys.stderr,
        )
        return 1

    # Derive prev_close from the prior bar per ticker (real yfinance data
    # does not store it). After this step the frame is sorted by
    # (ticker, date) which is required for the shift to align correctly.
    df = ensure_prev_close_column(df)
    df = compute_gaps_df(df)

    # 3. Gate.
    threshold = min_trades_override or settings.gates.eda_min_trades_per_cell
    gate = evaluate_gate(df, min_trades=threshold)

    # 4. Render + write the report.
    report = render_report(
        settings=settings,
        gate=gate,
        df_dev=df,
        cache_summary=summary,
        dev_start=split.dev_start,
        dev_end=split.dev_end,
        threshold=threshold,
    )
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(report, encoding="utf-8")

    decisive = [b for b in gate.buckets if b.is_decisive(threshold)]

    print(f"[eda] dev window: {split.dev_start} .. {split.dev_end}")
    print(f"[eda] cache: {summary.n_loaded} loaded, {summary.n_skipped} skipped")
    print(f"[eda] gate threshold: {threshold}; passed={gate.passed}; reason={gate.reason}")
    if decisive:
        for b in decisive:
            print(
                f"[eda]   PASS: {b.label} ({b.direction}) "
                f"N={b.n} mean={b.mean_return:+.4%} "
                f"sharpe={'n/a' if b.approx_sharpe != b.approx_sharpe else f'{b.approx_sharpe:.2f}'}"
            )

    return 0 if gate.passed else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2 EDA gate decision")
    parser.add_argument("--settings", type=Path, default=SETTINGS_PATH)
    parser.add_argument(
        "--cache-dir", type=Path, default=None,
        help="Override cache dir; defaults to settings.data.cache_dir.",
    )
    parser.add_argument(
        "--out-report", type=Path, default=None,
        help="Output markdown report; defaults to reports/eda_gate_decision.md.",
    )
    parser.add_argument(
        "--manifest", type=Path, default=None,
        help="Split manifest path; defaults to <cache-dir>/split.yaml.",
    )
    parser.add_argument(
        "--current-phase", type=str, default="Fase 2",
        help="Lock label. Pipeline default 'Fase 2'. Only Fase 6+ unlocks OOS.",
    )
    args = parser.parse_args(argv)

    settings = load_settings(args.settings)

    cache_dir = args.cache_dir or (ROOT / settings.data.cache_dir)
    if not cache_dir.is_dir():
        print(f"[abort] cache_dir does not exist: {cache_dir}", file=sys.stderr)
        return 1

    out_report = args.out_report or (ROOT / "reports" / "eda_gate_decision.md")
    manifest_path = args.manifest or (cache_dir / "split.yaml")

    return run_eda(
        settings=settings,
        cache_dir=cache_dir,
        out_report=out_report,
        manifest_path=manifest_path,
        current_phase=args.current_phase,
    )


if __name__ == "__main__":
    raise SystemExit(main())

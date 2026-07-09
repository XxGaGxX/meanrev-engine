"""scripts/download_data.py — Phase 1 MVP.

Usage:
    python scripts/download_data.py                # full universe
    python scripts/download_data.py --tickers AAPL MSFT GOOGL   # subset smoke test

Pipeline:
    1. Load settings + universe + split.
    2. Download OHLCV per ticker (yfinance) -> cache parquet.
    3. Write split manifest only AFTER the download loop succeeds
       (manifest on disk matches parquets on disk).
    4. Run check_continuity() against each cached file, honoring
       TICKER_ALIASES (renames / IPOs) so Fase 2 EDA doesn't see them
       as short_history for their entire history.
    5. Emit data/cache/_metadata.yaml with global data_window + per-ticker
       expected_start/actual_start/actual_end/gaps/status.

The 30% OOS window is NOT touched by any path that would let parameters
calibrate against it: Phase 3+ code that needs OOS bars must call
assert_oos_locked('Fase N', split) first.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import List

import pandas as pd
import yaml
import yfinance as yf

# Make `src` importable when this script is run directly.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import SETTINGS_PATH, load_settings  # noqa: E402
from src.data.ohlcv import (  # noqa: E402
    SHORT_HISTORY_GRACE_DAYS,
    cache_path_for,
    check_continuity,
    compute_split,
    normalize_ohlcv_columns,
    ticker_effective_start,
    write_split_manifest,
)
from src.data.universe import get_universe  # noqa: E402


def fetch_one(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Download daily OHLCV for a single ticker, with one auto-retry.

    Schema errors (raised by normalize_ohlcv_columns) propagate immediately
    without sleeping or retrying — a transient network issue cannot fix a
    schema mismatch. Only transport-level errors are retried.
    """
    from src.data.ohlcv import OHLCVSchemaError

    last_err: Exception | None = None
    for attempt in (0, 1):
        try:
            df = yf.download(
                ticker,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if df.empty:
                raise RuntimeError(f"yfinance returned empty frame for {ticker}")
            df = normalize_ohlcv_columns(df, ticker)
            df["ticker"] = ticker
            return df
        except OHLCVSchemaError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed for {ticker}: {last_err}")


def cache_one(cache_dir: Path, ticker: str, df: pd.DataFrame) -> Path:
    """Save DataFrame to per-ticker parquet; returns the file path."""
    path = cache_path_for(cache_dir, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def build_metadata(
    cache_dir: Path,
    tickers: List[str],
    expected_start: date,
    expected_end: date,
) -> dict:
    """Per-ticker metadata honoring TICKER_ALIASES for renames/IPO overrides."""
    metadata: dict = {}
    for ticker in tickers:
        path = cache_path_for(cache_dir, ticker)
        if not path.is_file():
            metadata[ticker] = {"status": "missing"}
            continue
        df = pd.read_parquet(path)
        actual_start = pd.to_datetime(df["date"]).dt.date.min()
        actual_end = pd.to_datetime(df["date"]).dt.date.max()
        # Per-ticker effective_start overrides expected_start for tickers
        # with renames/IPO history (PANW, RTX, ELV).
        effective_start = ticker_effective_start(ticker, expected_start)
        gaps = check_continuity(
            df, expected_start=effective_start, expected_end=actual_end
        )
        has_short_history = actual_start > (
            effective_start + timedelta(days=SHORT_HISTORY_GRACE_DAYS)
        )
        status = (
            "ok" if not gaps and not has_short_history
            else ("short_history" if has_short_history else "gap")
        )
        metadata[ticker] = {
            "status": status,
            "rows": int(len(df)),
            "expected_start": effective_start.isoformat(),
            "actual_start": actual_start.isoformat(),
            "actual_end": actual_end.isoformat(),
            "gaps_over_2bday": [
                {"start": s.isoformat(), "end": e.isoformat(), "bday_len": n}
                for s, e, n in gaps
            ],
        }
    return metadata


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1 OHLCV downloader")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="optional subset (e.g. for smoke testing). Defaults to the full MVP universe.",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=SETTINGS_PATH,
        help="path to settings.yaml",
    )
    parser.add_argument(
        "--full-download",
        action="store_true",
        help="unconditionally re-download even if cache file exists. Default: skip.",
    )
    args = parser.parse_args(argv)

    settings = load_settings(args.settings)
    split = compute_split(settings.data)
    cache_dir = ROOT / settings.data.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    universe = get_universe()
    tickers = args.tickers if args.tickers else universe
    if args.tickers:
        unknown = [t for t in tickers if t.upper() not in {u.upper() for u in universe}]
        if unknown:
            print(f"warning: tickers not in MVP universe: {unknown}", file=sys.stderr)

    # Download OHLCV per ticker, caching to parquet.
    # NOTE: split manifest is written AFTER this loop succeeds so a partial
    # download run never leaves a manifest that doesn't match the parquets
    # actually on disk (reviewer concern).
    print(f"[download] {len(tickers)} tickers, "
          f"window {settings.data.start_date}..{settings.data.end_date}")
    succeeded: List[str] = []
    failed: List[tuple[str, str]] = []
    manifest_path = cache_dir / "split.yaml"
    for i, ticker in enumerate(tickers, 1):
        path = cache_path_for(cache_dir, ticker)
        if path.is_file() and not args.full_download:
            print(f"  ({i:>3}/{len(tickers)}) {ticker:<6} cached -> {path.name}")
            succeeded.append(ticker)
            continue
        try:
            df = fetch_one(ticker, settings.data.start_date, settings.data.end_date)
            cache_one(cache_dir, ticker, df)
            print(f"  ({i:>3}/{len(tickers)}) {ticker:<6} downloaded ({len(df)} rows)")
            succeeded.append(ticker)
        except Exception as exc:  # noqa: BLE001
            print(f"  ({i:>3}/{len(tickers)}) {ticker:<6} FAILED: {exc}", file=sys.stderr)
            failed.append((ticker, str(exc)))

    # Write the split manifest only if we have at least one successful cache.
    if succeeded:
        write_split_manifest(manifest_path, split)
    else:
        if manifest_path.is_file():
            print(
                f"[manifest] all downloads failed; leaving previous {manifest_path} untouched",
                file=sys.stderr,
            )
        else:
            print("[manifest] no successful downloads; manifest NOT written",
                  file=sys.stderr)
    print(f"[manifest] {manifest_path}")
    print(f"          dev: {split.dev_start} .. {split.dev_end}")
    print(f"          oos: {split.oos_start} .. {split.oos_end}  [LOCKED until Fase 6]")

    # Continuity audit + per-ticker metadata.
    metadata = build_metadata(
        cache_dir, succeeded, settings.data.start_date, settings.data.end_date,
    )
    metadata_path = cache_dir / "_metadata.yaml"
    try:
        manifest_rel = str(manifest_path.relative_to(ROOT))
    except ValueError:
        manifest_rel = str(manifest_path)
    with metadata_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "data_window": {
                    "start_date": settings.data.start_date.isoformat(),
                    "end_date": settings.data.end_date.isoformat(),
                    "dev_end_date": settings.data.dev_end_date.isoformat(),
                },
                "tickers": metadata,
                "split_manifest": manifest_rel,
                "source": "yfinance",
                "interval": "1d",
                "auto_adjust": False,
            },
            f,
            sort_keys=True,
        )
    print(f"[metadata] {metadata_path}")

    short = [t for t, m in metadata.items() if m.get("status") == "short_history"]
    gapped = [t for t, m in metadata.items() if m.get("status") == "gap"]
    print()
    print("=== Phase 1 gate summary ===")
    print(f"  cached:   {len(succeeded)} / {len(tickers)}")
    print(f"  failed:   {len(failed)}")
    print(f"  short_history (>{SHORT_HISTORY_GRACE_DAYS}d from start): {len(short)}  {short}")
    print(f"  gap_audit (>2 bday):              {len(gapped)} {gapped}")
    print(f"  OOS locked:                       True (until {manifest_path.name} fences Fase 6)")

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

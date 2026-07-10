"""Phase 2 — gap mean-reversion EDA: detect, bucket, compute expectancy.

Pure math (no disk or network IO). The orchestrator in
scripts/eda_gap_expectancy.py wires these primitives to the real cache
and produces the markdown report.

Bucket convention (CONSISTENT across scalar helper and vectorized assign
and bucket_label_for_sign):

  - Boundaries are half-open [lo, hi) for non-terminal buckets: a value
    exactly on the lower edge belongs to that bucket; a value exactly on
    the upper edge belongs to the NEXT bucket.
  - The bottom bucket of each direction is half-open [lo_min, hi) — lo is
    inclusive because it is the operating-window lower bound (-2.0% /
    +0.3% respectively).
  - The top bucket of each direction is closed [lo, hi_max] — hi is
    inclusive because it is the operating-window upper bound (-0.3% /
    +2.0% respectively).
  - Net: -0.02 (or +0.003) lands in the bottom bucket, -0.003 (or +0.02)
    lands in the top bucket, and boundary values like -0.01, -0.006,
    +0.006, +0.01 land in the LOWER-in-index (more-negative / smaller-g)
    bucket.

Trade return is signed in the direction of fill:
  DOWN gap -> LONG candidate -> return = (Close - Open) / Open
  UP   gap -> SHORT candidate -> return = (Open - Close) / Open

Approximate Sharpe (annualized) = mean/std * sqrt(252 * frequency) where
frequency = n / total_dev_bars. NaN if std == 0 (single trade).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import math

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants — single source of truth for bucket boundaries and labels
# ---------------------------------------------------------------------------

# Default gate threshold from ROADMAP_MVP.md — Fase 2 requires "N >= 30".
# Overridable per-call via settings.gates.eda_min_trades_per_cell.
EXPECTANCY_MIN_TRADES_DEFAULT = 30

# ROADMAP: "celle con N<20 = dati insufficienti, non le usi"
INSUFFICIENT_DATA_CELL_THRESHOLD = 20

# Operating range from settings.yaml defaults.
GAP_MIN_PCT = 0.003   # 0.3%
GAP_MAX_PCT = 0.02    # 2.0%

# Bucket boundaries: half-open [lo, hi) for index 0..N-2, closed [lo, hi]
# for the topmost bucket (closes the operating window).
_DOWN_BOUNDS: List[Tuple[float, float, bool]] = [
    (-0.02,  -0.01,  False),  # [-2.0%, -1.0%)
    (-0.01,  -0.006, False),  # [-1.0%, -0.6%)
    (-0.006, -0.003, True),   # [-0.6%, -0.3%]  -- TOP, closed
]

_UP_BOUNDS: List[Tuple[float, float, bool]] = [
    (0.003,  0.006, False),   # [0.3%, 0.6%)
    (0.006,  0.01,  False),   # [0.6%, 1.0%)
    (0.01,   0.02,  True),    # [1.0%, 2.0%)  -- TOP, closed
]

DOWN_BUCKETS: Tuple[str, ...] = ("[-2.0%, -1.0%)", "[-1.0%, -0.6%)", "[-0.6%, -0.3%]")
UP_BUCKETS: Tuple[str, ...] = ("[0.3%, 0.6%)", "[0.6%, 1.0%)", "[1.0%, 2.0%)")


def _in_bucket(gap: float, lo: float, hi: float, hi_closed: bool) -> bool:
    """Single source of truth for membership test used by both the scalar
    helper `bucket_label_for_sign` and the vectorized `assign_bucket`."""
    if gap < lo:
        return False
    if hi_closed:
        return gap <= hi
    return gap < hi


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BucketRow:
    label: str
    direction: str  # "DOWN" or "UP"
    n: int
    mean_return: float
    std_return: float
    approx_sharpe: float  # NaN if std == 0
    frequency: float  # n / total_dev_bars

    def is_decisive(self, min_trades: int) -> bool:
        """Whether this bucket meets the gate criteria: N >= min_trades AND
        mean_return > 0."""
        return self.n >= min_trades and self.mean_return > 0.0


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str
    buckets: List[BucketRow]
    threshold: int
    total_dev_bars: int


# ---------------------------------------------------------------------------
# Gap computation
# ---------------------------------------------------------------------------


def ensure_prev_close_column(
    df: pd.DataFrame,
    *,
    ticker_col: str = "ticker",
    close_col: str = "close",
    date_col: str = "date",
    prev_close_col: str = "prev_close",
) -> pd.DataFrame:
    """Idempotent helper: ensures the frame has a `prev_close` column.

    If `prev_close` is already present, do nothing (synthetic test data and
    any pre-merged feeds). Otherwise, derive it by shifting the prior
    bar's close per ticker.

    Real yfinance data (per scripts/download_data.py) does NOT store
    prev_close — only OHLCV + ticker. To compute gap% on a real cache we
    need to look one bar back per ticker. After this helper, the first
    bar of each ticker has NaN prev_close (no prior bar in the frame);
    compute_gaps_df drops that bar — there is exactly one NaN-triggered
    drop per ticker per cached run, no look-ahead, no OOS leak.

    No-look-ahead guarantee: a bar whose date is dev_start has a
    predecessor at dev_start − 1 trading day. If that day is BEFORE
    dev_start, load_dev_bars already filtered it out. So the dev_start
    row has NaN prev_close and is correctly dropped. The dev_start+1 row's
    predecessor is the dev_start row (in frame), prev_close = close of
    dev_start row, which is dev_prev_close from the cache — the next
    bar's gap is computed from the immediately preceding cached bar,
    period, not from a traded price that exists only in the OOS window.
    """
    df = df.copy()
    if prev_close_col in df.columns:
        return df
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values([ticker_col, date_col]).reset_index(drop=True)
    df[prev_close_col] = df.groupby(ticker_col)[close_col].shift(1)
    return df


def compute_gaps_df(
    bars: pd.DataFrame,
    *,
    prev_close_col: str = "prev_close",
    open_col: str = "open",
    date_col: str = "date",
    close_col: str = "close",
    ticker_col: str = "ticker",
) -> pd.DataFrame:
    """For each bar, compute signed gap_pct and signed trade_return.

    Drops bars where prev_close is NaN (first day of a ticker in cache,
    no prior bar exists). The caller is expected to have arranged for
    `prev_close` to be present — either supplied directly (synthetic
    fixtures) or derived via `ensure_prev_close_column` (real yfinance
    data).

    Sorts by date so callers can hand us bars in any order without
    breaking the gap arithmetic across splits.
    """
    df = bars.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)
    if prev_close_col not in df.columns:
        # Caller forgot to ensure prev_close — derive it now and warn.
        df = ensure_prev_close_column(
            df,
            ticker_col=ticker_col,
            close_col=close_col,
            date_col=date_col,
            prev_close_col=prev_close_col,
        )
    df = df.dropna(subset=[prev_close_col])

    df["gap_pct"] = (df[open_col] - df[prev_close_col]) / df[prev_close_col]
    df["trade_return"] = _signed_return(df["gap_pct"], df[open_col], df[close_col])
    return df


def _signed_return(gap_pct: pd.Series, op: pd.Series, cl: pd.Series) -> pd.Series:
    """Sign the return in the direction of the fill.

    DOWN gap (< 0)  -> LONG  -> return = (Close - Open) / Open.
    UP   gap (> 0)  -> SHORT -> return = (Open - Close) / Open.

    gap == 0 falls into the SHORTS direction (sign = -1). Bucketing
    layers discard those rows because bucket_label_for_sign returns None
    for zero gaps; trade_return is computed purely for type-stability on
    the series and never flows into a gate decision.
    """
    sign = np.where(gap_pct < 0, 1.0, -1.0)
    return sign * (cl - op) / op


def bucket_label_for_sign(gap_pct: float) -> Optional[str]:
    """Return the bucket label for a SINGLE gap_pct value, or None if it is
    outside the operating range or is exactly 0. Same convention as the
    vectorized assign_bucket."""
    if gap_pct == 0.0:
        return None
    if gap_pct < 0:
        for (lo, hi, hi_closed), label in zip(_DOWN_BOUNDS, DOWN_BUCKETS):
            if _in_bucket(gap_pct, lo, hi, hi_closed):
                return label
        return None
    # gap_pct > 0
    for (lo, hi, hi_closed), label in zip(_UP_BOUNDS, UP_BUCKETS):
        if _in_bucket(gap_pct, lo, hi, hi_closed):
            return label
    return None


def assign_bucket(df: pd.DataFrame, *, gap_col: str = "gap_pct") -> pd.Series:
    """Vectorized bucket assignment for an entire DataFrame.

    Returns a Series[str|None] aligned to df.index. Uses the SAME
    membership semantics as `bucket_label_for_sign` so the scalar and
    vectorized paths agree on boundaries.
    """
    gap = df[gap_col]
    labels = pd.Series([None] * len(df), index=df.index, dtype=object)
    for (lo, hi, hi_closed), direction_bounds, direction_labels in (
        (_DOWN_BOUNDS, _DOWN_BOUNDS, DOWN_BUCKETS),
        (_UP_BOUNDS, _UP_BOUNDS, UP_BUCKETS),
    ):
        for (lo_, hi_, hi_closed_), lab in zip(direction_bounds, direction_labels):
            mask = (gap >= lo_) & ((gap <= hi_) if hi_closed_ else (gap < hi_))
            labels = labels.mask(mask, lab)
    return labels


# ---------------------------------------------------------------------------
# Bucketed expectancy
# ---------------------------------------------------------------------------


def compute_buckets(
    df: pd.DataFrame,
    *,
    min_trades: int,
    gap_col: str = "gap_pct",
    return_col: str = "trade_return",
    total_dev_bars: Optional[int] = None,
) -> List[BucketRow]:
    """Bucket-level expectancy: n, mean, std, approx Sharpe (annualized).

    Returns only buckets with at least `min_trades` observations. Buckets
    with N < min_trades are excluded — the orchestrator marks them
    "Insufficient Data" in the markdown report.

    `total_dev_bars` controls the Sharpe frequency component (n / total).
    If None, `total_dev_bars = len(df)` (use the full dev frame as
    denominator: bars without a usable gap are inside the row count but
    outside any bucket, so true frequency is slightly overestimated — good
    enough as an APPROXIMATE Sharpe for the gate).
    """
    df = df.copy()
    df["__bucket"] = assign_bucket(df, gap_col=gap_col)
    df_in = df.dropna(subset=["__bucket"])
    total = total_dev_bars if total_dev_bars is not None else max(len(df), 1)
    out: List[BucketRow] = []
    for label, direction in [
        *((lab, "DOWN") for lab in DOWN_BUCKETS),
        *((lab, "UP") for lab in UP_BUCKETS),
    ]:
        sub = df_in.loc[df_in["__bucket"] == label, return_col]
        n = int(len(sub))
        if n < min_trades:
            continue
        mean = float(sub.mean())
        std = float(sub.std(ddof=1)) if n > 1 else 0.0
        sharpe = float("nan") if std == 0.0 else (mean / std) * math.sqrt(252.0 * (n / total))
        out.append(BucketRow(
            label=label,
            direction=direction,
            n=n,
            mean_return=mean,
            std_return=std,
            approx_sharpe=sharpe,
            frequency=n / total,
        ))
    return out


def evaluate_gate(
    df: pd.DataFrame,
    *,
    min_trades: int = EXPECTANCY_MIN_TRADES_DEFAULT,
) -> GateResult:
    """Apply the ROADMAP_Fase_2 gate.

      - At least ONE bucket has N >= min_trades AND mean_return > 0.

    Returns GateResult with the per-bucket table (min_trades=1) so the
    orchestrator can print diagnostics regardless of the verdict.
    """
    buckets = compute_buckets(df, min_trades=1)
    decisive = [b for b in buckets if b.is_decisive(min_trades)]
    if decisive:
        return GateResult(
            passed=True,
            reason="gate_pass",
            buckets=buckets,
            threshold=min_trades,
            total_dev_bars=int(len(df)),
        )
    return GateResult(
        passed=False,
        reason="no_bucket_with_positive_edge_at_threshold",
        buckets=buckets,
        threshold=min_trades,
        total_dev_bars=int(len(df)),
    )

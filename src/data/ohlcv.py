"""OHLCV dataset management: cache layout + dev/OOS split + quality gates.

Phase 1 deliverables (per docs/superpowers/plans/ROADMAP_MVP.md):
  - Cache in data/cache/*.parquet
  - 70% dev / 30% OOS split prepared
  - OOS window 'isolated in a file/flag separato e non viene toccato prima
    della Fase 6'
  - No 'gap > 2 giorni consecutivi non giustificato da festività'

The split manifest IS that flag. It carries an oos_lock_message + a
`locked_until_phase` field, and `assert_oos_locked()` raises if you try to
use OOS bars before that phase. Together with `check_continuity()` this
closes the two Phase 1 gates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Constants — single source of truth for the lock message
# ---------------------------------------------------------------------------

# Phase at which the OOS window may be used, per ROADMAP_MVP.md.
OOS_LOCKED_UNTIL_PHASE = "Fase 6"
OOS_UNLOCK_PHASE_NUM = 6  # numeric form for assert_oos_locked()
DEFAULT_OOS_LOCK_MESSAGE = (
    f"OOS window locked until {OOS_LOCKED_UNTIL_PHASE} of the roadmap; "
    "do not use these bars for parameter calibration. "
    "See docs/superpowers/plans/ROADMAP_MVP.md."
)

# Maximum tolerable consecutive-trading-day gap inside the cached history.
# Roadmap gate: "nessun buco > 2 giorni consecutivi non giustificato da festività".
# 2 = up to 2 days; everything beyond is flagged.
MAX_CONSECUTIVE_GAP_DAYS = 2

# Maximum tolerable late-start of cached history vs. configured start.
# Tickers whose actual_start is more than SHORT_HISTORY_GRACE_DAYS after the
# configured start_date are flagged 'short_history' in metadata; they still
# pass the gate but are surfaced so Phase 2 EDA can decide whether to enroll
# them with a per-ticker start_date override.
SHORT_HISTORY_GRACE_DAYS = 180

# Renames / IPOs in the MVP universe that can't return 2019 data under the
# current ticker. Each entry overrides the ticker's effective expected_start
# so check_continuity + _metadata.yaml don't flag them as 'short_history'
# when their history genuinely starts at a later date.
# Source notes:
#   PANW: Palo Alto Networks IPO Oct 2019.
#   RTX:  Raytheon Technologies renamed to RTX mid-2023; predecessor was RYT.
#   ELV:  Anthem renamed to Elevance Health (ELV) late 2022.
TICKER_ALIASES: dict = {
    "PANW": date(2019, 10, 1),
    "RTX": date(2023, 5, 1),
    "ELV": date(2022, 12, 1),
}


def ticker_effective_start(ticker: str, default: date) -> date:
    """Per-ticker override of the audit expected_start date.

    Falls back to `default` for tickers without a rename history.
    """
    return TICKER_ALIASES.get(ticker.upper(), default)


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Split:
    dev_start: date
    dev_end: date
    oos_start: date
    oos_end: date
    oos_lock_message: str = DEFAULT_OOS_LOCK_MESSAGE

    def __post_init__(self) -> None:
        if not (self.dev_start <= self.dev_end):
            raise ValueError(f"dev window invalid: {self.dev_start} > {self.dev_end}")
        if not (self.oos_start <= self.oos_end):
            raise ValueError(f"OOS window invalid (empty): {self.oos_start} > {self.oos_end}")
        if not (self.dev_end < self.oos_start):
            raise ValueError(
                f"OOS must start strictly after dev_end ({self.dev_end}); "
                f"oos_start={self.oos_start}"
            )

    def in_dev_window(self, dt: date) -> bool:
        return self.dev_start <= dt <= self.dev_end

    def in_oos_window(self, dt: date) -> bool:
        return self.oos_start <= dt <= self.oos_end


def compute_split(data_cfg) -> Split:
    """Derive the dev/OOS split from settings.

    OOS starts the day AFTER dev_end_date (so the dev end day itself is
    inside the development window, not the validation window).

    The returned Split is stamped with the default lock message so that
    manifest round-trip equality (`written == loaded`) holds: if a caller
    persists this Split and reads it back, the two objects compare equal.
    """
    oos_start = data_cfg.dev_end_date + timedelta(days=1)
    return Split(
        dev_start=data_cfg.start_date,
        dev_end=data_cfg.dev_end_date,
        oos_start=oos_start,
        oos_end=data_cfg.end_date,
    )


# ---------------------------------------------------------------------------
# OOS lock enforcement
# ---------------------------------------------------------------------------


class OOSLockedError(RuntimeError):
    """Raised when downstream code tries to use OOS bars before Fase 6."""


def _phase_num(name: str) -> int:
    """Extract the phase number from a label like 'Fase 6' or 'Phase 10'.

    Returns 0 if no number is found (treated as the earliest phase).
    """
    digits = "".join(ch for ch in name if ch.isdigit())
    return int(digits) if digits else 0


import re  # noqa: F401  (kept at top — see dev_policy)

_PHASE_LABEL = re.compile(r"^(Fase|Phase)\s+\d+$")


def assert_oos_locked(current_phase: str, split: Split) -> None:
    """Raise OOSLockedError if current_phase hasn't unlocked the OOS window.

    Phase < OOS_UNLOCK_PHASE_NUM keeps the lock. Both 'Fase N' and 'Phase N'
    labels are accepted and validated: a label that doesn't match the
    documented shape raises ValueError before the lock check fires.
    """
    if not _PHASE_LABEL.match(current_phase):
        raise ValueError(
            f"current_phase must look like 'Fase N' or 'Phase N', got {current_phase!r}"
        )
    if _phase_num(current_phase) < OOS_UNLOCK_PHASE_NUM:
        raise OOSLockedError(split.oos_lock_message)


# ---------------------------------------------------------------------------
# Cache paths
# ---------------------------------------------------------------------------


def cache_path_for(cache_dir: Path, ticker: str) -> Path:
    """Where the cached OHLCV parquet for a given ticker lives.

    Layout: <cache_dir>/<TICKER>.parquet (one file per ticker).
    """
    safe = ticker.upper().replace(".", "_").replace("-", "_")
    return cache_dir / f"{safe}.parquet"


# ---------------------------------------------------------------------------
# Split manifest (YAML on disk) — the OOS isolation flag
# ---------------------------------------------------------------------------


def write_split_manifest(path: Path, split: Split) -> None:
    """Persist the dev/OOS split as a YAML file.

    The manifest always carries a default lock_message so the OOS isolation
    is recoverable even from a freshly-written manifest.
    """
    payload = {
        "dev": {
            "start": split.dev_start.isoformat(),
            "end": split.dev_end.isoformat(),
        },
        "oos": {
            "start": split.oos_start.isoformat(),
            "end": split.oos_end.isoformat(),
            "locked_until_phase": OOS_LOCKED_UNTIL_PHASE,
            "lock_message": split.oos_lock_message or DEFAULT_OOS_LOCK_MESSAGE,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def read_split_manifest(path: Path) -> Split:
    """Read a previously written split manifest back into a Split object.

    Round-trip stable: any Split written with `write_split_manifest` and
    re-read with this function compares equal under `==`.
    """
    if not path.is_file():
        raise FileNotFoundError(f"split manifest missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    oos_block = payload["oos"]
    return Split(
        dev_start=date.fromisoformat(payload["dev"]["start"]),
        dev_end=date.fromisoformat(payload["dev"]["end"]),
        oos_start=date.fromisoformat(oos_block["start"]),
        oos_end=date.fromisoformat(oos_block["end"]),
        oos_lock_message=str(oos_block["lock_message"]),
    )


# ---------------------------------------------------------------------------
# Cached OHLCV loader
# ---------------------------------------------------------------------------


def load_cached_ohlcv(cache_dir: Path, ticker: str) -> pd.DataFrame:
    """Load OHLCV bars for a ticker from local parquet cache.

    Raises FileNotFoundError if the cache file is missing — phase 1 expects
    the download step to populate the cache.
    """
    path = cache_path_for(cache_dir, ticker)
    if not path.is_file():
        raise FileNotFoundError(
            f"no cached OHLCV for {ticker} at {path}; "
            "run scripts/download_data.py first."
        )
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# Continuity / gap gate
# ---------------------------------------------------------------------------


def _us_federal_holidays(start: date, end: date) -> set:
    """Memoized fetch of US federal holidays in the [start, end] window."""
    from pandas.tseries.holiday import USFederalHolidayCalendar

    return set(USFederalHolidayCalendar().holidays(start=start, end=end))


def _is_us_business_day(d: date, _holidays: Optional[set] = None) -> bool:
    """Cheap approximation: Mon–Fri minus US federal holidays.

    The caller is expected to pass the memoized holiday set covering the
    audit window; if not, the function falls back to per-call construction
    (one extra holiday query, not 2200).
    """
    if d.weekday() >= 5:
        return False
    if _holidays is None:
        _holidays = _us_federal_holidays(
            d - timedelta(days=30), d + timedelta(days=30)
        )
    return pd.Timestamp(d) not in _holidays


def check_continuity(df: pd.DataFrame, expected_start: date, expected_end: date,
                     *,
                     max_consecutive_gap: int = MAX_CONSECUTIVE_GAP_DAYS,
                     date_col: str = "date") -> List[Tuple[date, date, int]]:
    """Find gaps in trading-day coverage that exceed `max_consecutive_gap`.

    Args:
        df: cached bars with a date column.
        expected_start, expected_end: calendar window the cache should cover.
        max_consecutive_gap: max acceptable run of missing days.
        date_col: column holding bar dates.

    Returns:
        List of (gap_start, gap_end, gap_length_in_business_days) tuples,
        each representing a gap LARGER than the tolerance. Returns ONLY
        gaps inside the calendar range (actual_start..actual_end).
    """
    if date_col not in df.columns:
        raise ValueError(f"column {date_col!r} not in DataFrame")
    if df.empty:
        raise ValueError("cannot check continuity on an empty DataFrame")

    dates = pd.to_datetime(df[date_col]).dt.date.sort_values().unique().tolist()
    actual_start, actual_end = dates[0], dates[-1]

    # Clip the expected window to what we actually have cached.
    expected_start = max(expected_start, actual_start)
    expected_end = min(expected_end, actual_end)

    # One holiday query covers the entire audit window.
    holidays = _us_federal_holidays(
        expected_start - timedelta(days=1), expected_end + timedelta(days=1)
    )

    # Build expected trading days in the actual range.
    expected = []
    cur = expected_start
    while cur <= expected_end:
        if _is_us_business_day(cur, _holidays=holidays):
            expected.append(cur)
        cur += timedelta(days=1)

    present = set(dates)
    missing = [d for d in expected if d not in present]

    # Collapse runs of consecutive missing business days.
    gaps: List[Tuple[date, date, int]] = []
    run_start: Optional[date] = None
    prev: Optional[date] = None
    for d in missing:
        if run_start is None:
            run_start = d
        elif (d - prev).days != 1:
            run_len = len(pd.bdate_range(run_start, prev))
            if run_len > max_consecutive_gap:
                gaps.append((run_start, prev, run_len))
            run_start = d
        prev = d
    if run_start is not None and prev is not None:
        run_len = len(pd.bdate_range(run_start, prev))
        if run_len > max_consecutive_gap:
            gaps.append((run_start, prev, run_len))
    return gaps


# ---------------------------------------------------------------------------
# OHLCV schema normalizer (used by scripts/download_data.fetch_one)
# ---------------------------------------------------------------------------


class OHLCVSchemaError(RuntimeError):
    """Raised when yfinance returns a frame that doesn't carry OHLCV + date.

    We treat this as a hard fail: the retry loop in fetch_one does NOT
    retry on schema mismatch (no transient network issue can fix this).
    """


def normalize_ohlcv_columns(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normalize a yfinance frame to a flat frame with a 'date' column.

    Two schemas appear in practice from yfinance.download(...):

      Schema A (current default — `auto_adjust=False`, single ticker):
        columns = MultiIndex like [('Date', ''), ('Open', ''), ('Close', ''), ...]
        index   = RangeIndex (or DatetimeIndex if reset_index not applied)

      Schema B (older yfinance / multi-ticker code path):
        columns = flat list ['Date', 'Open', ...] (no MultiIndex)
        index   = DatetimeIndex named 'Date'

    The helper handles both by:
      1. reset_index() — promotes a named DatetimeIndex to a 'date' column.
      2. Flatten any MultiIndex columns to first level ('Date', 'Open', ...).
      3. Lowercase string columns.
      4. Look for 'date'; promote 'datetime' if needed.
      5. Raise OHLCVSchemaError if 'date' is still missing.

    We deliberately do NOT guess by renaming an arbitrary column to 'date'
    — a frame whose first column is 'Open' must fail loudly so the
    operator notices. Silent rename here is exactly the failure mode the
    OOS-isolation Phase 1 gate is designed to prevent.
    """
    df = df.reset_index()
    # Schema A: flatten MultiIndex columns.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() if isinstance(c, str) else c for c in df.columns]
    if "date" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "date"})
    if "date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index().rename(columns={"index": "date"})
    if "date" not in df.columns:
        raise OHLCVSchemaError(
            f"unexpected yfinance schema for {ticker}; no `date` column after "
            f"normalization. columns={list(df.columns)}"
        )
    return df


# ---------------------------------------------------------------------------
# Optional helper: label each bar with its window for downstream code.
# ---------------------------------------------------------------------------


def label_window(df: pd.DataFrame, split: Split, date_col: str = "date") -> pd.DataFrame:
    """Add a 'window' column ('dev' | 'oos') to a bar-level DataFrame.

    Out-of-window rows are kept but their window is None — callers must
    decide what to do with them. (Earlier behavior raised on the first such
    row; that turned out too aggressive for downstream filters.)
    """
    if date_col not in df.columns:
        raise ValueError(f"column {date_col!r} not present in DataFrame")

    def _window(d: date) -> Optional[str]:
        if split.in_dev_window(d):
            return "dev"
        if split.in_oos_window(d):
            return "oos"
        return None

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col]).dt.date
    df["window"] = df[date_col].apply(_window)
    return df

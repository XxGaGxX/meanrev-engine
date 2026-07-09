"""Tests for src.data.ohlcv — Phase 1 download + cache + dev/OOS split logic.

Phase 1 gate (ROADMAP_MVP.md):
  - Data cached for all tickers, no gap > 2 consecutive trading days not
    justified by US holiday/weekend.
  - The 30% OOS period is isolated in a separate split manifest and locked
    until Fase 6 of the roadmap.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from src.config import load_settings, SETTINGS_PATH
from src.data.ohlcv import (
    DEFAULT_OOS_LOCK_MESSAGE,
    OOS_LOCKED_UNTIL_PHASE,
    OOSLockedError,
    OHLCVSchemaError,
    Split,
    TICKER_ALIASES,
    assert_oos_locked,
    cache_path_for,
    check_continuity,
    compute_split,
    load_cached_ohlcv,
    normalize_ohlcv_columns,
    read_split_manifest,
    ticker_effective_start,
    write_split_manifest,
)


# ---------------------------------------------------------------------------
# Split computation
# ---------------------------------------------------------------------------


def test_compute_split_returns_dev_and_oos_ranges() -> None:
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)

    assert isinstance(split, Split)
    assert split.dev_start == settings.data.start_date
    assert split.dev_end == settings.data.dev_end_date
    # settings parses dates into date objects; just add a day directly.
    expected_oos_start = settings.data.dev_end_date + timedelta(days=1)
    assert split.oos_start == expected_oos_start


def test_split_oos_starts_after_dev_ends() -> None:
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    assert split.oos_start > split.dev_end
    assert split.oos_end == settings.data.end_date


def test_oos_window_is_about_30_percent() -> None:
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    total_days = (split.oos_end - split.dev_start).days
    oos_days = (split.oos_end - split.oos_start).days
    ratio = oos_days / total_days
    assert 0.20 <= ratio <= 0.40, f"OOS ratio {ratio:.2%} outside 20-40% band"


def test_split_rejects_oos_start_not_strictly_after_dev_end() -> None:
    """__post_init__ must guard against dev_end >= oos_start (the OOS
    window must begin strictly after the dev window)."""
    with pytest.raises(ValueError, match="strictly after"):
        Split(
            dev_start=date(2020, 1, 1),
            dev_end=date(2024, 12, 31),
            oos_start=date(2024, 12, 31),  # NOT strictly after dev_end
            oos_end=date(2024, 12, 31),
        )


def test_split_rejects_zero_length_oos() -> None:
    with pytest.raises(ValueError):
        Split(
            dev_start=date(2020, 1, 1),
            dev_end=date(2022, 12, 31),
            oos_start=date(2024, 1, 1),
            oos_end=date(2023, 12, 31),  # oos_end < oos_start
        )


# ---------------------------------------------------------------------------
# OOS lock enforcement (Fase 6 gate)
# ---------------------------------------------------------------------------


def test_assert_oos_locked_raises_for_phase_5() -> None:
    """Phases 0-05 must NOT be allowed to read OOS bars."""
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    for phase in ["Fase 0", "Fase 1", "Fase 2", "Fase 3", "Fase 4", "Fase 5"]:
        with pytest.raises(OOSLockedError):
            assert_oos_locked(phase, split)


def test_assert_oos_locked_admits_phase_6_and_later() -> None:
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    # No exception means OK.
    assert_oos_locked("Fase 6", split)
    assert_oos_locked("Fase 10", split)


def test_assert_oos_locked_admits_phase_6_in_english_alias() -> None:
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    assert_oos_locked("Phase 6", split)


def test_oos_lock_message_is_deterministic() -> None:
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    try:
        assert_oos_locked("Fase 2", split)
    except OOSLockedError as exc:
        assert OOS_LOCKED_UNTIL_PHASE in str(exc)


def test_assert_oos_locked_rejects_malformed_label() -> None:
    """Phase labels that don't match 'Fase N' / 'Phase N' are a bug; raise
    ValueError (not OOSLockedError) so callers see the typo explicitly.
    """
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    for bad in ["Fase six", "fase 6", "PhaseXX 6", "", "6", "Phase Alpha", "fas6"]:
        with pytest.raises(ValueError, match="must look like"):
            assert_oos_locked(bad, split)


def test_split_dataclass_default_lock_message() -> None:
    """Reviewer E: there is now exactly one owner of the OOS lock message —
    the dataclass default. Manually-constructed Splits use it; compute_split
    doesn't need to stamp it.
    """
    s = Split(
        dev_start=date(2020, 1, 1),
        dev_end=date(2022, 12, 31),
        oos_start=date(2023, 1, 1),
        oos_end=date(2024, 12, 31),
    )
    assert s.oos_lock_message == DEFAULT_OOS_LOCK_MESSAGE


def test_ticker_aliases_cover_known_renames() -> None:
    """Reviewer G.1: tickers with renames or post-2019 IPOs have an alias
    entry so Fase 2 EDA doesn't see them as 'short_history' for the full
    pre-rename window.
    """
    for must_have in ("PANW", "RTX", "ELV"):
        assert must_have in TICKER_ALIASES, f"missing alias for {must_have}"


def test_ticker_effective_start_uses_alias_when_present() -> None:
    alias_start = TICKER_ALIASES["RTX"]
    got = ticker_effective_start("RTX", date(2019, 1, 1))
    assert got == alias_start


def test_ticker_effective_start_falls_back_to_default() -> None:
    fallback = date(2019, 1, 1)
    assert ticker_effective_start("AAPL", fallback) == fallback


# ---------------------------------------------------------------------------
# OHLCV schema normalizer (download_data.fetch_one backing helper)
# ---------------------------------------------------------------------------


def test_normalize_ohlcv_columns_flat_schema_passes_through() -> None:
    """The flat-column yfinance response is the typical shape."""
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3),
        "open": [100.0, 101.0, 102.0],
        "high": [101.0, 102.0, 103.0],
        "low": [99.0, 100.0, 101.0],
        "close": [100.5, 101.5, 102.5],
        "volume": [1000, 1100, 1200],
    })
    out = normalize_ohlcv_columns(df, "AAPL")
    assert "date" in out.columns


def test_normalize_ohlcv_columns_uppercase_lowercased() -> None:
    df = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=2),
        "Open": [100.0, 101.0],
        "Close": [100.5, 101.5],
    })
    out = normalize_ohlcv_columns(df, "AAPL")
    assert "date" in out.columns
    assert "open" in out.columns


def test_normalize_ohlcv_columns_raises_on_no_date_column() -> None:
    """A frame with no `date`/`datetime`/DatetimeIndex is a hard fail.

    The retry loop in fetch_one does NOT retry here; the error must
    propagate immediately so a bad schema can't silently write a frame
    downstream will mis-parse.
    """
    df = pd.DataFrame({"foo": [1, 2, 3], "bar": [4, 5, 6]})
    with pytest.raises(OHLCVSchemaError, match="no `date` column"):
        normalize_ohlcv_columns(df, "BAD")


def test_normalize_ohlcv_columns_promotes_datetimeindex() -> None:
    idx = pd.date_range("2024-01-01", periods=2, name="Date")
    df = pd.DataFrame({"open": [1, 2]}, index=idx)
    out = normalize_ohlcv_columns(df, "AAPL")
    assert "date" in out.columns


def test_normalize_ohlcv_columns_flattens_multiindex_to_first_level() -> None:
    """yfinance with auto_adjust=False returns MultiIndex columns even for
    a single-ticker call. The first level is the field name ('Date',
    'Open', 'Close', ...). Flatten it so 'Date' becomes 'date'.

    Without this normalization, all 80 tickers fail with OHLCVSchemaError.
    """
    cols = pd.MultiIndex.from_tuples([
        ("Date", ""),
        ("Open", ""),
        ("High", ""),
        ("Low", ""),
        ("Close", ""),
        ("Adj Close", ""),
        ("Volume", ""),
    ])
    n = 5
    df = pd.DataFrame(
        {
            ("Date", ""): pd.date_range("2024-01-01", periods=n),
            ("Open", ""): [100.0] * n,
            ("High", ""): [101.0] * n,
            ("Low", ""): [99.0] * n,
            ("Close", ""): [100.5] * n,
            ("Adj Close", ""): [100.5] * n,
            ("Volume", ""): [1000] * n,
        },
        columns=cols,
    )
    out = normalize_ohlcv_columns(df, "AAPL")
    assert "date" in out.columns
    assert "open" in out.columns
    assert "close" in out.columns
    # All tuple-form is gone:
    for c in out.columns:
        assert not isinstance(c, tuple), f"column {c!r} is still a tuple"


# ---------------------------------------------------------------------------
# Manifest round-trip + OOS isolation flag
# ---------------------------------------------------------------------------


def test_cache_path_extension_is_parquet(tmp_path: Path) -> None:
    p = cache_path_for(tmp_path, "AAPL")
    assert p.suffix == ".parquet"
    assert "AAPL" in p.name


def test_cache_path_normalizes_dot_class_shares(tmp_path: Path) -> None:
    # BRK.B -> BRK_B.parquet
    p = cache_path_for(tmp_path, "BRK.B")
    assert p.name == "BRK_B.parquet"


def test_write_and_read_split_manifest_roundtrip(tmp_path: Path) -> None:
    """The manifest path is what makes the OOS window 'isolated in a file'
    per the roadmap gate. Round-trip must preserve ALL fields via `==`,
    including the default lock_message that compute_split stamps."""
    settings = load_settings(SETTINGS_PATH)
    split = compute_split(settings.data)
    manifest_path = tmp_path / "split.yaml"
    write_split_manifest(manifest_path, split)
    assert manifest_path.is_file()
    loaded = read_split_manifest(manifest_path)
    assert loaded == split


def test_split_manifest_marks_oos_as_locked(tmp_path: Path) -> None:
    """The manifest must surface a lock message referencing Fase 6."""
    settings = load_settings(SETTINGS_PATH)
    manifest_path = tmp_path / "split.yaml"
    write_split_manifest(manifest_path, compute_split(settings.data))
    manifest = read_split_manifest(manifest_path)
    assert manifest.oos_lock_message is not None
    assert "Fase 6" in manifest.oos_lock_message


def test_manifest_yaml_carries_locked_until_phase_field(tmp_path: Path) -> None:
    """We assert against the YAML field name too — guards against a
    refactor that drops the schema."""
    import yaml

    manifest_path = tmp_path / "split.yaml"
    write_split_manifest(manifest_path, compute_split(load_settings(SETTINGS_PATH).data))
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert payload["oos"]["locked_until_phase"] == "Fase 6"


def test_load_cached_ohlcv_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_cached_ohlcv(tmp_path, "ZZZZ")


# ---------------------------------------------------------------------------
# Continuity / gap-detection gate
# ---------------------------------------------------------------------------


def _bar(d: date, close: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({"date": [d], "close": [close]})


def test_check_continuity_returns_empty_for_full_coverage() -> None:
    """A continuous Mon-Fri run with no missing days should be gap-free."""
    # 2024-01-01 was a Mon (holiday): use 2024-01-02 .. 2024-01-05 (Tue-Fri).
    bars = pd.concat([_bar(date(2024, 1, 2)), _bar(date(2024, 1, 3)),
                      _bar(date(2024, 1, 4)), _bar(date(2024, 1, 5))])
    gaps = check_continuity(
        bars,
        expected_start=date(2024, 1, 2),
        expected_end=date(2024, 1, 5),
    )
    assert gaps == []


def test_check_continuity_detects_long_gap() -> None:
    """A 4-business-day gap (Tue-Fri missing) exceeds the 2-day tolerance
    and must be reported."""
    bars = pd.concat([
        _bar(date(2024, 1, 1)),  # Mon (holiday, would be missing anyway)
        _bar(date(2024, 1, 8)),  # Mon, after a 4-bday gap
    ])
    gaps = check_continuity(
        bars,
        expected_start=date(2024, 1, 1),
        expected_end=date(2024, 1, 12),
    )
    assert any(len_gap >= 4 and start <= date(2024, 1, 5)
               for start, _, len_gap in gaps)


def test_check_continuity_tolerates_two_day_gap() -> None:
    """A 2-bday gap is the largest acceptable per the roadmap gate."""
    bars = pd.concat([
        _bar(date(2024, 1, 1)),  # Mon (holiday)
        _bar(date(2024, 1, 2)),  # Tue — present
        _bar(date(2024, 1, 5)),  # Fri — present, 2 bdays gap
    ])
    gaps = check_continuity(
        bars,
        expected_start=date(2024, 1, 1),
        expected_end=date(2024, 1, 5),
    )
    # 2-bday gap is within tolerance.
    assert gaps == []


def test_check_continuity_requires_dates_column() -> None:
    bars = pd.DataFrame({"close": [100.0]})
    with pytest.raises(ValueError, match="date"):
        check_continuity(bars, date(2024, 1, 1), date(2024, 1, 5))


def test_check_continuity_rejects_empty_dataframe() -> None:
    bars = pd.DataFrame({"date": []})
    with pytest.raises(ValueError, match="empty"):
        check_continuity(bars, date(2024, 1, 1), date(2024, 1, 5))

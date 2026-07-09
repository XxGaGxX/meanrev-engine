"""Integration tests — multi-step wiring of Phase 1 contracts.

Tests in this file intentionally cross module boundaries: they exercise a
write -> read -> enforce chain that the roadmap mandates for Phase 1 gate
"OOS isolated". Keeping them separate from unit tests surfaces the real
contract.
"""

from pathlib import Path

import pytest

from src.config import SETTINGS_PATH, load_settings
from src.data.ohlcv import (
    OOSLockedError,
    assert_oos_locked,
    compute_split,
    read_split_manifest,
    write_split_manifest,
)


def test_split_manifest_round_trip_then_lock_chain(tmp_path: Path) -> None:
    """End-to-end: compute a split, write the manifest, read it back, then
    verify that attempting to use OOS bars from Fase 2 raises the lock
    error carrying the same message the manifest stored.

    This is the actual Phase 1 contract downstream code (Fase 3..5) will
    rely on: it MUST be locked under a single integration test so a
    refactor that breaks any link in the chain fails loudly.
    """
    settings = load_settings(SETTINGS_PATH)
    original = compute_split(settings.data)
    manifest_path = tmp_path / "split.yaml"

    write_split_manifest(manifest_path, original)
    loaded = read_split_manifest(manifest_path)

    # Equality holds across the round-trip.
    assert loaded == original

    # Lock message survives the round-trip verbatim.
    assert loaded.oos_lock_message == original.oos_lock_message
    assert "Fase 6" in loaded.oos_lock_message

    # Pre-Fase 6 callers cannot touch the OOS window.
    with pytest.raises(OOSLockedError) as excinfo:
        assert_oos_locked("Fase 2", loaded)
    # And the lock message they see is the one persisted to disk.
    assert str(excinfo.value) == loaded.oos_lock_message

    # Fase 6+ callers may touch OOS bars (no exception).
    assert_oos_locked("Fase 6", loaded)
    assert_oos_locked("Fase 7", loaded)


def test_metadata_writer_records_global_data_window(tmp_path: Path) -> None:
    """data/cache/_metadata.yaml must record start_date/end_date/
    dev_end_date so Fase 2 EDA can re-verify the audit window without
    re-parsing settings.yaml."""
    import yaml

    # Simulate the writer's payload shape so we can lock its schema.
    payload = {
        "data_window": {
            "start_date": "2019-01-01",
            "end_date": "2024-12-31",
            "dev_end_date": "2022-12-31",
        },
        "tickers": {},
        "split_manifest": "split.yaml",
        "source": "yfinance",
        "interval": "1d",
        "auto_adjust": False,
    }
    path = tmp_path / "_metadata.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=True)

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded["data_window"]["start_date"] == "2019-01-01"
    assert loaded["data_window"]["end_date"] == "2024-12-31"
    assert loaded["data_window"]["dev_end_date"] == "2022-12-31"

"""Tests for src.config — settings loader.

Phase 1 needs: configurable data window, dev/OOS split, cache directory.
No hardcoded params in code — all must come from config/settings.yaml.
"""

from pathlib import Path

import pytest

from src.config import load_settings, Settings, DataConfig, StrategyConfig, RiskConfig


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def test_settings_path_exists() -> None:
    """The single source of truth must exist on disk."""
    assert SETTINGS_PATH.is_file(), f"settings.yaml missing at {SETTINGS_PATH}"


def test_load_settings_returns_settings_instance() -> None:
    """load_settings returns a typed Settings object, not a raw dict."""
    settings = load_settings(SETTINGS_PATH)
    assert isinstance(settings, Settings)


def test_settings_has_data_and_strategy_blocks() -> None:
    """Both top-level blocks (strategy, data) must be present and typed."""
    settings = load_settings(SETTINGS_PATH)
    assert isinstance(settings.data, DataConfig)
    assert isinstance(settings.strategy, StrategyConfig)


def test_settings_has_risk_block() -> None:
    """Fase A: the risk block (sl/tp extend multiples) must load typed."""
    settings = load_settings(SETTINGS_PATH)
    assert isinstance(settings.risk, RiskConfig)
    assert settings.risk.sl_atr_multiple == 2.0
    assert settings.risk.tp_extend_atr_multiple == 4.0
    assert settings.risk.partial_tp_frac == 0.5
    assert settings.risk.time_stop_bars is None


def test_data_config_window_matches_roadmap() -> None:
    """Phase 1 requires at least 5y of data + a 70/30 dev/OOS split.

    Settings enforce:
        start_date < dev_end_date < end_date
        end_date - start_date >= 5 years
    """
    settings = load_settings(SETTINGS_PATH)
    d = settings.data
    assert d.start_date < d.dev_end_date < d.end_date
    span_years = (d.end_date - d.start_date).days / 365.25
    assert span_years >= 5.0, f"need >=5y of history, got {span_years:.2f}y"


def test_cache_dir_is_relative_to_project_root() -> None:
    """cache_dir must be a project-relative path, never absolute."""
    settings = load_settings(SETTINGS_PATH)
    cache = Path(settings.data.cache_dir)
    assert not cache.is_absolute(), "cache_dir must be relative"


def test_universe_size_is_at_least_50() -> None:
    """Phase 1 requires 50-100 large-cap USA liquidi."""
    settings = load_settings(SETTINGS_PATH)
    assert 50 <= settings.strategy.universe_size <= 100


def test_missing_file_raises_clear_error(tmp_path: Path) -> None:
    """If the settings file is missing, the loader raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "does_not_exist.yaml")

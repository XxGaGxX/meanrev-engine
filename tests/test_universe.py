"""Tests for src.data.universe — curated liquid large-cap USA tickers.

Phase 1 needs:
  - 50-100 large-cap USA tickers
  - All symbols must be non-empty strings in standard format (A-Z, up to 5 chars)
  - Universe size must match settings.strategy.universe_size

NOTE: For MVP we don't reconstruct the historical S&P 500 (survivorship bias
is acknowledged in the audit but deferred to v2). Universe is the CURRENT
S&P 500 top large-caps, fixed.
"""

from src.config import load_settings, SETTINGS_PATH
from src.data.universe import get_universe, MVP_UNIVERSE


def test_get_universe_returns_list_of_strings() -> None:
    universe = get_universe()
    assert isinstance(universe, list)
    assert all(isinstance(t, str) for t in universe)


def test_universe_size_matches_settings() -> None:
    """settings.yaml says universe_size: 80 → we should produce 80 tickers."""
    settings = load_settings(SETTINGS_PATH)
    universe = get_universe()
    assert len(universe) == settings.strategy.universe_size


def test_universe_size_in_roadmap_range() -> None:
    """Roadmap mandates 50-100 large-cap USA liquidi."""
    universe = get_universe()
    assert 50 <= len(universe) <= 100


def test_universe_symbols_are_well_formed() -> None:
    """Ticker symbols must be uppercase letters, optionally with a dot+class."""
    import re
    pattern = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")
    for t in get_universe():
        assert pattern.match(t), f"malformed ticker symbol: {t!r}"


def test_universe_has_no_duplicates() -> None:
    universe = get_universe()
    assert len(universe) == len(set(universe)), "duplicate tickers in universe"


def test_mvp_universe_contains_known_megacaps() -> None:
    """Sanity check: well-known liquid S&P 500 large-caps present."""
    for must_have in ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM"]:
        assert must_have in MVP_UNIVERSE, f"missing megacap {must_have}"


def test_universe_is_deterministic() -> None:
    """Two calls return the same list in the same order."""
    assert get_universe() == get_universe()

"""Curated universe of liquid US large-cap tickers.

Phase 1 needs ~50-100 large-cap USA liquidi. For the MVP we use the CURRENT
S&P 500 top tickers (fixed list). Survivorship bias in the historical
constituents is acknowledged in the roadmap audit and DEFERRED to v2 — for
the MVP the goal is to validate the edge on the dataset we have, not to
reconstruct the historical universe.

If you need a different size, edit this list AND update settings.yaml
(strategy.universe_size). The two MUST agree — test_universe.py enforces it.
"""

from __future__ import annotations

from typing import List

# 80 mega- and large-cap US tickers, ordered for determinism.
# Tech (20)
# Financials (15)
# Healthcare (15)
# Consumer (10)
# Energy (5)
# Industrials (5)
# Materials (3)
# Utilities (3)
# Real Estate (2)
# Telecom (2)
MVP_UNIVERSE: List[str] = [
    # Tech (20)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "ORCL",
    "CRM", "ADBE", "CSCO", "IBM", "INTC", "AMD", "QCOM", "AVGO",
    "TXN", "MU", "NOW", "PANW",
    # Financials (15)
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW",
    "AXP", "USB", "PNC", "TFC", "COF", "SPGI", "ICE",
    # Healthcare (15)
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "DHR",
    "ABT", "BMY", "AMGN", "GILD", "CVS", "CI", "ELV",
    # Consumer (10)
    "WMT", "PG", "KO", "PEP", "MCD", "NKE", "SBUX", "COST",
    "HD", "LOW",
    # Energy (5)
    "XOM", "CVX", "COP", "SLB", "EOG",
    # Industrials (5)
    "BA", "CAT", "HON", "RTX", "DE",
    # Materials (3)
    "LIN", "APD", "FCX",
    # Utilities (3)
    "NEE", "DUK", "SO",
    # Real Estate (2)
    "PLD", "AMT",
    # Telecom (2)
    "VZ", "T",
]


def get_universe() -> List[str]:
    """Return the deterministic MVP universe list.

    A copy is returned to prevent callers from mutating the module-level
    constant. Order is preserved.
    """
    return list(MVP_UNIVERSE)

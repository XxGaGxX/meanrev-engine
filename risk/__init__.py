"""
Risk package — position sizing and risk management.

FASE 3 implements volatility-targeted share sizing and Kelly-fractioned
risk overlays; the position sizing layer produces real dollar P&L so the
equity curve reflects true risk exposure.
"""

from .sizing import (
    apply_position_sizing,
    build_equity_curve,
    build_pct_curve,
    calculate_shares,
    kelly_risk_pct,
)

__all__ = [
    "apply_position_sizing",
    "build_equity_curve",
    "build_pct_curve",
    "calculate_shares",
    "kelly_risk_pct",
]

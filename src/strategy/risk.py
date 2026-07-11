"""Phase 4 - Risk & Position Sizing (base MVP + quant R:R fix).

Single responsibility: turn an entry signal + market context into a
concrete, risk-bounded trade plan (entry, SL, TP, size, time-stop).

Two layers, both required by the roadmap + quant discipline:

  (A) BASE plan (docs/specs §4.3-4.5):
        TP   = prev_close          (the gap-fill target)
        SL   = opening_range low (LONG) / high (SHORT)
        size = risk_amount / stop_distance, ATR-volatility scaled, capped
        risk_amount = capital * risk_per_trade
        stop_distance = max(|entry - SL|, entry * min_stop_distance_pct)

  (B) QUANT FIX -- R:R < 1 by construction otherwise:
        A DOWN-gap breakout LONG enters at the OR-high breakout and sets
        SL below OR-low. The stop is WIDER than the target (prev_close),
        so pure price R:R ~ 0.6. No backtest saves that. We fix it with:
          - partial_tp_frac: take that fraction at the OR boundary
            (OR-high for LONG / OR-low for SHORT) to recover risk early;
            the remainder runs to prev_close. Effective R:R improves.
          - time_stop_bars: if unfilled after N bars, exit (caps the loss
            the poor price R:R implies).

All parameters are arguments wired from config/settings.yaml by the
orchestrator (Phase 5). No hardcoding. Pure, IO-free, no hidden state.

Costs: Alpaca is commission-free; we model the regulatory fees only
(SEC ~$8/$1M notional, FINRA TAF $0.000119/sh capped $5.95/side). These
are used by the backtest (Phase 5) to net P&L; exported here so the cost
model lives in ONE place.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# --- Alpaca regulatory cost constants (no commission) ---
SEC_FEE_RATE = 8e-6          # ~$8 per $1,000,000 of notional sold
FINRA_TAF_PER_SHARE = 0.000119
FINRA_TAF_CAP = 5.95


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class PositionPlan:
    """A fully-specified, risk-bounded trade plan.

    entry_price : fill price (signal bar_index + 1 open, set by caller).
    sl_price    : hard stop.
    tp_price    : full target (prev_close).
    tp_partial_price : partial-TAKE profit level (OR boundary) or None.
    partial_tp_frac   : fraction taken at tp_partial_price (0 = disabled).
    size        : integer share count (>= 0).
    time_stop_bars : max bars in trade before forced exit, or None.
    direction   : LONG / SHORT.
    """

    direction: Direction
    entry_price: float
    sl_price: float
    tp_price: float
    size: int
    tp_partial_price: Optional[float] = None
    partial_tp_frac: float = 0.0
    time_stop_bars: Optional[int] = None

    @property
    def is_valid(self) -> bool:
        # For LONG: SL below entry, entry at/below the OR-high partial TP.
        # The partial TP (OR-high) can sit ABOVE the full TP (prev_close)
        # because it is hit first on the way up. So we only require the
        # directional monotonicity SL < entry <= tp_partial (LONG).
        if self.direction is Direction.LONG:
            return (
                self.sl_price < self.entry_price
                and self.entry_price <= self.tp_partial_price
            )
        return (
            self.tp_partial_price <= self.entry_price
            and self.entry_price < self.sl_price
        )

    def effective_rr(self) -> float:
        """Effective risk/reward accounting for the partial TP.

        Half (partial_tp_frac) of the position exits at tp_partial_price
        to recover risk early; the remainder runs to tp_price. The reward
        is the size-weighted average; the risk is the full stop distance.
        Returns 0.0 if the plan is not valid.
        """
        if not self.is_valid or self.size <= 0:
            return 0.0
        if self.direction is Direction.LONG:
            risk = self.entry_price - self.sl_price
            rew_partial = self.tp_partial_price - self.entry_price
            rew_full = self.tp_price - self.entry_price
        else:
            risk = self.sl_price - self.entry_price
            rew_partial = self.entry_price - self.tp_partial_price
            rew_full = self.entry_price - self.tp_price
        if risk <= 0:
            return 0.0
        frac = self.partial_tp_frac
        eff_reward = frac * rew_partial + (1.0 - frac) * rew_full
        return eff_reward / risk


def _clamp_size(size: float, entry_price: float, max_notional: float) -> int:
    """Cap share count so notional <= max_notional, return int shares."""
    if entry_price <= 0:
        return 0
    max_shares = max_notional / entry_price
    return int(min(size, max_shares))


def alpaca_round_trip_cost(shares: float, price: float) -> float:
    """Regulatory cost of one round trip (entry + exit) at `price`.

    Alpaca charges no commission. We model:
      SEC fee  = notional * SEC_FEE_RATE  (applies to sells; round-trip
                 approximates 2x notional)
      FINRA TAF = shares * FINRA_TAF_PER_SHARE, capped at FINRA_TAF_CAP
                 per side.
    """
    if shares <= 0 or price <= 0:
        return 0.0
    notional = shares * price
    sec = 2.0 * notional * SEC_FEE_RATE
    taf_per_side = min(shares * FINRA_TAF_PER_SHARE, FINRA_TAF_CAP)
    return sec + 2.0 * taf_per_side


def compute_position(
    *,
    direction: str,
    entry_price: float,
    opening_range_high: float,
    opening_range_low: float,
    prev_close: float,
    capital: float,
    risk_per_trade: float,
    atr: float,
    atr_target: float,
    min_stop_distance_pct: float,
    max_position_size: float,
    partial_tp_frac: float = 0.0,
    time_stop_bars: Optional[int] = None,
    sl_atr_multiple: Optional[float] = None,
) -> PositionPlan:
    """Build a risk-bounded PositionPlan.

    Args mirror the design doc §4.3-4.5 plus the quant fixes:
        partial_tp_frac: 0 disables partial TP; (0,1] takes that fraction
            at the OR boundary.
        time_stop_bars: optional max bars in trade before forced exit.
        sl_atr_multiple: if given, the SL is volatility-scaled
            (entry - atr*mult for LONG / entry + atr*mult for SHORT)
            INSTEAD of the (often wide) opening-range boundary. This caps
            loss size so a few adverse gaps cannot produce outsized
            losses that destroy profit factor. Recommended for live use.

    Returns:
        PositionPlan with integer share count.

    Raises:
        ValueError: bad direction, non-positive capital/entry,
            partial_tp_frac outside [0,1], or sl_atr_multiple <= 0.
    """
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"direction must be LONG/SHORT, got {direction!r}")
    if capital <= 0:
        raise ValueError(f"capital must be positive, got {capital!r}")
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price!r}")
    if not (0.0 <= partial_tp_frac <= 1.0):
        raise ValueError(f"partial_tp_frac must be in [0,1], got {partial_tp_frac!r}")
    if time_stop_bars is not None and time_stop_bars <= 0:
        raise ValueError(f"time_stop_bars must be positive, got {time_stop_bars!r}")
    if sl_atr_multiple is not None and sl_atr_multiple <= 0:
        raise ValueError(f"sl_atr_multiple must be positive, got {sl_atr_multiple!r}")

    is_long = direction == "LONG"
    dir_enum = Direction.LONG if is_long else Direction.SHORT

    # --- SL / TP per design doc §4.3 ---
    # Base SL uses the OR boundary. The ATR stop (quant fix) OVERRIDES it
    # when provided, bounding the loss to volatility instead of the wide OR.
    if sl_atr_multiple is not None and atr > 0:
        sl_offset = atr * sl_atr_multiple
        sl_price = entry_price - sl_offset if is_long else entry_price + sl_offset
    else:
        sl_price = opening_range_low if is_long else opening_range_high
    tp_price = prev_close
    # OR boundary used for the partial take-profit. Always populated so the
    # backtest / report can reason about it; whether it is USED is governed
    # by partial_tp_frac (0 = disabled, but the price is still known).
    tp_partial = opening_range_high if is_long else opening_range_low

    # --- Stop distance (defended by min_stop_distance_pct) ---
    raw_stop_dist = abs(entry_price - sl_price)
    min_dist = entry_price * min_stop_distance_pct
    stop_distance = max(raw_stop_dist, min_dist)
    if stop_distance <= 0:
        raise ValueError("stop_distance resolved to <= 0; check SL/entry")

    # --- Risk-based size ---
    risk_amount = capital * risk_per_trade
    size = risk_amount / stop_distance

    # --- ATR volatility scaling (normalize vs target vol) ---
    if atr_target > 0 and atr > 0:
        size = size * (atr_target / atr)

    max_notional = capital * max_position_size
    size = _clamp_size(size, entry_price, max_notional)

    return PositionPlan(
        direction=dir_enum,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_price=tp_price,
        size=size,
        tp_partial_price=tp_partial,
        partial_tp_frac=partial_tp_frac,
        time_stop_bars=time_stop_bars,
    )

"""Tests for Phase 4 Risk & Position Sizing (TDD, RED before GREEN).

Contract (docs/specs/2026-07-09-gap-mean-reversion-design.md §4.3-4.5
+ ROADMAP_MVP.md Phase 4 + quant analysis: R:R must be >1):

  - Entry LONG  = opening-range breakout (signal bar_index+1 open)
  - TP   (base) = prev_close  (the gap fill target)
  - SL   (base) = opening_range low  (LONG) / high (SHORT)
  - Position size = risk_amount / stop_distance, capped.
      risk_amount = capital * risk_per_trade
      stop_distance = max(|entry - SL|, entry * min_stop_distance_pct)
  - Alpaca costs: SEC fee (~$8/$1M notional) + FINRA TAF ($0.000119/sh,
    capped $5.95). Applied on entry and exit notional.

  QUANT FIX (R:R < 1 by construction otherwise):
  - time_stop_bars: if price hasn't filled by N bars after entry, the
    position is closed (caps the loss poor price-based R:R implies).
  - partial_tp_frac in (0,1]: take that fraction of the position at the
    OR-high (LONG) / OR-low (SHORT) to recover risk early; remainder
    runs to prev_close. With partial_tp_frac=0.5 the EFFECTIVE R:R
    improves because half the risk is recovered at the OR boundary.

  All params come from the caller (settings.yaml) -- no hardcoding.
  Pure functions, no IO, no hidden state.
"""

from __future__ import annotations

import pytest

from src.strategy.risk import (
    FINRA_TAF_CAP,
    FINRA_TAF_PER_SHARE,
    SEC_FEE_RATE,
    PositionPlan,
    Direction,
    compute_position,
    alpaca_round_trip_cost,
)


# --------------------------------------------------------------------------
# Basic plan shape
# --------------------------------------------------------------------------


def test_compute_long_plan_sl_tp_and_direction() -> None:
    # Case: SMALL gap (entry near prev_close) but a WIDE opening range ->
    # stop wider than target. entry 99.85, OR-low 99.2, prev_close 100.0
    plan = compute_position(
        direction="LONG",
        entry_price=99.85,
        opening_range_high=100.1,
        opening_range_low=99.2,
        prev_close=100.0,
        capital=25_000.0,
        risk_per_trade=0.01,
        atr=0.5,
        atr_target=0.5,
        min_stop_distance_pct=0.001,
        max_position_size=0.95,
    )
    assert plan.direction is Direction.LONG
    assert plan.entry_price == pytest.approx(99.85)
    assert plan.sl_price == pytest.approx(99.2)          # OR-low
    assert plan.tp_price == pytest.approx(100.0)         # prev_close
    assert plan.tp_partial_price == pytest.approx(100.1)  # OR-high (partial)
    # risk amount = 250; raw stop distance = 99.85-99.2 = 0.65 -> 384 shares
    # but notional cap = 0.95*25000 = 23750; 23750/99.85 = 237.8 -> 237 shares
    raw_size = 250.0 / 0.65
    assert raw_size == pytest.approx(384.6, abs=1.0)
    assert plan.size == 237  # capped by max_position_size


def test_compute_short_plan_mirrors() -> None:
    plan = compute_position(
        direction="SHORT",
        entry_price=100.7,
        opening_range_high=101.1,
        opening_range_low=100.8,
        prev_close=100.0,
        capital=25_000.0,
        risk_per_trade=0.01,
        atr=0.5,
        atr_target=0.5,
        min_stop_distance_pct=0.001,
        max_position_size=0.95,
    )
    assert plan.direction is Direction.SHORT
    assert plan.sl_price == pytest.approx(101.1)   # OR-high
    assert plan.tp_price == pytest.approx(100.0)   # prev_close
    assert plan.tp_partial_price == pytest.approx(100.8)  # OR-low


# --------------------------------------------------------------------------
# R:R fix — partial TP must beat pure price-based R:R
# --------------------------------------------------------------------------


def _rr(p: PositionPlan) -> float:
    """Effective R:R with partial TP: half size exits at tp_partial
    (risk recovered), half runs to tp. Reward weighted by size."""
    if p.direction is Direction.LONG:
        risk = p.entry_price - p.sl_price
        rew_partial = p.tp_partial_price - p.entry_price
        rew_full = p.tp_price - p.entry_price
    else:
        risk = p.sl_price - p.entry_price
        rew_partial = p.entry_price - p.tp_partial_price
        rew_full = p.entry_price - p.tp_price
    frac = p.partial_tp_frac
    eff_reward = frac * rew_partial + (1 - frac) * rew_full
    return eff_reward / risk


def test_partial_tp_improves_rr_over_pure() -> None:
    """Pure price R:R for a SMALL-gap DOWN breakout with a WIDE OR is < 1
    (stop OR-low is wider than target prev_close). With 50% partial TP at
    the OR-high the EFFECTIVE R:R must exceed the pure R:R. This is the
    quant fix captured in Fase 4."""
    base = dict(
        entry_price=99.85, opening_range_high=100.1, opening_range_low=99.2,
        prev_close=100.0, capital=25_000.0, risk_per_trade=0.01, atr=0.5,
        atr_target=0.5, min_stop_distance_pct=0.001, max_position_size=0.95,
    )
    pure = compute_position(direction="LONG", partial_tp_frac=0.0, **base)
    fixed = compute_position(direction="LONG", partial_tp_frac=0.5, **base)
    pure_rr = _rr(pure)
    fixed_rr = _rr(fixed)
    assert pure_rr < 1.0, f"expected pure R:R < 1, got {pure_rr}"
    assert fixed_rr > pure_rr, f"partial TP should improve R:R: {pure_rr} -> {fixed_rr}"


def test_time_stop_present_when_enabled() -> None:
    plan = compute_position(
        direction="LONG", entry_price=99.3, opening_range_high=99.1,
        opening_range_low=98.7, prev_close=100.0, capital=25_000.0,
        risk_per_trade=0.01, atr=0.5, atr_target=0.5,
        min_stop_distance_pct=0.001, max_position_size=0.95,
        time_stop_bars=30,
    )
    assert plan.time_stop_bars == 30


# --------------------------------------------------------------------------
# ATR volatility scaling
# --------------------------------------------------------------------------


def test_atr_scaling_scales_size() -> None:
    base = dict(
        direction="LONG", entry_price=99.3, opening_range_high=99.1,
        opening_range_low=98.7, prev_close=100.0, capital=25_000.0,
        risk_per_trade=0.01, min_stop_distance_pct=0.001,
        max_position_size=0.95,
    )
    calm = compute_position(atr=0.3, atr_target=0.6, **base)   # vol below target
    wild = compute_position(atr=1.2, atr_target=0.6, **base)   # vol above target
    # Higher ticker vol -> smaller size (scaling factor < 1).
    assert wild.size < calm.size


# --------------------------------------------------------------------------
# Alpaca cost model
# --------------------------------------------------------------------------


def test_alpaca_round_trip_cost_positive_and_capped() -> None:
    # 100 shares at $100 -> $10,000 notional each side.
    c = alpaca_round_trip_cost(100, 100.0)
    # SEC: 2 * 10000 * 8e-6 = 0.16 ; TAF: 2 * min(100*0.000119, 5.95)=0.0238
    assert c == pytest.approx(0.16 + 0.0238, abs=1e-4)
    assert c > 0


def test_alpaca_taf_capped_per_side() -> None:
    # Huge share count -> TAF hits the $5.95 cap per side.
    c = alpaca_round_trip_cost(100_000, 100.0)
    # TAF capped: 2 * 5.95 = 11.9 ; SEC = 2*1e7*8e-6 = 160
    assert c == pytest.approx(160 + 11.9, abs=1e-2)


# --------------------------------------------------------------------------
# No hardcoding — params drive behaviour
# --------------------------------------------------------------------------


def test_smaller_risk_per_trade_smaller_size() -> None:
    base = dict(
        direction="LONG", entry_price=99.3, opening_range_high=99.1,
        opening_range_low=98.7, prev_close=100.0, capital=25_000.0,
        atr=0.5, atr_target=0.5, min_stop_distance_pct=0.001,
        max_position_size=0.95,
    )
    big = compute_position(risk_per_trade=0.02, **base)
    small = compute_position(risk_per_trade=0.005, **base)
    assert big.size > small.size


def test_effective_rr_method_matches_helper() -> None:
    """The module's effective_rr() must agree with the test helper _rr()
    and must reflect the partial-TP improvement over pure R:R."""
    base = dict(
        direction="LONG", entry_price=99.85, opening_range_high=100.1,
        opening_range_low=99.2, prev_close=100.0, capital=25_000.0,
        risk_per_trade=0.01, atr=0.5, atr_target=0.5,
        min_stop_distance_pct=0.001, max_position_size=0.95,
    )
    pure = compute_position(partial_tp_frac=0.0, **base)
    fixed = compute_position(partial_tp_frac=0.5, **base)
    assert pure.effective_rr() < 1.0
    assert fixed.effective_rr() > pure.effective_rr()
    # module method == independent helper
    assert fixed.effective_rr() == pytest.approx(_rr(fixed), abs=1e-9)


def test_is_valid_enforces_price_order() -> None:
    ok = compute_position(
        direction="LONG", entry_price=99.85, opening_range_high=100.1,
        opening_range_low=99.2, prev_close=100.0, capital=25_000.0,
        risk_per_trade=0.01, atr=0.5, atr_target=0.5,
        min_stop_distance_pct=0.001, max_position_size=0.95,
    )
    assert ok.is_valid is True


def test_invalid_direction_raises() -> None:
    with pytest.raises(ValueError):
        compute_position(
            direction="SIDEWAYS", entry_price=99.3, opening_range_high=99.1,
            opening_range_low=98.7, prev_close=100.0, capital=25_000.0,
            risk_per_trade=0.01, atr=0.5, atr_target=0.5,
            min_stop_distance_pct=0.001, max_position_size=0.95,
        )


def test_negative_capital_raises() -> None:
    with pytest.raises(ValueError):
        compute_position(
            direction="LONG", entry_price=99.3, opening_range_high=99.1,
            opening_range_low=98.7, prev_close=100.0, capital=-1.0,
            risk_per_trade=0.01, atr=0.5, atr_target=0.5,
            min_stop_distance_pct=0.001, max_position_size=0.95,
        )

"""
Visual + numeric smoke test for FASE 3 — Position Sizing
=========================================================

Runs a deterministic synthetic trade log with one catastrophic tail
loss, then asserts that the risk-sized curve is strictly safer than the
equal-weight naive curve.

This script is self-contained: it does NOT touch the network, Alpaca,
or the indicator/fetch machinery. It only depends on matplotlib,
pandas, numpy, and `risk.sizing`. Run it standalone as a regression
check on FASE 3.

What the test actually demonstrates
-----------------------------------
The Sized curve disagrees with the naive curve **because of two compounding
behaviors**, not because Sized limits per-trade loss to 1%:

1. **Re-sizing after losses**: Sized recomputes the position as 1% of
   pre-trade equity on every entry; after a wipe the per-trade
   notional shrinks alongside the account, so each subsequent trade
   contributes a smaller (and smaller-attached) dollar P&L.

2. **No-leverage cap**: each Sized trade is bounded by
   ``max_position_pct × equity / price`` so the notional never reaches
   the full equity. Naive implicitly treats every trade as a 100%
   equity position, so a -30% gap blow-up natively destroys 30% of
   the war chest.

Both effects together mean that after the same tail loss, Sized and
Naive end the sequence with very different equity levels and max
drawdowns.

Sequence used here:
    [+5%, +5%, -30%, +5%, +5%]
With sized notional ≈ $6,667/trade — specifically
``shares = 10_000 × 0.01 / (1.0 × 1.5) ≈ 66.67`` and
``position_value = 66.67 × $100 = $6,667``. Naive implicitly bets
the full $10,000 equity on every trade. The -30% synthetic event
bypasses any firm stop-loss, so Sized and Naive both register the
same -30% on the offending trade — but Sized arrives there with the
smaller notional.

Usage:
    python scripts/visual_check_sizing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=False)  # safest headless backend; no-op if already set
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Allow running this script directly from the repo root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from risk.sizing import (
    apply_position_sizing,
    build_equity_curve,
    build_pct_curve,
)
from utils.metrics import max_drawdown


# ─────────────────────────────────────────────────────────────────────
# 1. Deterministic synthetic fixture
# ─────────────────────────────────────────────────────────────────────

def _fixture(n_bars: int = 200) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a minimal df (ATR only) and a 5-trade log [+5,+5,-30,+5,+5]."""
    idx = pd.date_range("2024-09-01 09:30", periods=n_bars, freq="15min")
    df = pd.DataFrame(index=idx)
    df["atr"] = 1.0
    df["close"] = 100.0

    # Sequence: win, win, TAIL LOSS, win, win. The middle loss is large
    # enough to bypass any realistic stop loss on intraday data.
    slots = [10, 40, 80, 110, 150]
    exit_offsets = [3, 3, 15, 3, 3]  # the tail loss lingers ~1 session
    pnl_pcts = [+0.05, +0.05, -0.30, +0.05, +0.05]

    n_trades = len(pnl_pcts)
    return df, pd.DataFrame({
        "entry_idx":  slots,
        "exit_idx":   [slots[i] + exit_offsets[i] for i in range(n_trades)],
        "entry_price": [100.0] * n_trades,
        "exit_price":  [100.0 * (1.0 + p) for p in pnl_pcts],
        "direction":   [1] * n_trades,
        "pnl_pct":     pnl_pcts,
        "bars_held":   exit_offsets,
        "exit_reason": ["tp", "tp", "sl", "tp", "tp"],
    })


# ─────────────────────────────────────────────────────────────────────
# 2. Build both curves and assert divergence
# ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 60)
    print("  VISUAL CHECK — FASE 3 risk-based sizing")
    print("=" * 60)

    df, trades_raw = _fixture()
    print(f"  Trade log: {len(trades_raw)} trades")
    print(f"  P&L pcts:  {[f'{p:+.2%}' for p in trades_raw['pnl_pct']]}")

    sized = apply_position_sizing(
        trades_raw, df, initial_equity=10_000.0,
        risk_cfg={
            "risk_per_trade_pct": 1.0,
            "max_risk_per_trade_pct": 2.0,
            "atr_multiplier": 1.5,
            "allow_fractional": True,
            "max_position_pct": 1.0,
            "kelly_fraction": 0.0,
            "commission_per_side": 0.0,
            "slippage_pct": 0.0,
        },
    )

    # Both curves delegate to the production helpers so the regression
    # actually exercises risk.sizing.build_equity_curve and build_pct_curve.
    sized_series = build_equity_curve(sized, df, initial_equity=10_000.0)
    naive_series = build_pct_curve(sized, df, initial_equity=10_000.0)

    sized_final = float(sized_series.iloc[-1])
    naive_final = float(naive_series.iloc[-1])
    sized_dd = float(max_drawdown(sized_series))
    naive_dd = float(max_drawdown(naive_series))

    print("\n  ── Curve headlines ──")
    print(f"  Sized final:   ${sized_final:>10,.2f}   "
          f"max DD: {sized_dd * 100:+.2f}%")
    print(f"  Naive final:   ${naive_final:>10,.2f}   "
          f"max DD: {naive_dd * 100:+.2f}%")
    print(f"  Equity delta:  ${sized_final - naive_final:+,.2f}  "
          f"(positive = Sized outperformed)")
    print(f"  DD     delta:  {(sized_dd - naive_dd) * 100:+.2f}pp  "
          f"(positive = Sized less catastrophic)")

    # ── Assertions with relative floors so the test doesn't pass by
    # ── accident if the fixture is later tweaked toward zero divergence.
    # SIGN CONVENTION (don't flip these!):
    #   - sized_dd and naive_dd are max drawdowns returned by
    #     utils.metrics.max_drawdown — always NEGATIVE or zero.
    #   - sized_dd_advantage_pp = (sized_dd - naive_dd) * 100
    #     ⇒ POSITIVE when Sized's drawdown is shallower (less negative)
    #     than Naive's, i.e. when Sized dominated on the tail event. A
    #     future regression that makes Sized worse on tail loss will flip
    #     this sign.
    eq_gap_pct = (sized_final - naive_final) / 10_000.0
    sized_dd_advantage_pp = (sized_dd - naive_dd) * 100.0  # positive = Sized less severe
    assert sized_final > naive_final and eq_gap_pct > 0.03, (
        f"FASE 3 regression: sized final ${sized_final:,.2f} must beat naive "
        f"${naive_final:,.2f} on [+5,+5,-30,+5,+5] by at least 3% of initial "
        f"equity; gap was {eq_gap_pct * 100:.2f}%."
    )
    assert sized_dd > naive_dd and sized_dd_advantage_pp > 5.0, (
        f"FASE 3 regression: sized max DD {sized_dd * 100:.2f}% must be at "
        f"least 5pp shallower than naive max DD {naive_dd * 100:.2f}%; the "
        f"gap was {sized_dd_advantage_pp:.2f}pp."
    )

    # ── Plot ──
    out_dir = PROJECT_ROOT / "scripts" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "visual_check_sizing.png"

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axhline(10_000.0, color="grey", lw=0.6, ls=":", alpha=0.6,
                label=f"initial (${10_000:,.0f})")
    ax.plot(sized_series.index, sized_series.values, color="navy", lw=1.6,
             label=f"Sized (vol-targeted)  final ${sized_final:,.0f}  "
                   f"maxDD {sized_dd * 100:.1f}%")
    ax.plot(naive_series.index, naive_series.values, color="darkorange",
             lw=1.1, ls="--",
             label=f"Equal-weight naive  final ${naive_final:,.0f}  "
                   f"maxDD {naive_dd * 100:.1f}%")
    ax.set_title("FASE 3 visual check — Sized vs Naive on a deterministic "
                  "tail-loss fixture", fontsize=12, fontweight="bold")
    ax.set_ylabel("Equity ($)")
    ax.set_xlabel("Date (synthetic)")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(alpha=0.3)

    # Stat inset on the upper-RIGHT so it doesn't collide with the Sized
    # curve's peak, which is in the upper-left on this fixture.
    ax.text(
        0.98, 0.97,
        f"\u0394 max DD: {sized_dd_advantage_pp:+.2f}pp   "
        f"(Sized {sized_dd * 100:.2f}% vs Naive {naive_dd * 100:.2f}%)\n"
        f"Sized final: ${sized_final:,.0f}\n"
        f"Naive final: ${naive_final:,.0f}   "
        f"(\u0394 ${sized_final - naive_final:+,.0f})",
        transform=ax.transAxes, fontsize=9, va="top", ha="right",
        family="monospace", zorder=10,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                  edgecolor="grey", alpha=0.92),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)

    print(f"\n  → plot saved: {out_path}  "
          f"({out_path.stat().st_size:,} bytes)")
    print("\n  ✓ Sized curve dominates naive on tail-loss fixture. FASE 3 OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

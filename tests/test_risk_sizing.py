"""
Tests for risk/sizing.py — risk-based position sizing (FASE 3)
"""

import numpy as np
import pandas as pd
import pytest

from risk.sizing import (
    apply_position_sizing,
    build_equity_curve,
    build_pct_curve,
    calculate_shares,
    kelly_risk_pct,
)
from signals.exit import TRADE_LOG_COLUMNS


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_sized_df(n: int = 200, atr: float = 1.0, price: float = 100.0) -> pd.DataFrame:
    """Build a minimal df that satisfies sizing's needs: just an ATR column."""
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    df = pd.DataFrame(index=idx)
    df["atr"] = atr
    return df


def _make_synthetic_trade_log(
    n: int = 5,
    entry_idxs=None,
    exit_idxs=None,
    entry_prices=None,
    exit_prices=None,
    directions=None,
    pnl_pcts=None,
) -> pd.DataFrame:
    """Build a minimal trade log DataFrame."""
    entry_idxs = entry_idxs or list(range(0, n * 10, 10))
    exit_idxs = exit_idxs or [e + 5 for e in entry_idxs]
    entry_prices = entry_prices or [100.0] * n
    exit_prices = exit_prices or [101.0] * n    # +1% gain
    directions = directions or [1] * n
    pnl_pcts = pnl_pcts or [
        d * (x - p) / p for d, p, x in zip(directions, entry_prices, exit_prices)
    ]
    return pd.DataFrame({
        "entry_idx": entry_idxs,
        "exit_idx": exit_idxs,
        "entry_price": entry_prices,
        "exit_price": exit_prices,
        "direction": directions,
        "pnl_pct": pnl_pcts,
        "bars_held": [e2 - e1 for e1, e2 in zip(entry_idxs, exit_idxs)],
        "exit_reason": ["tp"] * n,
    })


# ─────────────────────────────────────────────────────────────────────
# calculate_shares — formula correctness
# ─────────────────────────────────────────────────────────────────────

class TestCalculateShares:
    def test_basic_formula(self):
        # equity=10_000, risk=1% → risk_dollar=100.
        # stop_distance = atr × mult = 1.0 × 1.5 = 1.5
        # shares = 100 / 1.5 = 66.6667
        shares = calculate_shares(
            equity=10_000, risk_pct=1.0, atr=1.0, multiplier=1.5,
            price=100.0, allow_fractional=True,
        )
        assert shares == pytest.approx(66.6667, rel=1e-3)

    def test_fractional_default(self):
        shares = calculate_shares(10_000, 1.0, 1.0, 1.5, 100.0)
        # Rounded to 4 decimals → 66.6667
        assert shares == pytest.approx(66.6667, abs=1e-4)

    def test_whole_shares_floor(self):
        shares = calculate_shares(
            equity=10_000, risk_pct=1.0, atr=1.0, multiplier=1.5,
            price=100.0, allow_fractional=False,
        )
        # floor(66.6667) = 66
        assert shares == 66

    def test_no_leverage_cap(self):
        # position_value = shares × price held under equity
        shares = calculate_shares(
            equity=10_000, risk_pct=99.0, atr=1.0, multiplier=1.5,
            price=100.0, allow_fractional=True, max_position_pct=1.0,
        )
        # Would imply 6_600 shares ($660k notional). Cap kicks in at $10k equity.
        # 10_000 / 100 = 100 shares
        assert shares == pytest.approx(100.0, abs=1e-4)

    def test_invalid_inputs_return_zero(self):
        assert calculate_shares(-1, 1.0, 1.0, 1.5, 100.0) == 0.0
        assert calculate_shares(10_000, 0.0, 1.0, 1.5, 100.0) == 0.0
        assert calculate_shares(10_000, 1.0, 0.0, 1.5, 100.0) == 0.0
        assert calculate_shares(10_000, 1.0, 1.0, 0.0, 100.0) == 0.0
        assert calculate_shares(10_000, 1.0, 1.0, 1.5, 0.0) == 0.0
        assert calculate_shares(np.nan, 1.0, 1.0, 1.5, 100.0) == 0.0
        assert calculate_shares(10_000, 1.0, np.inf, 1.5, 100.0) == 0.0

    def test_higher_atr_means_smaller_size(self):
        s_low = calculate_shares(10_000, 1.0, atr=0.5, multiplier=1.5, price=100.0)
        s_high = calculate_shares(10_000, 1.0, atr=2.0, multiplier=1.5, price=100.0)
        assert s_low > s_high

    def test_higher_risk_means_larger_size(self):
        s_lo = calculate_shares(10_000, 0.5, 1.0, 1.5, 100.0)
        s_hi = calculate_shares(10_000, 2.0, 1.0, 1.5, 100.0)
        assert s_hi > s_lo


# ─────────────────────────────────────────────────────────────────────
# kelly_risk_pct
# ─────────────────────────────────────────────────────────────────────

class TestKellyRiskPct:
    def test_returns_zero_on_empty(self):
        assert kelly_risk_pct(pd.Series(dtype=float)) == 0.0

    def test_returns_zero_with_only_wins(self):
        s = pd.Series([0.01, 0.02, 0.03])
        assert kelly_risk_pct(s, fraction=0.25, risk_cap_pct=2.0) == 0.0

    def test_caps_at_risk_cap(self):
        # Hypothetical huge-kelly scenario: high win rate, big wins
        s = pd.Series([0.05] * 9 + [-0.01] * 1)
        cap = 2.0
        out = kelly_risk_pct(s, fraction=0.25, risk_cap_pct=cap)
        assert out <= cap

    def test_positive_for_positive_expectancy(self):
        s = pd.Series([0.02] * 6 + [-0.01] * 4)
        out = kelly_risk_pct(s, fraction=0.25, risk_cap_pct=2.0)
        assert out > 0
        assert out <= 2.0

    def test_zero_for_negative_expectancy(self):
        s = pd.Series([0.01] * 3 + [-0.03] * 7)
        out = kelly_risk_pct(s, fraction=0.25, risk_cap_pct=2.0)
        assert out == 0.0

    def test_higher_kelly_fraction_yields_higher_or_equal(self):
        s = pd.Series([0.02] * 6 + [-0.01] * 4)
        out_q = kelly_risk_pct(s, fraction=0.25, risk_cap_pct=10.0)
        out_h = kelly_risk_pct(s, fraction=0.5, risk_cap_pct=10.0)
        assert out_h >= out_q


# ─────────────────────────────────────────────────────────────────────
# apply_position_sizing
# ─────────────────────────────────────────────────────────────────────

class TestApplyPositionSizing:
    def test_empty_trades_returns_columns(self):
        empty = pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct", "bars_held", "exit_reason",
        ])
        df = _make_sized_df()
        out = apply_position_sizing(empty, df, initial_equity=10_000.0)
        assert out.empty
        for col in ("shares", "position_value", "risk_dollar",
                    "pnl_dollar", "commission_cost", "equity_after",
                    "kelly_risk_pct", "pnl_pct_slip"):
            assert col in out.columns

    def test_initial_columns_present(self):
        trades = _make_synthetic_trade_log(n=3)
        df = _make_sized_df(n=200)
        out = apply_position_sizing(trades, df, initial_equity=10_000.0)
        assert set(out.columns) >= {
            "shares", "position_value", "risk_dollar",
            "pnl_dollar", "commission_cost", "equity_after",
            "kelly_risk_pct",
        }

    def test_risk_dollar_matches_initial_risk_pct(self):
        trades = _make_synthetic_trade_log(n=2)
        df = _make_sized_df(n=200)
        out = apply_position_sizing(
            trades, df, initial_equity=10_000.0,
            risk_cfg={"risk_per_trade_pct": 1.0, "kelly_fraction": 0.0},
        )
        # First trade uses initial equity → 1% × 10_000 = 100
        assert out["risk_dollar"].iloc[0] == pytest.approx(100.0, abs=1e-4)

    def test_running_equity_changes_after_each_trade(self):
        # Two winning +1% trades should grow equity slightly
        trades = _make_synthetic_trade_log(
            n=3,
            entry_idxs=[0, 20, 40],
            exit_idxs=[5, 25, 45],
            directions=[1, 1, 1],
            entry_prices=[100.0, 100.0, 100.0],
            exit_prices=[101.0, 101.0, 101.0],
        )
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        out = apply_position_sizing(
            trades, df, initial_equity=10_000.0,
            risk_cfg={"risk_per_trade_pct": 1.0, "kelly_fraction": 0.0},
        )
        eq0 = float(out["equity_after"].iloc[0])
        eq1 = float(out["equity_after"].iloc[1])
        eq2 = float(out["equity_after"].iloc[2])
        assert eq0 > 10_000.0
        # Each subsequent trade sizes on a slightly bigger equity → bigger $ P&L
        assert (eq1 - eq0) > 0
        assert (eq2 - eq1) > 0

    def test_kelly_disabled_by_default(self):
        trades = _make_synthetic_trade_log(n=3)
        df = _make_sized_df(n=200)
        out = apply_position_sizing(trades, df, initial_equity=10_000.0)
        # kelly_risk_pct column is all NaN when Kelly is disabled
        assert out["kelly_risk_pct"].isna().all()

    def test_kelly_enabled_after_min_history(self):
        # 6 winning trades to satisfy min_history=5 plus one more
        n = 7
        trades = _make_synthetic_trade_log(
            n=n,
            entry_idxs=list(range(0, n * 20, 20)),
            exit_idxs=[e + 5 for e in range(0, n * 20, 20)],
            exit_prices=[101.0 + i * 0.1 for i in range(n)],
        )
        df = _make_sized_df(n=500, atr=1.0, price=100.0)
        out = apply_position_sizing(
            trades, df, initial_equity=10_000.0,
            risk_cfg={"kelly_fraction": 0.25, "risk_cap_pct": 2.0},
        )
        # First 5 trades: no Kelly history yet → NaN
        assert out["kelly_risk_pct"].iloc[:5].isna().all()
        # From trade 6 onwards: Kelly computed
        assert out["kelly_risk_pct"].iloc[5:].notna().all()

    def test_full_wipe_floors_equity_at_zero(self):
        # A single catastrophic trade bigger than equity should floor at 0
        trades = _make_synthetic_trade_log(
            n=1, entry_idxs=[0], exit_idxs=[5],
            entry_prices=[100.0], exit_prices=[0.0],    # −100%
            directions=[1], pnl_pcts=[-1.0],
        )
        df = _make_sized_df(n=200, atr=0.0001, price=100.0)  # tiny ATR → big size
        out = apply_position_sizing(trades, df, initial_equity=10_000.0)
        assert out["equity_after"].iloc[0] == 0.0

    def test_halt_after_wipe_drops_tail_trades(self):
        # atr=0.0001 forces shares to 100 (capped by equity at 10000/100), so
        # position_value = $10_000 = full equity. A $0 exit wipes the account.
        trades = _make_synthetic_trade_log(
            n=2,
            entry_idxs=[0, 20],
            exit_idxs=[5, 25],
            entry_prices=[100.0, 100.0],
            exit_prices=[0.0, 102.0],     # first wipes, second is a win
            directions=[1, 1],
            pnl_pcts=[-1.0, 0.02],
        )
        df = _make_sized_df(n=200, atr=0.0001, price=100.0)
        out = apply_position_sizing(trades, df, initial_equity=10_000.0)
        # First trade: equity 0
        assert out["equity_after"].iloc[0] == 0.0
        # Second trade: halted, 0 shares
        assert out["shares"].iloc[1] == 0.0
        assert out["equity_after"].iloc[1] == 0.0

    def test_no_halt_after_wipe_trades_continue(self):
        # Same wipe setup, but halt_after_wipe=False leaves the internal
        # `wiped` flag unset. The second trade still sizes, but
        # calculate_shares() guards equity<=0 and returns 0 — so the relevant
        # invariants are: (a) no share on trade 2, (b) pnl_dollar stays 0,
        # (c) no crash, (d) pnl_pct_slip is preserved as the raw entry/exit
        # delta because no slippage adjustment is applied to zero-sized rows.
        trades = _make_synthetic_trade_log(
            n=2,
            entry_idxs=[0, 20],
            exit_idxs=[5, 25],
            entry_prices=[100.0, 100.0],
            exit_prices=[0.0, 102.0],
            directions=[1, 1],
            pnl_pcts=[-1.0, 0.02],
        )
        df = _make_sized_df(n=200, atr=0.0001, price=100.0)
        out = apply_position_sizing(
            trades, df, initial_equity=10_000.0,
            risk_cfg={"halt_after_wipe": False},
        )
        assert out["shares"].iloc[1] == 0.0
        assert out["pnl_dollar"].iloc[1] == 0.0
        assert out["equity_after"].iloc[1] == 0.0
        assert out["pnl_pct_slip"].iloc[1] == pytest.approx(0.02, abs=1e-9)

    def test_partial_drawdown_continues_sizing(self):
        # Sanity check that halt_after_wipe doesn't stop ordinary drawdowns.
        # atr=1.0 → 66.67 shares × $100 = $6_666.67 notional; a −50% drawdown
        # leaves 6_666 equity, well above zero, so trading continues.
        trades = _make_synthetic_trade_log(
            n=2,
            entry_idxs=[0, 20],
            exit_idxs=[5, 25],
            entry_prices=[100.0, 100.0],
            exit_prices=[50.0, 101.0],    # 50% drawdown then +1% win
            directions=[1, 1],
            pnl_pcts=[-0.5, 0.01],
        )
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        out = apply_position_sizing(trades, df, initial_equity=10_000.0)
        # Surviving equity after first trade: 10_000 + 66.67 × (50 − 100) ≈ 6_666.67
        assert out["equity_after"].iloc[0] == pytest.approx(6_666.67, rel=1e-3)
        # Second trade sizes on >0 equity → non-zero shares
        assert out["shares"].iloc[1] > 0
        assert out["equity_after"].iloc[1] > out["equity_after"].iloc[0]  # +1% on survivor

    def test_commission_subtracted_from_dollar_pnl(self):
        trades = _make_synthetic_trade_log(
            n=1, entry_idxs=[0], exit_idxs=[5],
            exit_prices=[101.0],    # +1%
        )
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        out_no_comm = apply_position_sizing(
            trades.copy(), df, initial_equity=10_000.0,
            risk_cfg={"commission_per_side": 0.0},
        )
        out_with_comm = apply_position_sizing(
            trades.copy(), df, initial_equity=10_000.0,
            risk_cfg={"commission_per_side": 0.001},
        )
        # With commission, pnl_dollar must be strictly smaller
        assert out_with_comm["pnl_dollar"].iloc[0] < out_no_comm["pnl_dollar"].iloc[0]

    def test_slippage_adverse_effect_on_pnl_pct(self):
        trades = _make_synthetic_trade_log(
            n=1, entry_idxs=[0], exit_idxs=[5],
            entry_prices=[100.0], exit_prices=[101.0],
            directions=[1], pnl_pcts=[0.01],
        )
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        out = apply_position_sizing(
            trades, df, initial_equity=10_000.0,
            risk_cfg={"slippage_pct": 0.001, "commission_per_side": 0.0},
        )
        # Slippage on entry long → entry is 100.10; exit is 100.99.
        # pnl_pct_slip = (100.99 - 100.10) / 100.10 ≈ 0.00890 < 0.01
        assert "pnl_pct_slip" in out.columns
        assert out["pnl_pct_slip"].iloc[0] < 0.01
        # Original exit-derived pnl_pct must NOT have been overwritten
        assert out["pnl_pct"].iloc[0] == pytest.approx(0.01, abs=1e-9)

    def test_whole_share_mode_yields_integer_shares(self):
        trades = _make_synthetic_trade_log(n=3)
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        out = apply_position_sizing(
            trades, df, initial_equity=10_000.0,
            risk_cfg={"allow_fractional": False},
        )
        # Shares must be whole numbers in whole-share mode
        for s in out["shares"]:
            assert s == int(s)

    def test_short_trade_sign_convention(self):
        trades = _make_synthetic_trade_log(
            n=1, entry_idxs=[0], exit_idxs=[5],
            entry_prices=[100.0], exit_prices=[99.0],    # −1%
            directions=[-1], pnl_pcts=[0.01],
        )
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        out = apply_position_sizing(trades, df, initial_equity=10_000.0)
        # Short winning trade → pnl_dollar > 0
        assert out["pnl_dollar"].iloc[0] > 0


# ─────────────────────────────────────────────────────────────────────
# build_equity_curve
# ─────────────────────────────────────────────────────────────────────

class TestBuildEquityCurve:
    def test_no_trades_returns_initial_only(self):
        df = _make_sized_df(n=100)
        empty = pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct",
        ])
        ec = build_equity_curve(empty, df, initial_equity=10_000.0)
        assert len(ec) == 1
        assert ec.iloc[0] == 10_000.0

    def test_uses_trade_exit_timestamps(self):
        n = 3
        entry_idxs = [0, 20, 40]
        exit_idxs = [5, 25, 45]
        trades = _make_synthetic_trade_log(
            n=n, entry_idxs=entry_idxs, exit_idxs=exit_idxs,
        )
        df = _make_sized_df(n=200)
        ec = build_equity_curve(trades, df, initial_equity=10_000.0)
        # Expect 1 (initial) + n exits
        assert len(ec) == n + 1
        # Initial timestamp = df.index[0]
        assert ec.index[0] == df.index[0]
        # Each subsequent timestamp = df.index[exit_idx]
        for i, exit_idx in enumerate(exit_idxs):
            assert ec.index[i + 1] == df.index[exit_idx]

    def test_final_value_matches_last_equity_after(self):
        trades = _make_synthetic_trade_log(n=3)
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        sized = apply_position_sizing(trades, df, initial_equity=10_000.0)
        ec = build_equity_curve(sized, df, initial_equity=10_000.0)
        assert ec.iloc[-1] == pytest.approx(sized["equity_after"].iloc[-1], rel=1e-9)

    def test_empty_df_returns_one_element_nat_anchored_series(self):
        # Regression test pinning the empty-df guard. Before the fix
        # this crashed with ``IndexError: index 0 is out of bounds`` on
        # ``df.index[0]`` because the body unconditionally indexed before
        # the empty-trades guard. The chosen contract: 1-element Series
        # at ``pd.NaT`` containing ``initial_equity`` so downstream
        # metrics stay honest (``max_drawdown`` returns 0.0 rather than
        # NaN as it would on a truly empty Series) and callers can
        # continue to call ``.iloc[-1]`` for the initial-bar value.
        df_empty = pd.DataFrame(columns=["atr"])
        trades_empty = pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct",
        ])
        ec = build_equity_curve(
            trades_empty, df_empty, initial_equity=15_000.0,
        )
        assert len(ec) == 1
        assert float(ec.iloc[0]) == 15_000.0
        assert pd.isna(ec.index[0])
        assert isinstance(ec.index, pd.DatetimeIndex)
        assert ec.name == "equity"


# ─────────────────────────────────────────────────────────────────────
# build_pct_curve — legacy equal-weight naive comparison helper
# ─────────────────────────────────────────────────────────────────────

class TestBuildPctCurve:
    def test_empty_trades_returns_initial_only(self):
        df = _make_sized_df(n=100)
        empty = pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct",
        ])
        ec = build_pct_curve(empty, df, initial_equity=10_000.0)
        assert len(ec) == 1
        assert float(ec.iloc[0]) == 10_000.0

    def test_default_initial_equity_is_ten_thousand(self):
        trades = _make_synthetic_trade_log(n=1)
        df = _make_sized_df(n=200)
        ec = build_pct_curve(trades, df)
        assert ec.iloc[0] == pytest.approx(10_000.0, abs=1e-9)

    def test_initial_equity_override(self):
        trades = _make_synthetic_trade_log(n=1)
        df = _make_sized_df(n=200)
        ec = build_pct_curve(trades, df, initial_equity=25_000.0)
        assert ec.iloc[0] == pytest.approx(25_000.0, abs=1e-9)

    def test_compounds_pnl_pct_multiplicatively(self):
        # Independent of size — naive treats every trade as 100% equity.
        # Two wins of +5% then −5% on $10k must yield exactly:
        #   10_000 * 1.05 * 1.05 * 0.95 = 0.9975 * 10_000 = 9_975.0
        trades = _make_synthetic_trade_log(
            n=3,
            entry_idxs=[0, 20, 40],
            exit_idxs=[5, 25, 45],
            exit_prices=[105.0, 105.0, 95.00],   # +5%, +5%, −5%
            entry_prices=[100.0, 100.0, 100.0],
        )
        df = _make_sized_df(n=100, atr=0.5, price=100.0)
        # No apply_position_sizing call needed — pct_curve reads pnl_pct
        # column directly and ignores size-related columns.
        ec = build_pct_curve(trades, df, initial_equity=10_000.0)
        assert ec.iloc[-1] == pytest.approx(10_000.0 * 1.05 * 1.05 * 0.95, abs=1e-9)

    def test_first_timestamp_is_df_index_zero(self):
        # Even if the first trade is at idx=40 the curve must start at
        # df.index[0] so the two curves (sized vs naive) plot on the
        # same x-axis baseline.
        trades = _make_synthetic_trade_log(
            n=1, entry_idxs=[40], exit_idxs=[45],
        )
        df = _make_sized_df(n=200)
        ec = build_pct_curve(trades, df, initial_equity=10_000.0)
        assert ec.index[0] == df.index[0]
        # Second point should be df.index[45]
        assert ec.index[1] == df.index[45]

    def test_ignores_equity_after_when_present(self):
        # Contract — DO NOT "fix": build_pct_curve must ALWAYS compound
        # pnl_pct and must NEVER consult equity_after, even when that
        # column is present on the trade log. This makes build_pct_curve
        # a true comparison baseline against build_equity_curve.
        #
        # To enforce that the column is actually ignored (rather than
        # merely coincidentally preferring pnl_pct in this fixture), we
        # drop equity_after from the trade log entirely and assert the
        # resulting curve is bit-for-bit identical.
        trades = _make_synthetic_trade_log(n=3)
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        sized = apply_position_sizing(trades, df, initial_equity=10_000.0)
        assert "equity_after" in sized.columns
        assert sized["equity_after"].notna().all()
        # All rows have +1% pnl_pct → naive compounds to 1.01^3 * 10k
        ec_with = build_pct_curve(sized, df, initial_equity=10_000.0)
        assert ec_with.iloc[-1] == pytest.approx(10_000.0 * 1.01 ** 3, abs=1e-9)
        # Drop equity_after and every other sizing-derived column. The
        # result MUST still be 1.01^3 * 10_000 because build_pct_curve
        # must not depend on these columns. Use the public TRADE_LOG_COLUMNS
        # schema from signals.exit so the keep-set self-updates if the
        # simulate_all_trades output schema evolves.
        keep = set(TRADE_LOG_COLUMNS)
        sized_minimal = sized.drop(
            columns=[c for c in sized.columns if c not in keep]
        )
        ec_without = build_pct_curve(sized_minimal, df, initial_equity=10_000.0)
        # True bit-for-bit equality on the FULL series (raw ==, not
        # pytest.approx). Two calls with identical inputs and a
        # deterministic float loop produce identical bits; any divergence
        # proves build_pct_curve consulted a non-`pnl_pct` column.
        # Final-value divergence is reported in the message for diagnosis,
        # but the requirement is strict per-index equality.
        assert list(ec_with.values) == list(ec_without.values), (
            f"build_pct_curve must produce an identical curve regardless of "
            f"sizing columns; final values diverge: "
            f"{ec_with.iloc[-1]:.6f} (with sizing) vs "
            f"{ec_without.iloc[-1]:.6f} (without)."
        )

    def test_diverges_from_sized_curve_on_tail_loss(self):
        # Regression-invariant: build_pct_curve (naive) must compound more
        # aggressively than build_equity_curve (sized) on a tail loss
        # because Sized limits notional. This is the visual_check contract
        # — encoded here so future refactors can't silently flip it.
        trades = _make_synthetic_trade_log(
            n=3,
            entry_idxs=[0, 20, 40],
            exit_idxs=[5, 25, 45],
            exit_prices=[105.0, 70.0, 105.0],      # +5%, −30%, +5%
            entry_prices=[100.0, 100.0, 100.0],
        )
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        sized_trades = apply_position_sizing(
            trades, df, initial_equity=10_000.0,
            risk_cfg={"risk_per_trade_pct": 1.0, "kelly_fraction": 0.0},
        )
        naive_ec = build_pct_curve(sized_trades, df, initial_equity=10_000.0)
        sized_ec = build_equity_curve(sized_trades, df, initial_equity=10_000.0)
        # Use RELATIVE FLOORS just like the visual_check_sizing.py smoke test:
        # a regression that quietly shrinks the advantage should be caught,
        # not silently passed.
        eq_gap_pct = (
            (float(sized_ec.iloc[-1]) - float(naive_ec.iloc[-1])) / 10_000.0
        )
        assert eq_gap_pct > 0.03, (
            f"Sized should beat Naive by >3% of initial equity on [+5,−30,+5]; "
            f"gap was {eq_gap_pct * 100:.2f}%."
        )

    def test_negative_only_sequence_monotonic_decline(self):
        # All-loss sequence with one FLAT trade in the middle: catches
        # >/>= off-by-one bugs in the multiplicative formula. All trades
        # negative except one which must produce flat-to-flat handoff.
        trades = _make_synthetic_trade_log(
            n=4,
            entry_idxs=[0, 20, 40, 60],
            exit_idxs=[5, 25, 45, 65],
            exit_prices=[97.0, 100.0, 97.0, 97.0],     # −3%, 0%, −3%, −3%
            entry_prices=[100.0, 100.0, 100.0, 100.0],
        )
        df = _make_sized_df(n=200, atr=1.0, price=100.0)
        ec = build_pct_curve(trades, df, initial_equity=10_000.0)
        # Strict decline except at the flat trade (where pnl_pct=0)
        assert ec.iloc[0] > ec.iloc[1]
        # Flat handoff: trade 2 (pnl_pct=0) leaves equity unchanged
        assert ec.iloc[2] == pytest.approx(ec.iloc[1], abs=1e-9)
        # Then strict decline resumes
        assert ec.iloc[2] > ec.iloc[3] > ec.iloc[4]
        # Closed form: 10_000 * 0.97 * 1.0 * 0.97 * 0.97
        assert ec.iloc[-1] == pytest.approx(10_000.0 * 0.97 * 1.0 * 0.97 * 0.97, abs=1e-9)

    def test_none_input_returns_initial_only(self):
        # Both trades is None and trades.empty must short-circuit; the
        # visual_check contract relies on this for empty-pipeline demos.
        df = _make_sized_df(n=100)
        ec = build_pct_curve(None, df, initial_equity=10_000.0)
        # Full type contract on the single-point curve:
        assert isinstance(ec, pd.Series)
        assert len(ec) == 1
        assert ec.index[0] == df.index[0]
        assert isinstance(ec.index, pd.DatetimeIndex)
        assert ec.name == "equity_naive"
        assert float(ec.iloc[0]) == 10_000.0
        # Confirm the empty DataFrame path returns an identical Series.
        empty = pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct",
        ])
        ec2 = build_pct_curve(empty, df, initial_equity=10_000.0)
        assert isinstance(ec2, pd.Series)
        assert len(ec2) == 1
        assert ec2.index[0] == df.index[0]
        assert ec2.name == "equity_naive"
        assert float(ec2.iloc[0]) == 10_000.0

    def test_empty_df_returns_one_element_nat_anchored_series(self):
        # Mirror defense-in-depth contract to ``build_equity_curve``:
        # a fully-empty ``df`` produces a 1-element Series anchored at
        # ``pd.NaT`` so Sized vs Naive overlays still plot on the same
        # x-axis baseline in ``visual_check_sizing`` when the engine
        # fully emits rows out (e.g., all-zero-volume input) — the
        # caller-facing contract becomes uniform across both helpers.
        df_empty = pd.DataFrame(columns=["atr"])
        ec = build_pct_curve(None, df_empty, initial_equity=12_500.0)
        assert len(ec) == 1
        assert float(ec.iloc[0]) == 12_500.0
        assert pd.isna(ec.index[0])
        assert isinstance(ec.index, pd.DatetimeIndex)
        assert ec.name == "equity_naive"
        # Empty trades also produces the same contract — confirms the
        # two early-return branches (empty df, empty trades) yield
        # internally consistent shapes for the Sized helper.
        trades_empty = pd.DataFrame(columns=[
            "entry_idx", "exit_idx", "entry_price", "exit_price",
            "direction", "pnl_pct",
        ])
        ec_from_trades = build_pct_curve(
            trades_empty, df_empty, initial_equity=12_500.0,
        )
        # Use pd.isna for the index comparison: ``NaT == NaT`` returns
        # False (pandas treats NaT analogously to NaN), so the
        # equality form would fail even when both timestamps are the
        # intended sentinel.
        assert pd.isna(ec_from_trades.index[0])
        assert pd.isna(ec.index[0])
        assert float(ec_from_trades.iloc[0]) == float(ec.iloc[0])

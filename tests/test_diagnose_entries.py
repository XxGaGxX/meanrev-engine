"""Unit tests for scripts/diagnose_entries.py."""
import io
import json
import sys
from contextlib import redirect_stdout

import numpy as np
import pandas as pd
import pytest

# Import testable functions from the diagnostic script.
# The script does sys.path manipulation on import, so we replicate it.
from pathlib import Path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.diagnose_entries import (
    _entry_date,
    _print_condition_frequency,
    _print_trade_diagnostics,
    _print_win_loss_comparison,
    parse_cfg,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _make_df(n_bars: int = 100) -> pd.DataFrame:
    """Build a minimal post-pipeline DataFrame with all required columns."""
    idx = pd.date_range("2024-01-08 10:00", periods=n_bars, freq="15min")
    df = pd.DataFrame(index=idx)
    df["close"] = np.linspace(98, 102, n_bars)
    df["rsi"] = np.linspace(25, 75, n_bars)
    df["bb_upper"] = df["close"] + 2.0
    df["bb_lower"] = df["close"] - 2.0
    df["zscore"] = np.sin(np.linspace(0, 4 * np.pi, n_bars)) * 2.5
    df["regime_ok"] = True
    df["vol_confirm"] = np.random.default_rng(42).choice(
        [True, False], n_bars, p=[0.7, 0.3]
    )
    df["vol_avg"] = 100.0
    df["volume"] = 150.0
    return df


def _make_trades(n: int = 5) -> pd.DataFrame:
    """Build a minimal trade log."""
    trades = pd.DataFrame({
        "entry_idx": [10, 20, 30, 40, 50][:n],
        "exit_idx": [15, 25, 35, 45, 55][:n],
        "entry_price": [100.0] * n,
        "exit_price": [101.0, 99.0, 102.0, 98.0, 100.5][:n],
        "direction": [1, -1, 1, -1, 1][:n],
        "pnl_pct": [0.01, -0.01, 0.02, -0.02, 0.005][:n],
        "bars_held": [5, 5, 5, 5, 5][:n],
        "exit_reason": ["tp", "sl", "tp", "sl", "time"][:n],
    })
    return trades


# ── parse_cfg ──────────────────────────────────────────────────────

class TestParseCfg:
    def test_none_returns_none(self):
        assert parse_cfg(None) is None

    def test_valid_json_returns_dict(self):
        result = parse_cfg('{"entry_signal": {"z_threshold": 1.5}}')
        assert result == {"entry_signal": {"z_threshold": 1.5}}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_cfg("not json")

    def test_empty_object(self):
        assert parse_cfg("{}") == {}

    def test_preserves_types(self):
        result = parse_cfg('{"a": 1, "b": true, "c": "str"}')
        assert result == {"a": 1, "b": True, "c": "str"}


# ── _entry_date ────────────────────────────────────────────────────

class TestEntryDate:
    def test_returns_date_string(self):
        df = _make_df(10)
        assert _entry_date(df, 0) == "2024-01-08"
        assert _entry_date(df, 5) == "2024-01-08"

    def test_out_of_bounds_negative(self):
        df = _make_df(10)
        assert _entry_date(df, -1) == "N/A"

    def test_out_of_bounds_too_high(self):
        df = _make_df(10)
        assert _entry_date(df, 10) == "N/A"
        assert _entry_date(df, 999) == "N/A"

    def test_last_index(self):
        df = _make_df(10)
        assert _entry_date(df, 9) == _entry_date(df, len(df) - 1)


# ── Section 1 — condition frequency ────────────────────────────────

class TestConditionFrequency:
    def test_output_contains_header(self):
        df = _make_df(50)
        out = io.StringIO()
        with redirect_stdout(out):
            _print_condition_frequency(df, 30, 70, 2.0, True, 50)
        text = out.getvalue()
        assert "ENTRY CONDITION FREQUENCY (50 bars)" in text
        assert "Condition" in text
        assert "Bars" in text

    def test_output_shows_all_eight_conditions_with_volume(self):
        df = _make_df(50)
        out = io.StringIO()
        with redirect_stdout(out):
            _print_condition_frequency(df, 30, 70, 2.0, True, 50)
        text = out.getvalue()
        for fragment in (
            "regime_ok", "RSI < oversold (30)", "RSI > overbought (70)",
            "close < bb_lower", "close > bb_upper",
            "zscore < -2.0", "zscore > +2.0", "vol_confirm",
            "ALL long conditions", "ALL short conditions",
        ):
            assert fragment in text, f"missing: {fragment}"

    def test_without_volume_hides_vol_confirm(self):
        df = _make_df(50)
        out = io.StringIO()
        with redirect_stdout(out):
            _print_condition_frequency(df, 30, 70, 2.0, False, 50)
        text = out.getvalue()
        assert "vol_confirm" not in text

    def test_all_conditions_zero_when_nothing_passes(self):
        """All columns set to impossible values → every count = 0."""
        df = _make_df(20)
        df["regime_ok"] = False
        df["close"] = df["bb_lower"] - 1  # below lower
        df["rsi"] = np.nan                  # NaN → False
        out = io.StringIO()
        with redirect_stdout(out):
            _print_condition_frequency(df, 30, 70, 2.0, True, 20)
        text = out.getvalue()
        assert "ALL long conditions" in text
        assert "ALL short conditions" in text
        assert "0.0%" in text

    def test_respects_oversold_override(self):
        df = _make_df(50)
        # All RSI at 45; oversold=40 → some below, oversold=50 → all below
        df["rsi"] = 45.0
        out = io.StringIO()
        with redirect_stdout(out):
            _print_condition_frequency(df, 50, 70, 2.0, True, 50)
        text = out.getvalue()
        assert "RSI < oversold (50)" in text


# ── Section 2 — trade diagnostics ──────────────────────────────────

class TestTradeDiagnostics:
    def test_empty_trades_prints_no_trades(self):
        df = _make_df(30)
        trades = pd.DataFrame()
        out = io.StringIO()
        with redirect_stdout(out):
            _print_trade_diagnostics(trades, df, 20)
        assert "No trades to analyse" in out.getvalue()

    def test_prints_table_with_trades(self):
        df = _make_df(60)
        trades = _make_trades(3)
        out = io.StringIO()
        with redirect_stdout(out):
            _print_trade_diagnostics(trades, df, 20)
        text = out.getvalue()
        assert "TRADE DIAGNOSTICS (3 trades, top 3)" in text
        assert "Exit reason" in text
        assert "tp" in text
        assert "sl" in text

    def test_respects_top_n_limit(self):
        df = _make_df(100)
        trades = _make_trades(5)
        out = io.StringIO()
        with redirect_stdout(out):
            _print_trade_diagnostics(trades, df, 2)
        text = out.getvalue()
        assert "top 2" in text

    def test_sorts_by_pnl_worst_to_best(self):
        df = _make_df(100)
        trades = _make_trades(4)  # P&L: +1%, -1%, +2%, -2%
        out = io.StringIO()
        with redirect_stdout(out):
            _print_trade_diagnostics(trades, df, 20)
        text = out.getvalue()
        lines = [l for l in text.split("\n") if l.strip() and not l.startswith("===") and not l.startswith("#") and not l.startswith("-" ) and "Exit reason" not in l]
        # After sorting by P&L: -2% first, then -1%, +1%, +2%
        pnl_values = []
        for line in lines:
            parts = line.split()
            for p in parts:
                if p.endswith("%") and p != "BB%":
                    try:
                        pnl_values.append(float(p.replace("%", "")))
                    except ValueError:
                        pass
        if len(pnl_values) >= 2:
            assert pnl_values[0] <= pnl_values[-1], f"not sorted: {pnl_values}"


# ── Section 3 — win/loss comparison ────────────────────────────────

class TestWinLossComparison:
    def test_empty_trades_produces_no_output(self):
        df = _make_df(30)
        trades = pd.DataFrame()
        out = io.StringIO()
        with redirect_stdout(out):
            _print_win_loss_comparison(trades, df)
        assert out.getvalue() == ""

    def test_prints_winners_and_losers(self):
        df = _make_df(100)
        trades = _make_trades(5)  # 3 winners (+), 2 losers (-)
        out = io.StringIO()
        with redirect_stdout(out):
            _print_win_loss_comparison(trades, df)
        text = out.getvalue()
        assert "WIN VS LOSS COMPARISON" in text
        assert "Winners (n=3)" in text
        assert "Losers (n=2)" in text
        assert "RSI" in text
        assert "Z-score" in text
        assert "BB_pos" in text
        assert "Vol(x)" in text
        assert "Bars held" in text
        assert "P&L" in text
        assert "Long/Short mix" in text

    def test_handles_all_winners(self):
        df = _make_df(100)
        trades = _make_trades(5)
        trades["pnl_pct"] = [0.01, 0.02, 0.03, 0.04, 0.05]
        out = io.StringIO()
        with redirect_stdout(out):
            _print_win_loss_comparison(trades, df)
        assert "Winners (n=5)" in out.getvalue()
        assert "Losers (n=0)" in out.getvalue()

    def test_handles_all_losers(self):
        df = _make_df(100)
        trades = _make_trades(5)
        trades["pnl_pct"] = [-0.01, -0.02, -0.03, -0.04, -0.05]
        out = io.StringIO()
        with redirect_stdout(out):
            _print_win_loss_comparison(trades, df)
        text = out.getvalue()
        assert "Winners (n=0)" in text
        assert "Losers (n=5)" in text

"""Tests for Phase 2 EDA — gap detection, bucketing, expectancy, gate.

TDD discipline:
  - These tests are written BEFORE the implementation in src/strategy/gap_calc.py
    and scripts/eda_gap_expectancy.py. They fail (RED) until those modules
    are written. They must NOT depend on the network or real parquet cache.

Contract (docs/superpowers/plans/ROADMAP_MVP.md, Phase 2):
  - Gap = (Open_today - Close_yesterday) / Close_yesterday (signed).
  - Operating range: |gap| in [gap_min_pct, gap_max_pct].
  - 6 symmetric size buckets (3 DOWN + 3 UP):
      DOWN: [-2.0%, -1.0%), [-1.0%, -0.6%), [-0.6%, -0.3%]
      UP:   [0.3%, 0.6%), [0.6%, 1.0%), [1.0%, 2.0%)
    Boundaries are half-open [lo, hi) up to the top of the operating range
    where a single inclusive end avoids losing the boundary value.
  - Trade return (signed in direction of fill):
      DOWN gap -> LONG  -> return = (Close - Open) / Open
      UP   gap -> SHORT -> return = (Open - Close) / Open
  - Approx Sharpe = (mean / std) * sqrt(252 * frequency)  if std > 0 else NaN.
  - Cells with N < ROADMAP_MIN_CELL_THRESHOLD (20) are "insufficient data".
  - Gate PASSES iff at least one bucket has N >= EDAGateMinTradesPerCell
    (default 30, from settings.gates.eda_min_trades_per_cell) AND mean > 0.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from src.config import load_settings, SETTINGS_PATH, Settings, GatesConfig
from src.data.ohlcv import Split, write_split_manifest
from scripts.eda_gap_expectancy import CacheLoadSummary
from src.strategy.gap_calc import (
    DOWN_BUCKETS,
    EXPECTANCY_MIN_TRADES_DEFAULT,
    INSUFFICIENT_DATA_CELL_THRESHOLD,
    UP_BUCKETS,
    BucketRow,
    GateResult,
    bucket_label_for_sign,
    compute_buckets,
    compute_gaps_df,
    ensure_prev_close_column,
)


# ---------------------------------------------------------------------
# compute_gaps_df
# ---------------------------------------------------------------------


def _bar(d: date, prev_close: float, op: float, cl: float) -> dict:
    return {"date": d, "open": op, "close": cl, "prev_close": prev_close}


def test_compute_gaps_df_attaches_signed_pct_column() -> None:
    bars = pd.DataFrame([
        _bar(date(2020, 1, 2), prev_close=100.0, op=101.0, cl=102.0),  # +1.0%
        _bar(date(2020, 1, 3), prev_close=102.0, op=100.0, cl=101.0),  # -1.96%
    ])
    out = compute_gaps_df(bars)
    assert "gap_pct" in out.columns
    row0 = out.iloc[0]
    assert row0["gap_pct"] == pytest.approx(0.01)
    row1 = out.iloc[1]
    assert row1["gap_pct"] == pytest.approx((100.0 - 102.0) / 102.0)


def test_compute_gaps_df_drops_first_bar_without_prev_close() -> None:
    bars = pd.DataFrame([
        _bar(date(2020, 1, 2), prev_close=float("nan"), op=101.0, cl=102.0),
        _bar(date(2020, 1, 3), prev_close=102.0, op=100.0, cl=101.0),
    ])
    out = compute_gaps_df(bars)
    assert len(out) == 1
    assert pd.to_datetime(out.iloc[0]["date"]).date() == date(2020, 1, 3)


def test_compute_gaps_df_uses_sorted_input_invariant() -> None:
    bars = pd.DataFrame([
        _bar(date(2020, 1, 5), prev_close=104.0, op=105.0, cl=106.0),
        _bar(date(2020, 1, 2), prev_close=100.0, op=101.0, cl=102.0),
    ])
    out = compute_gaps_df(bars)
    dates = list(pd.to_datetime(out["date"]).dt.date)
    assert dates == sorted(dates)


# ---------------------------------------------------------------------
# bucket_label_for_sign
# ---------------------------------------------------------------------


def test_bucket_label_down_three_buckets_in_order() -> None:
    """DOWN buckets: -2 to -1, -1 to -0.6, -0.6 to -0.3 (last closed).

    Boundary convention: half-open [lo, hi) for non-last, closed [lo, hi]
    for last. Boundary values like -0.01, -0.006 land in the
    lower-in-index (more negative) bucket per the convention documented
    in src/strategy/gap_calc.py.
    """
    assert bucket_label_for_sign(-0.015) == "[-2.0%, -1.0%)"
    assert bucket_label_for_sign(-0.008) == "[-1.0%, -0.6%)"
    assert bucket_label_for_sign(-0.005) == "[-0.6%, -0.3%]"
    # Boundaries: -0.01 -> DOWN2 (next-up bucket); -0.006 -> DOWN3; -0.003 -> DOWN3 (closed top)
    assert bucket_label_for_sign(-0.01) == "[-1.0%, -0.6%)"
    assert bucket_label_for_sign(-0.006) == "[-0.6%, -0.3%]"
    assert bucket_label_for_sign(-0.003) == "[-0.6%, -0.3%]"
    assert bucket_label_for_sign(-0.025) is None  # out of range below
    assert bucket_label_for_sign(-0.002) is None  # too small in magnitude


def test_bucket_label_up_three_buckets_in_order() -> None:
    """UP buckets: 0.3 to 0.6, 0.6 to 1.0, 1.0 to 2.0 (last closed)."""
    assert bucket_label_for_sign(+0.005) == "[0.3%, 0.6%)"
    assert bucket_label_for_sign(+0.008) == "[0.6%, 1.0%)"
    assert bucket_label_for_sign(+0.015) == "[1.0%, 2.0%)"
    # Boundaries: 0.006 -> UP2 (lower-in-index); 0.01 -> UP3 (last, closed top)
    assert bucket_label_for_sign(+0.006) == "[0.6%, 1.0%)"
    assert bucket_label_for_sign(+0.01) == "[1.0%, 2.0%)"
    assert bucket_label_for_sign(+0.02) == "[1.0%, 2.0%)"  # top of operating window
    assert bucket_label_for_sign(+0.025) is None
    assert bucket_label_for_sign(+0.002) is None


def test_bucket_label_zero_is_none() -> None:
    assert bucket_label_for_sign(0.0) is None


def test_bucket_labels_have_six_distinct_values() -> None:
    """The full set of bucket labels has exactly 6 entries."""
    all_labels = {b for bs in (DOWN_BUCKETS, UP_BUCKETS) for b in bs}
    assert len(all_labels) == 6
    assert len(DOWN_BUCKETS) == 3
    assert len(UP_BUCKETS) == 3


# ---------------------------------------------------------------------
# compute_buckets + evaluate_gate
# ---------------------------------------------------------------------


def _synth_bars_with_gaps(n: int) -> pd.DataFrame:
    """Build n synthetic dev bars, all with gap_pct=-0.005 (DOWN bucket
    [-0.6%, -0.3%]) and return=+0.005 (LONG fill, positive edge)."""
    rows = []
    base = date(2019, 1, 2)
    for i in range(n):
        d = base + timedelta(days=i)
        prev_close = 100.0
        op = 99.5  # gap_pct = -0.005
        cl = op * 1.005  # return = +0.5%
        rows.append({"date": d, "open": op, "close": cl, "prev_close": prev_close})
    return pd.DataFrame(rows)


def test_compute_buckets_returns_one_row_per_label() -> None:
    bars = _synth_bars_with_gaps(20)
    df = compute_gaps_df(bars)
    rows = compute_buckets(df, min_trades=10)
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert isinstance(row, BucketRow)
    assert row.label == "[-0.6%, -0.3%]"
    assert row.direction == "DOWN"


def test_compute_buckets_drops_buckets_below_min_trades() -> None:
    bars = _synth_bars_with_gaps(5)  # below threshold
    df = compute_gaps_df(bars)
    rows = compute_buckets(df, min_trades=10)
    assert rows == []


def test_compute_buckets_mean_return_matches_synthetic() -> None:
    bars = _synth_bars_with_gaps(1)
    df = compute_gaps_df(bars)
    rows = compute_buckets(df, min_trades=1)
    assert len(rows) == 1
    r = rows[0]
    assert r.n == 1
    assert r.mean_return == pytest.approx(0.005, abs=1e-9)
    assert r.std_return == 0.0
    assert pd.isna(r.approx_sharpe)


def test_compute_buckets_signed_return_short_when_gap_up() -> None:
    """For an UP gap, the trade direction is SHORT, so return =
    (Open − Close) / Open — INVERTED from a long-only definition. Bars
    where close < open contribute positive return for an UP-gap bucket.
    """
    rows = [
        {"date": date(2020, 1, 2), "prev_close": 100.0,
         "open": 100.5, "close": 100.0},  # gap +0.5% (UP bucket [0.3%, 0.6%)),
                                         # short WIN: open->close is -0.5%
                                         # but inverted it's +0.5%
    ]
    df = compute_gaps_df(pd.DataFrame(rows))
    rows_out = compute_buckets(df, min_trades=1)
    assert len(rows_out) == 1
    r = rows_out[0]
    assert r.direction == "UP"
    # (open - close) / open = (100.5 - 100) / 100.5 ≈ 0.00498
    assert r.mean_return == pytest.approx((100.5 - 100.0) / 100.5, abs=1e-5)


def test_evaluate_gate_fail_when_below_default_threshold() -> None:
    from src.strategy.gap_calc import evaluate_gate

    bars = _synth_bars_with_gaps(25)  # < 30 threshold
    df = compute_gaps_df(bars)
    res = evaluate_gate(df, min_trades=EXPECTANCY_MIN_TRADES_DEFAULT)
    assert isinstance(res, GateResult)
    assert res.passed is False
    assert "no_bucket_with_positive_edge_at_threshold" in res.reason


def test_evaluate_gate_pass_at_n30_positive_mean() -> None:
    from src.strategy.gap_calc import evaluate_gate

    bars = _synth_bars_with_gaps(30)
    df = compute_gaps_df(bars)
    res = evaluate_gate(df, min_trades=30)
    assert res.passed is True
    assert any(r.n >= 30 and r.mean_return > 0 for r in res.buckets)


def test_evaluate_gate_fail_on_negative_mean_even_n30() -> None:
    from src.strategy.gap_calc import evaluate_gate

    # 30 bars where the trade loses: op * 0.995.
    rows = []
    base = date(2019, 1, 2)
    for i in range(30):
        d = base + timedelta(days=i)
        prev_close = 100.0
        op = 99.5  # DOWN bucket [-0.6%, -0.3%]
        cl = op * 0.995  # -0.5% return
        rows.append({"date": d, "open": op, "close": cl, "prev_close": prev_close})
    df = compute_gaps_df(pd.DataFrame(rows))
    res = evaluate_gate(df, min_trades=30)
    assert res.passed is False


# ---------------------------------------------------------------------
# render_report — cost-sensitivity advisor sign-bug lock-in.
# ---------------------------------------------------------------------


def test_render_report_cost_advisor_picks_best_positive_bucket() -> None:
    """Regression catch: render_report used to pick the bucket with
    max(abs(mean_return)). With a -10bp loser in `gate.buckets`, the
    advisor would quote -10.01 bp instead of the actual best positive
    bucket's +3 bp. Fix filters positive-mean first.
    """
    from scripts.eda_gap_expectancy import render_report
    from src.strategy.gap_calc import BucketRow, GateResult

    good = BucketRow(
        label="[-0.6%, -0.3%]", direction="DOWN", n=100,
        mean_return=+3e-4, std_return=0.01,
        approx_sharpe=1.0, frequency=0.10,
    )
    bad = BucketRow(
        label="[1.0%, 2.0%)", direction="UP", n=200,
        mean_return=-1e-3, std_return=0.01,
        approx_sharpe=-2.0, frequency=0.20,
    )
    summary = CacheLoadSummary(n_loaded=2, n_skipped=0, skipped_tickers=[])
    gate = GateResult(
        passed=True, reason="gate_pass", buckets=[good, bad],
        threshold=30, total_dev_bars=1000,
    )

    # Minimal df_dev with both `bucket` (so _render_sector_table skips
    # assign_bucket) and `ticker` (so the sector map doesn't KeyError).
    # We only assert on the cost advisor below; sector rows are uninteresting
    # here.
    df_dev = pd.DataFrame([{
        "gap_pct": 0.005,
        "trade_return": 0.001,
        "bucket": "[0.3%, 0.6%)",
        "ticker": "ZZZZ",  # sector_of("ZZZZ") -> "Unknown", safe
        "date": date(2020, 1, 2),
        "open": 100.0,
        "close": 101.0,
        "prev_close": 100.0,
    }])
    report = render_report(
        settings=load_settings(SETTINGS_PATH),
        gate=gate,
        df_dev=df_dev,
        cache_summary=summary,
        dev_start=date(2019, 1, 1),
        dev_end=date(2022, 12, 31),
        threshold=30,
    )

    # Best positive is +3bp. The buggy advisor would quote -10bp instead.
    assert "+3.00 bp/trade" in report
    assert "-10.01 bp/trade" not in report
    # Verdict reflects the FRAGILE 0.3× cost ratio.
    assert "FRAGILE" in report
    assert "0.30" in report  # 3 / 10 = 0.30, formatted without trailing zeros


# ---------------------------------------------------------------------
# prev_close handling — synthetic vs real-shape parquets.
#
# Real yfinance data (per scripts/download_data.py) lacks prev_close.
# `ensure_prev_close_column` is idempotent: if prev_close is already
# present the frame is returned as-is, otherwise prev_close is computed
# via groupby(ticker)['close'].shift(1).
# ---------------------------------------------------------------------


def test_ensure_prev_close_column_derives_when_missing() -> None:
    """Real-shape case (NO prev_close column): helper computes
    prev_close from the prior bar's close per ticker. First bar of each
    ticker has NaN — compute_gaps_df will drop it."""
    rows = [
        {"ticker": "AAPL", "date": date(2020, 1, 2), "open": 99.0, "close": 100.0},
        {"ticker": "AAPL", "date": date(2020, 1, 3), "open": 101.0, "close": 102.0},
        {"ticker": "AAPL", "date": date(2020, 1, 4), "open": 103.0, "close": 104.0},
        {"ticker": "MSFT", "date": date(2020, 1, 2), "open": 199.0, "close": 200.0},
        {"ticker": "MSFT", "date": date(2020, 1, 3), "open": 201.0, "close": 202.0},
    ]
    df = ensure_prev_close_column(pd.DataFrame(rows))
    aapl = df[df["ticker"] == "AAPL"].sort_values("date")
    assert pd.isna(aapl.iloc[0]["prev_close"])
    assert aapl.iloc[1]["prev_close"] == 100.0
    assert aapl.iloc[2]["prev_close"] == 102.0
    msft = df[df["ticker"] == "MSFT"].sort_values("date")
    assert pd.isna(msft.iloc[0]["prev_close"])
    assert msft.iloc[1]["prev_close"] == 200.0


def test_ensure_prev_close_column_is_no_op_when_already_present() -> None:
    """Synthetic case (prev_close already provided): helper is no-op.
    Row-by-row prev_close values must be preserved exactly, including
    for the first bar of each ticker (which had NaN in the derivation
    path)."""
    rows = [
        {"ticker": "AAPL", "date": date(2020, 1, 2), "open": 99.0,
         "close": 100.0, "prev_close": 100.0},
        {"ticker": "AAPL", "date": date(2020, 1, 3), "open": 101.0,
         "close": 102.0, "prev_close": 100.0},  # prev_close explicit
    ]
    df = ensure_prev_close_column(pd.DataFrame(rows))
    aapl = df[df["ticker"] == "AAPL"].sort_values("date")
    assert aapl.iloc[0]["prev_close"] == 100.0  # preserved, not NaN
    assert aapl.iloc[1]["prev_close"] == 100.0  # preserved


def test_ensure_prev_close_column_sorts_caller_order() -> None:
    """Helper re-sorts by (ticker, date) before shift — caller order
    doesn't matter for the derivation path."""
    rows = [
        {"ticker": "AAPL", "date": date(2020, 1, 4), "open": 103.0, "close": 104.0},
        {"ticker": "AAPL", "date": date(2020, 1, 2), "open": 99.0, "close": 100.0},
        {"ticker": "AAPL", "date": date(2020, 1, 3), "open": 101.0, "close": 102.0},
    ]
    df = ensure_prev_close_column(pd.DataFrame(rows))
    aapl = df[df["ticker"] == "AAPL"]
    prev_closes = list(aapl["prev_close"])
    # First bar becomes NaN (derivation); subsequent bars = prior close.
    assert pd.isna(prev_closes[0])
    assert prev_closes[1] == 100.0
    assert prev_closes[2] == 102.0


def test_run_eda_handles_real_shape_parquet_without_prev_close(tmp_path: Path) -> None:
    """Integration test (reviewer item #10): the orchestrator must run
    end-to-end against a parquet snapshot that mirrors what yfinance /
    scripts/download_data.py produces — i.e. columns are
    [date, open, high, low, close, adj_close, volume, ticker], with NO
    prev_close column. The helper derives it; the gate verdicts cleanly."""
    from scripts.eda_gap_expectancy import run_eda

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Build 35 bars mimicking yfinance output. Each ticker has a 0.3%-
    # magnitude DOWN gap and a +0.5% intraday fill (LONG trade wins).
    # After the first bar of each ticker is dropped (NaN prev_close),
    # 34 bars remain — all positive-edge. N>=30 → gate PASSES.
    rows = []
    base = date(2019, 1, 2)
    for i in range(35):
        d = base + timedelta(days=i)
        prev = 100.0
        op_ = 99.5  # gap_pct = -0.005 → DOWN bucket [-0.6%, -0.3%]
        cl = op_ * 1.005  # +0.5% return
        rows.append({
            "date": d,
            "open": op_,
            "high": cl + 0.1,
            "low": op_ - 0.1,
            "close": cl,
            "adj_close": cl,
            "volume": 1_000_000,
            "ticker": "TEST",
        })
    pd.DataFrame(rows).to_parquet(cache_dir / "TEST.parquet", index=False)

    # Suppress warning about pandas Parquet writing a 'ticker' column -- the
    # tests above exercise load_dev_bars which ignores 'ticker' in the file
    # and sets it from the file stem.

    # Write split manifest with all 35 dev days inside the window.
    split = Split(
        dev_start=date(2019, 1, 1),
        dev_end=date(2019, 2, 28),
        oos_start=date(2019, 3, 1),
        oos_end=date(2019, 12, 31),
    )
    manifest_path = tmp_path / "split.yaml"
    write_split_manifest(manifest_path, split)

    settings = load_settings(SETTINGS_PATH)

    rc = run_eda(
        settings=settings,
        cache_dir=cache_dir,
        out_report=tmp_path / "report.md",
        manifest_path=manifest_path,
    )
    assert rc == 0  # gate PASSES via derived prev_close
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "[GATE: PASS]" in text


# ---------------------------------------------------------------------
# Orchestrator: missing cache (return-code semantics, not SystemExit)
# ---------------------------------------------------------------------


def test_orchestrator_reports_missing_cache_fails_loud(tmp_path: Path) -> None:
    """If the cache dir has zero parquets AND no split manifest, the
    orchestrator returns 1 — Phase 1 must be run first. CLI callers
    raise SystemExit on this rc."""
    from scripts.eda_gap_expectancy import run_eda

    settings = load_settings(SETTINGS_PATH)
    bogus_cache = tmp_path / "no_data_here"
    bogus_cache.mkdir()
    rc = run_eda(
        settings=settings,
        cache_dir=bogus_cache,
        out_report=tmp_path / "report.md",
    )
    assert rc == 1


# ---------------------------------------------------------------------
# Orchestrator: synthetic PASS
# ---------------------------------------------------------------------


def test_orchestrator_writes_markdown_with_gate_marker(tmp_path: Path) -> None:
    from scripts.eda_gap_expectancy import run_eda

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    bars = _synth_bars_with_gaps(30)
    bars.to_parquet(cache_dir / "TEST.parquet", index=False)

    split = Split(
        dev_start=date(2019, 1, 1),
        dev_end=date(2019, 5, 1),
        oos_start=date(2019, 5, 2),
        oos_end=date(2019, 12, 31),
    )
    manifest_path = tmp_path / "split.yaml"
    write_split_manifest(manifest_path, split)

    settings = load_settings(SETTINGS_PATH)

    out_report = tmp_path / "report.md"
    rc = run_eda(
        settings=settings,
        cache_dir=cache_dir,
        out_report=out_report,
        manifest_path=manifest_path,
    )
    assert rc == 0  # gate PASSES
    text = out_report.read_text(encoding="utf-8")
    assert "[GATE: PASS]" in text
    assert "30" in text  # threshold echoed


# ---------------------------------------------------------------------
# Orchestrator: OOS bars are NOT loaded in Fase 2
# ---------------------------------------------------------------------


def test_orchestrator_does_not_load_oos_bars(tmp_path: Path) -> None:
    """Even if OOS parquets are present on disk, the orchestrator must NOT
    count them under Fase 2. The orchestrator reads the manifest (which
    declares the OOS window) and filters rows by dev window before
    bucketing."""
    from scripts.eda_gap_expectancy import run_eda

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    dev = _synth_bars_with_gaps(32).copy()
    dev["date"] = [date(2019, 1, 2) + timedelta(days=i) for i in range(len(dev))]
    dev.to_parquet(cache_dir / "DEV1.parquet", index=False)

    bad_rows = []
    base = date(2023, 1, 3)  # in OOS window
    for i in range(30):
        d = base + timedelta(days=i)
        prev_close = 100.0
        op = 99.5
        cl = op * 0.99  # -1% return
        bad_rows.append({"date": d, "open": op, "close": cl, "prev_close": prev_close})
    pd.DataFrame(bad_rows).to_parquet(cache_dir / "OOS1.parquet", index=False)

    manifest_path = tmp_path / "split.yaml"
    split = Split(
        dev_start=date(2019, 1, 1),
        dev_end=date(2022, 12, 31),
        oos_start=date(2023, 1, 1),
        oos_end=date(2024, 12, 31),
    )
    write_split_manifest(manifest_path, split)

    settings = load_settings(SETTINGS_PATH)
    rc = run_eda(
        settings=settings,
        cache_dir=cache_dir,
        out_report=tmp_path / "report.md",
        manifest_path=manifest_path,
    )
    assert rc == 0  # dev-only is PASS
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "[GATE: PASS]" in text


# ---------------------------------------------------------------------
# Orchestrator: settings.gates is wired through
# ---------------------------------------------------------------------


def test_settings_exposes_gates_block(tmp_path: Path) -> None:
    """settings.yaml declares a `gates:` block; the loader must expose it
    as a typed GatesConfig on Settings so the orchestrator can read the
    threshold without hardcoded constants."""
    settings = load_settings(SETTINGS_PATH)
    assert isinstance(settings.gates, GatesConfig)
    assert settings.gates.eda_min_trades_per_cell == 30
    assert settings.gates.backtest_oos_min_sharpe == 0.0
    assert settings.gates.backtest_oos_min_profit_factor == 1.0
    assert settings.gates.paper_trading_min_days == 15

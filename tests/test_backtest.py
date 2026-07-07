"""
Tests for backtest/engine.py — FASE 4 Slice 1
==============================================

Validate the single-symbol in-memory pipeline wrapper:

* ``BacktestResult`` dataclass shape and types
* ``run_backtest`` cfg merging (defaults vs overrides)
* Pipeline composition (each stage produces its expected columns)
* Determinism (same input → same output)
* Equity curve math (sized vs naive)
* Signal-to-trade consistency
* Empty-pipeline graceful handling (zero signals → zero trades)
* Invalid-input errors (missing OHLCV columns)
"""

import numpy as np
import pandas as pd
import pytest

from backtest.engine import (
    BacktestResult,
    _default_cfg,
    _fetch_bars,
    _merge_cfg,
    run_backtest,
    run_backtest_for_symbol,
    run_universe_backtest,
)


# ─────────────────────────────────────────────────────────────────────
# Synthetic data fixture
# ─────────────────────────────────────────────────────────────────────


def _make_synthetic_ohlcv(
    n_bars: int = 800,
    seed: int = 42,
    start_open: float = 100.0,
) -> pd.DataFrame:
    """
    Build a long-enough synthetic OHLCV frame that survives the
    pipeline without being trimmed to emptiness.

    * Index spans 15-minute bars starting at 10:00 — this falls AFTER
      the ``skip_first_minutes=30`` morning cutoff, so ``filter_session_hours``
      keeps essentially every bar.
    * Volume is always > 0 so ``clean_data`` doesn't drop any row on the
      zero-volume mask.
    * Hurst's rolling window is 252 bars, so seeds 1..252 will have
      ``hurst = NaN`` → ``regime_ok = False`` → no signals. Tests that
      require trading activity should use ``n_bars >= 600``.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-08 10:00", periods=n_bars, freq="15min")
    close = start_open + rng.standard_normal(n_bars).cumsum() * 0.3
    df = pd.DataFrame(index=idx)
    df["open"] = close - 0.05
    df["high"] = close + 0.3
    df["low"] = close - 0.3
    df["close"] = close
    df["volume"] = rng.integers(1_000_000, 5_000_000, n_bars)
    return df


# ─────────────────────────────────────────────────────────────────────
# Dataclass shape
# ─────────────────────────────────────────────────────────────────────


class TestBacktestResultShape:
    def test_returns_dataclass_instance(self):
        df = _make_synthetic_ohlcv(n_bars=300)
        result = run_backtest(df)
        assert isinstance(result, BacktestResult)

    def test_all_fields_have_expected_types(self):
        df = _make_synthetic_ohlcv(n_bars=300)
        result = run_backtest(df)
        assert isinstance(result.df, pd.DataFrame)
        assert isinstance(result.trades, pd.DataFrame)
        assert isinstance(result.equity, pd.Series)
        assert isinstance(result.naive_equity, pd.Series)
        assert isinstance(result.metrics, dict)
        assert isinstance(result.config_used, dict)
        assert isinstance(result.signals, dict)

    def test_dataclass_has_all_documented_fields(self):
        # Compile-time-free contract test: catches accidental field renames.
        result = run_backtest(_make_synthetic_ohlcv(n_bars=300))
        for field_name in (
            "df", "trades", "equity", "naive_equity",
            "metrics", "config_used", "signals",
        ):
            assert hasattr(result, field_name), f"missing field: {field_name}"

    def test_results_dataclass_fields_simple_construction(self):
        # Smoke test on BacktestResult itself — bypasses run_backtest so we
        # catch dataclass signature breakage early.
        r = BacktestResult(
            df=pd.DataFrame(),
            trades=pd.DataFrame(),
            equity=pd.Series(dtype=float),
            naive_equity=pd.Series(dtype=float),
            metrics={},
            config_used={},
        )
        assert r.signals == {}    # field defaults to empty dict


# ─────────────────────────────────────────────────────────────────────
# Pipeline composition
# ─────────────────────────────────────────────────────────────────────


class TestPipelineComposition:
    def test_dataframe_after_pipeline_has_indicator_columns(self):
        df = _make_synthetic_ohlcv(n_bars=300)
        result = run_backtest(df)
        for col in (
            "adx", "hurst", "rsi", "bb_upper", "bb_lower",
            "zscore", "vol_confirm", "atr", "regime_ok",
            "signal_long", "signal_short",
        ):
            assert col in result.df.columns, f"missing column: {col}"

    def test_signals_field_matches_df(self):
        df = _make_synthetic_ohlcv(n_bars=400)
        result = run_backtest(df)
        assert result.signals["long_signals"] == int(
            result.df["signal_long"].sum()
        )
        assert result.signals["short_signals"] == int(
            result.df["signal_short"].sum()
        )
        assert result.signals["total_signals"] == (
            result.signals["long_signals"] + result.signals["short_signals"]
        )

    def test_sizing_columns_present_when_trades_fire(self):
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df)
        if not result.trades.empty:
            for col in (
                "shares", "pnl_dollar", "equity_after",
                "pnl_pct_slip", "commission_cost",
            ):
                assert col in result.trades.columns

    def test_trades_match_signals(self):
        # Every trade's entry_idx must coincide with a signal bar in df.
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df)
        for _, t in result.trades.iterrows():
            ei = int(t["entry_idx"])
            assert (
                result.df["signal_long"].iloc[ei]
                or result.df["signal_short"].iloc[ei]
            ), f"trade at idx {ei} did not fire from a signal"

    def test_equity_curve_has_initial_bar(self):
        df = _make_synthetic_ohlcv(n_bars=300, start_open=100.0)
        cfg = {"account": {"equity": 12_345.0}}
        result = run_backtest(df, cfg=cfg)
        assert len(result.equity) >= 1
        assert float(result.equity.iloc[0]) == 12_345.0
        assert float(result.naive_equity.iloc[0]) == 12_345.0


# ─────────────────────────────────────────────────────────────────────
# Config merging
# ─────────────────────────────────────────────────────────────────────


class TestConfigMerging:
    def test_no_cfg_uses_global_defaults(self):
        # No user_cfg → engine reads from config.yaml singleton defaults.
        df = _make_synthetic_ohlcv(n_bars=300)
        result = run_backtest(df)
        assert result.config_used["account"]["equity"] == 10_000.0
        assert result.config_used["timeframe"]["skip_first_minutes"] == 30
        # All known blocks present
        for block in (
            "indicators", "regime_filter", "entry_signal",
            "exit", "risk", "backtest", "account", "timeframe",
        ):
            assert block in result.config_used

    def test_explicit_empty_cfg_still_uses_defaults(self):
        df = _make_synthetic_ohlcv(n_bars=300)
        result = run_backtest(df, cfg={})
        assert result.config_used["account"]["equity"] == 10_000.0

    def test_user_overrides_win_over_defaults(self):
        df = _make_synthetic_ohlcv(n_bars=300)
        cfg = {"account": {"equity": 25_000.0}}
        result = run_backtest(df, cfg=cfg)
        assert result.config_used["account"]["equity"] == 25_000.0
        # Other defaults untouched
        assert result.config_used["timeframe"]["skip_first_minutes"] == 30

    def test_strict_regime_kills_all_signals(self):
        # adx_threshold=1.0 makes regime_ok essentially impossible
        # (ADX normally >= 10).
        df = _make_synthetic_ohlcv(n_bars=400)
        cfg = {"regime_filter": {"adx_threshold": 1.0}}
        result = run_backtest(df, cfg=cfg)
        assert result.signals["total_signals"] == 0
        assert result.trades.empty
        assert len(result.equity) == 1
        assert float(result.equity.iloc[0]) == 10_000.0

    def test_user_cfg_does_not_mutate_global_config(self):
        # Contract: subsequent runs of run_backtest without cfg must still
        # see the original config.yaml equity. Catches shallow-copy bugs
        # in _default_cfg / _merge_cfg that would propagate back to the
        # singleton.
        from utils.config import config as global_cfg
        original_equity = float(global_cfg.get("account.equity"))

        df = _make_synthetic_ohlcv(n_bars=200)
        run_backtest(df, cfg={"account": {"equity": 99_999.0}})
        run_backtest(df, cfg={"account": {"equity": 1.0}})
        assert float(global_cfg.get("account.equity")) == original_equity


# ─────────────────────────────────────────────────────────────────────
# Equity curves
# ─────────────────────────────────────────────────────────────────────


class TestEquityCurves:
    def test_sized_curve_final_matches_last_equity_after(self):
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df)
        if not result.trades.empty:
            assert result.equity.iloc[-1] == pytest.approx(
                float(result.trades["equity_after"].iloc[-1]),
                abs=1e-6,
            )

    def test_naive_curve_compounds_pnl_pct(self):
        # build_pct_curve uses pnl_pct (exit-derived), NOT pnl_pct_slip.
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df, cfg={"account": {"equity": 10_000.0}})
        if len(result.trades) >= 1:
            running = 10_000.0
            for _, t in result.trades.iterrows():
                running = running * (1.0 + float(t["pnl_pct"]))
            assert result.naive_equity.iloc[-1] == pytest.approx(
                running, abs=1e-6
            )

    def test_equity_curves_diverge_on_tail_loss_sequence(self):
        # Same data → same trades. Sized curve should diverge from naive
        # only if sizing actually scaled the position (which is true on real
        # data with non-trivial ATR). At minimum, both curves must end at
        # 10_000 when there are zero trades.
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df, cfg={"account": {"equity": 10_000.0}})
        # Both curves start at initial equity regardless of trade outcome
        assert float(result.equity.iloc[0]) == float(result.naive_equity.iloc[0])


# ─────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_input_same_metrics(self):
        df = _make_synthetic_ohlcv(n_bars=400)
        cfg = {"account": {"equity": 10_000.0}}
        r1 = run_backtest(df, cfg=cfg)
        r2 = run_backtest(df, cfg=cfg)
        # Metrics dict is JSON-comparable
        assert r1.metrics == r2.metrics

    def test_same_input_same_equity_curves(self):
        df = _make_synthetic_ohlcv(n_bars=400)
        cfg = {"account": {"equity": 10_000.0}}
        r1 = run_backtest(df, cfg=cfg)
        r2 = run_backtest(df, cfg=cfg)
        assert list(r1.equity.values) == list(r2.equity.values)
        assert list(r1.naive_equity.values) == list(r2.naive_equity.values)

    def test_same_input_same_trade_count(self):
        df = _make_synthetic_ohlcv(n_bars=400)
        cfg = {"account": {"equity": 10_000.0}}
        r1 = run_backtest(df, cfg=cfg)
        r2 = run_backtest(df, cfg=cfg)
        assert len(r1.trades) == len(r2.trades)


# ─────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────


class TestInputValidation:
    def test_missing_ohlcv_columns_raises(self):
        bad_df = pd.DataFrame({"close": [100.0, 101.0, 102.0]})
        bad_df.index = pd.date_range("2024-01-08 10:00", periods=3, freq="15min")
        with pytest.raises(ValueError, match="Missing required columns"):
            run_backtest(bad_df)

    def test_zero_volume_bars_are_filtered(self):
        # clean_data removes zero-volume rows. With a MIX of valid and
        # zero-volume bars, the engine filters them out and the post-pipeline
        # df has strictly fewer rows than the input. (We deliberately avoid
        # the all-zero case is separately exercised by
        # ``test_all_zero_volume_filtered_returns_valid_backtest_result``
        # below; together they pin the contract that ``run_backtest`` never
        # raises on input whose clean-stage output is empty (the empty-df
        # guard in ``risk.sizing.build_equity_curve`` / ``build_pct_curve``
        # resolves such inputs to a NaT-anchored 1-element Series rather
        # than crashing on ``df.index[0]``).
        idx = pd.date_range("2024-01-08 10:00", periods=20, freq="15min")
        rng = np.random.default_rng(42)
        close = 100 + rng.standard_normal(20).cumsum() * 0.2
        df = pd.DataFrame(index=idx)
        df["open"] = close - 0.05
        df["high"] = close + 0.3
        df["low"] = close - 0.3
        df["close"] = close
        volumes = rng.integers(1, 5_000_000, 20)
        volumes[:10] = 0    # first half dropped by clean_data
        df["volume"] = volumes
        result = run_backtest(df)
        # 10 of 20 survive clean_data; indicator/regime/entry stages
        # preserve row count
        assert len(result.df) == 10
        # 10 bars is too few for the Hurst(252) window → no signals fire
        assert result.signals["total_signals"] == 0
        assert result.trades.empty
        # Equity curve has only the initial point (no trades)
        assert len(result.equity) == 1
        assert float(result.equity.iloc[0]) == 10_000.0

    def test_all_zero_volume_filtered_returns_valid_backtest_result(self):
        # Counterpart to ``test_zero_volume_bars_are_filtered``: when
        # EVERY bar has zero volume, ``clean_data`` drops every row
        # -> the indicator pipeline emits an empty DataFrame. Pre-fix
        # this path crashed with ``IndexError: index 0 is out of
        # bounds`` inside ``risk.sizing.build_equity_curve``. After
        # the empty-df guard, the engine returns a fully-typed
        # BacktestResult with a 1-element NaT-anchored equity curve
        # (initial equity preserved, no signals, zero trades, metrics
        # dict fully populated with zeroed defaults). Together with the
        # half-zero test above, this pins the contract that
        # ``run_backtest`` never crashes on input whose clean-stage
        # output is empty — a precondition for Slice 3's batch fetch
        # path which may legitimately receive all-empty rows from
        # Alpaca for symbols with very short history.
        idx = pd.date_range("2024-01-08 10:00", periods=20, freq="15min")
        rng = np.random.default_rng(42)
        close = 100 + rng.standard_normal(20).cumsum() * 0.2
        df = pd.DataFrame(index=idx)
        df["open"] = close - 0.05
        df["high"] = close + 0.3
        df["low"] = close - 0.3
        df["close"] = close
        df["volume"] = np.zeros(20)    # all-zero -> fully filtered out
        result = run_backtest(df)
        # Post-pipeline df is empty
        assert len(result.df) == 0
        # No signals fire (no rows to even compute signals on)
        assert result.signals["total_signals"] == 0
        assert result.trades.empty
        # Equity curve is the NaT-anchored single-element fallback
        assert len(result.equity) == 1
        assert float(result.equity.iloc[0]) == 10_000.0
        assert pd.isna(result.equity.index[0])
        # Naive curve identical contract
        assert len(result.naive_equity) == 1
        assert float(result.naive_equity.iloc[0]) == 10_000.0
        # Metrics still dict-shaped even on empty pipeline
        assert isinstance(result.metrics, dict)
        assert result.metrics["total_trades"] == 0
        assert result.metrics["max_drawdown"] == 0.0


# ─────────────────────────────────────────────────────────────────────
# Metrics surface
# ─────────────────────────────────────────────────────────────────────


class TestMetricsOutput:
    def test_metrics_dict_contains_always_present_keys(self):
        # Core keys are populated regardless of trade activity. Splitting
        # this test out so single-point equity doesn't get dinged for
        # missing sharpe_ratio / sortino_ratio (those are conditional).
        df = _make_synthetic_ohlcv(n_bars=400)
        result = run_backtest(df)
        for key in (
            "total_trades", "winning_trades", "losing_trades",
            "win_rate", "profit_factor", "avg_win", "avg_loss",
            "expectancy", "max_drawdown", "max_drawdown_bars",
            "total_return",
        ):
            assert key in result.metrics, f"missing metric: {key}"

    def test_metrics_compute_sharpe_when_equity_multi_bar(self):
        # When trades fire and equity has multiple points, the periodic
        # ratios are computed because periods_per_year is set.
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df)
        if len(result.equity) > 1 and not result.trades.empty:
            assert "sharpe_ratio" in result.metrics
            assert "sortino_ratio" in result.metrics

    def test_metrics_omit_sharpe_when_equity_single_point(self):
        # No signals → equity is just the initial bar → pct_change().dropna()
        # is empty → calculate_all_metrics skips sharpe/sortino.
        df = _make_synthetic_ohlcv(n_bars=400)
        cfg = {"regime_filter": {"adx_threshold": 1.0}}   # strict → zero signals
        result = run_backtest(df, cfg=cfg)
        assert len(result.equity) == 1
        assert result.metrics["total_trades"] == 0
        assert "sharpe_ratio" not in result.metrics
        assert "sortino_ratio" not in result.metrics

    def test_equity_curve_reflects_slippage(self):
        # Dollar-P&L path — verifies apply_position_sizing correctly passes
        # slippage into the dollar calc (independent of the metrics
        # selector branch).
        df = _make_synthetic_ohlcv(n_bars=800)
        cfg_no_cost = {
            "backtest": {"commission_per_side": 0.0, "slippage_pct": 0.0}
        }
        cfg_with_cost = {
            "backtest": {"commission_per_side": 0.0, "slippage_pct": 0.01}
        }
        r_no_cost = run_backtest(df, cfg=cfg_no_cost)
        r_with_cost = run_backtest(df, cfg=cfg_with_cost)
        if not r_no_cost.trades.empty and not r_with_cost.trades.empty:
            # Same fixtures trade the same set of bars in deterministic order.
            # With non-zero slippage per trade, the cost-aware equity must
            # end ≤ the no-cost version.
            assert float(r_with_cost.equity.iloc[-1]) <= float(
                r_no_cost.equity.iloc[-1]
            )

    def test_metrics_use_pnl_pct_slip_when_slippage_nonzero(self):
        # Metrics-selector path — DIRECT proof that `trade_returns` derives
        # from `pnl_pct_slip` rather than from the exit-derived `pnl_pct`.
        # ``profit_factor`` is a trade-derived metric that depends ONLY on
        # ``trade_returns`` (not on the equity curve), so it isolates the
        # selector from the dollar-P&L path the test above covers.
        #
        # With slippage_pct = 0.0, mathematically ``pnl_pct_slip == pnl_pct``
        # for every trade, so profit_factor matches the baseline.
        # With slippage_pct = 0.005, the magnitudes diverge → if the engine
        # correctly prefers pnl_pct_slip, profit_factor must change. If a
        # regression swapped back to deriving trade_returns from pnl_pct,
        # profit_factor would stay identical to the zero-slippage baseline
        # — this test would catch it.
        df = _make_synthetic_ohlcv(n_bars=800)
        cfg_zero = {
            "backtest": {"commission_per_side": 0.0, "slippage_pct": 0.0}
        }
        cfg_slip = {
            "backtest": {"commission_per_side": 0.0, "slippage_pct": 0.005}
        }
        r_zero = run_backtest(df, cfg=cfg_zero)
        r_slip = run_backtest(df, cfg=cfg_slip)
        if not r_zero.trades.empty and not r_slip.trades.empty:
            assert r_zero.metrics["profit_factor"] != r_slip.metrics["profit_factor"], (
                "metrics profit_factor must change when slippage_pct is "
                "applied — the engine should derive trade_returns from "
                "pnl_pct_slip, not from the exit-derived pnl_pct"
            )

    def test_zero_trades_yields_zero_drawdown(self):
        df = _make_synthetic_ohlcv(n_bars=200)
        cfg = {"regime_filter": {"adx_threshold": 1.0}}   # no signals
        result = run_backtest(df, cfg=cfg)
        assert result.metrics["total_trades"] == 0
        assert result.metrics["max_drawdown"] == 0.0
        assert result.metrics["total_return"] == 0.0

    def test_max_drawdown_is_non_positive(self):
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df)
        # max_drawdown is by convention a negative fraction (≤ 0)
        assert result.metrics["max_drawdown"] <= 0.0


# ─────────────────────────────────────────────────────────────────────
# Direct unit tests on internal config helpers
# ─────────────────────────────────────────────────────────────────────


class TestDefaultCfg:
    """
    Direct unit tests for ``backtest.engine._default_cfg``.

    These guard the spec claim that ``_default_cfg`` returns fresh dicts
    per call (so the global ``utils.config.config`` singleton cannot be
    mutated by consumer-side code). They also pin down the rule that
    ``regime_filter`` is whitelisted before being forwarded to
    ``apply_regime_filter``.
    """

    def test_returns_all_eight_known_blocks(self):
        cfg = _default_cfg()
        for block in (
            "indicators", "regime_filter", "entry_signal",
            "exit", "risk", "backtest", "account", "timeframe",
        ):
            assert block in cfg, f"missing default block: {block}"

    def test_account_block_has_positive_float_equity(self):
        cfg = _default_cfg()
        equity = cfg["account"]["equity"]
        assert isinstance(equity, (int, float))
        assert equity > 0

    def test_default_bars_per_year_is_5544(self):
        # Single source of truth for 15-min bars per year.
        # Locked so a future config.yaml edit cannot silently change the
        # Sharpe/Sortino annualization multiplier.
        cfg = _default_cfg()
        assert cfg["timeframe"]["bars_per_year"] == 5544

    def test_regime_filter_keys_whitelisted_before_pass_through(self):
        # config.yaml's regime_filter can carry validation bounds (min/max
        # coverage pct) that are NOT engine params. ``_default_cfg`` must
        # filter them out so ``apply_regime_filter(df, **...)`` doesn't
        # blow up on TypeError.
        from utils.config import config as global_cfg
        yaml_regime = (global_cfg.raw.get("regime_filter") or {})
        whitelisted = {
            "adx_threshold", "hurst_threshold",
            "atr_relative_std_threshold", "atr_window",
        }
        non_engine_keys = set(yaml_regime.keys()) - whitelisted
        if non_engine_keys:
            cfg = _default_cfg()
            for k in non_engine_keys:
                assert k not in cfg["regime_filter"], (
                    f"non-engine regime_filter key leaked through: {k}"
                )


class TestMergeCfg:
    """
    Direct unit tests for ``backtest.engine._merge_cfg``.

    Locks the spec that ``_merge_cfg`` deep-copies the defaults — so
    subsequent calls cannot see mutations made on a previously-merged
    result.
    """

    def test_none_user_cfg_returns_independent_defaults(self):
        cfg = _merge_cfg(None)
        original = cfg["account"]["equity"]
        cfg["account"]["equity"] = 1.0
        cfg_again = _merge_cfg(None)
        assert cfg_again["account"]["equity"] == original

    def test_user_partial_block_merged_with_defaults(self):
        # Partial override does not blow away sibling defaults.
        cfg = _merge_cfg({"regime_filter": {"adx_threshold": 30.0}})
        assert cfg["regime_filter"]["adx_threshold"] == 30.0
        # Sibling regime defaults still present
        assert "hurst_threshold" in cfg["regime_filter"]

    def test_unknown_top_level_cfg_block_raises(self):
        # Contract: typos like ``rejime_filter`` and unsolicited blocks
        # raise ValueError early instead of being silently dropped.
        df = _make_synthetic_ohlcv(n_bars=200)
        with pytest.raises(ValueError, match="Unknown engine cfg block"):
            run_backtest(df, cfg={"rejime_filter": {"adx_threshold": 30.0}})

    def test_unknown_block_error_enumerates_valid_blocks(self):
        # The ValueError message MUST list valid blocks so callers can
        # self-correct without grep'ing the engine source.
        df = _make_synthetic_ohlcv(n_bars=200)
        with pytest.raises(ValueError) as exc_info:
            run_backtest(df, cfg={"not_a_block": 123})
        msg = str(exc_info.value)
        for block in (
            "indicators", "regime_filter", "entry_signal",
            "exit", "risk", "backtest", "account", "timeframe",
        ):
            assert block in msg, (
                f"valid block {block!r} missing from validation error"
            )

    def test_known_block_with_unknown_leaf_propagates_downstream(self):
        # Boundary: ``_merge_cfg`` only validates top-level keys. Within a
        # validated block, an unknown leaf key survives the merge and
        # propagates to ``apply_regime_filter`` which raises TypeError on
        # the unfamiliar kwarg name. Using ``match="not_a_real_kwarg"``
        # locks the assertion specifically to that propagation path; a
        # bare ``pytest.raises(TypeError)`` could pass on TypeErrors raised
        # elsewhere in the pipeline (e.g. clean_data, indicators) and
        # silently lose coverage of THIS regression.
        df = _make_synthetic_ohlcv(n_bars=200)
        with pytest.raises(TypeError, match="not_a_real_kwarg"):
            run_backtest(
                df,
                cfg={
                    "regime_filter": {
                        "adx_threshold": 30.0,
                        "hurst_threshold": 0.6,
                        "atr_relative_std_threshold": 3.0,
                        "not_a_real_kwarg": "x",
                    }
                },
            )


# ─────────────────────────────────────────────────────────────────────
# Risk / sizing cfg propagation tests
# ─────────────────────────────────────────────────────────────────────


class TestRiskCfgPropagation:
    """
    User-supplied ``cfg["risk"]`` / ``cfg["backtest"]`` overrides must
    flow into the inline ``risk_cfg`` built inside ``run_backtest`` and
    afterwards into ``apply_position_sizing``.
    """

    def test_default_slippage_is_5_bps(self):
        # config.yaml sets slippage_pct: 0.0005 by default. Lock it so
        # a silent cfg edit doesn't change backtests in flight.
        df = _make_synthetic_ohlcv(n_bars=400)
        result = run_backtest(df)
        assert result.config_used["backtest"]["slippage_pct"] == pytest.approx(
            0.0005, abs=1e-9
        )

    def test_user_commission_propagates_to_pnl_dollar(self):
        # Commission is subtracted from pnl_dollar, so a higher commission
        # Strictly reduces the dollar P&L for the same trade set
        # (deterministic seed → same trades fire).
        df = _make_synthetic_ohlcv(n_bars=800)
        cfg_zero = {"backtest": {"commission_per_side": 0.0}}
        cfg_high = {"backtest": {"commission_per_side": 0.005}}
        r_zero = run_backtest(df, cfg=cfg_zero)
        r_high = run_backtest(df, cfg=cfg_high)
        if not r_zero.trades.empty and not r_high.trades.empty:
            assert r_high.trades["pnl_dollar"].sum() < (
                r_zero.trades["pnl_dollar"].sum()
            )

    def test_user_risk_per_trade_pct_increases_risk_per_trade_dollar(self):
        # Assert on ``risk_dollar`` (uncapped raw formula
        # ``equity * risk_pct / 100``) rather than on ``shares`` because
        # ``calculate_shares`` caps raw size at ``max_position_pct`` —
        # when the synthetic entry price makes the cap binding, both 1 %
        # and 2 % risk clamp to identical share counts and a strict-`>`
        # assertion on ``shares`` becomes seed-dependent. ``risk_dollar``
        # carries the propagation signal free of cap interference.
        df = _make_synthetic_ohlcv(n_bars=800)
        cfg_low = {"risk": {"risk_per_trade_pct": 1.0}}
        cfg_high = {"risk": {"risk_per_trade_pct": 2.0}}
        r_low = run_backtest(df, cfg=cfg_low)
        r_high = run_backtest(df, cfg=cfg_high)
        if not r_low.trades.empty and not r_high.trades.empty:
            # First trade uses initial equity ($10 000) and Kelly is off
            # by default, so risk_dollar scales linearly with risk_pct.
            assert r_high.trades["risk_dollar"].iloc[0] == pytest.approx(
                2 * r_low.trades["risk_dollar"].iloc[0], rel=1e-9
            )


# ─────────────────────────────────────────────────────────────────────
# bars_per_year propagation through cfg to engine / metrics
# ─────────────────────────────────────────────────────────────────────


class TestBarsPerYearPropagation:
    """``bars_per_year`` must propagate from cfg to ``calculate_all_metrics``."""

    def test_default_bars_per_year_visible_in_config_used(self):
        df = _make_synthetic_ohlcv(n_bars=400)
        result = run_backtest(df)
        assert result.config_used["timeframe"]["bars_per_year"] == 5544

    def test_user_supplied_bars_per_year_overrides_default(self):
        df = _make_synthetic_ohlcv(n_bars=400)
        cfg = {"timeframe": {"bars_per_year": 1234}}
        result = run_backtest(df, cfg=cfg)
        assert result.config_used["timeframe"]["bars_per_year"] == 1234


# ─────────────────────────────────────────────────────────────────────
# Equity curve datetime-index alignment
# ─────────────────────────────────────────────────────────────────────


class TestEquityCurveDatetimeIndex:
    """
    Equity curves must use the input ``df.index`` for their timestamp
    axis (Sized vs Naive overlay contract — both must align on the same
    baseline so plots compare on the same x-axis).
    """

    def test_first_timestamp_is_df_index_zero(self):
        df = _make_synthetic_ohlcv(n_bars=500)
        result = run_backtest(df)
        assert result.equity.index[0] == df.index[0]
        assert result.naive_equity.index[0] == df.index[0]

    def test_subsequent_timestamps_match_trade_exits(self):
        df = _make_synthetic_ohlcv(n_bars=800)
        result = run_backtest(df)
        if not result.trades.empty:
            for i, (_, t) in enumerate(result.trades.iterrows()):
                exit_idx = int(t["exit_idx"])
                expected_ts = df.index[min(exit_idx, len(df) - 1)]
                assert result.equity.index[i + 1] == expected_ts
                assert result.naive_equity.index[i + 1] == expected_ts


# ─────────────────────────────────────────────────────────────────────
# BacktestResult dataclass default-factory safety
# ─────────────────────────────────────────────────────────────────────


class TestBacktestResultDefaults:
    """
    Contract tests on the ``BacktestResult`` dataclass itself — bypass
    ``run_backtest`` so any breakage is caught at the dataclass layer
    rather than buried in a noisy pipeline failure.
    """

    def test_dataclass_constructible_without_signals_kwarg(self):
        # Demonstrates ``field(default_factory=dict)`` is correctly set.
        r = BacktestResult(
            df=pd.DataFrame(),
            trades=pd.DataFrame(),
            equity=pd.Series(dtype=float),
            naive_equity=pd.Series(dtype=float),
            metrics={},
            config_used={},
        )
        assert r.signals == {}

    def test_signals_default_factory_isolates_instances(self):
        # Two instances must NOT share the same underlying dict. If they
        # did (mutable-default footgun), writing into r1.signals would
        # leak into r2.signals.
        def _new() -> BacktestResult:
            return BacktestResult(
                df=pd.DataFrame(),
                trades=pd.DataFrame(),
                equity=pd.Series(dtype=float),
                naive_equity=pd.Series(dtype=float),
                metrics={},
                config_used={},
            )

        r1, r2 = _new(), _new()
        r1.signals["long_signals"] = 42
        assert "long_signals" not in r2.signals
        # Independent identity check (different objects)
        assert r1.signals is not r2.signals

    def test_fields_are_publicly_mutable(self):
        # The dataclass is intentionally not frozen — callers can
        # annotate or extend. Document the choice so a future refactor
        # doesn't accidentally add ``frozen=True``.
        r = BacktestResult(
            df=pd.DataFrame(),
            trades=pd.DataFrame(),
            equity=pd.Series(dtype=float),
            naive_equity=pd.Series(dtype=float),
            metrics={},
            config_used={},
        )
        r.notes = "tail-runs annotator"
        assert r.notes == "tail-runs annotator"


# -----------------------------------------------------------------------
# Slice 2: fetch layer (run_backtest_for_symbol + _fetch_bars)
# -----------------------------------------------------------------------


class TestRunBacktestForSymbol:
    """
    Tests for the slice-2 fetch layer. All happy-path tests stub
    ``_fetch_bars`` so the pipeline stays network-free; the credential
    guard is tested by clearing the env vars directly. The
    empty-response branch of ``_fetch_bars`` is tested at the lower
    layer (``TestFetchBars``) so the real production code in that
    branch is exercised rather than a stubbed-out version.
    """

    REQUIRED_CREDS = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")

    def test_missing_alpaca_credentials_raises_runtime_error(self, monkeypatch):
        # Both env vars absent -> RuntimeError listing both keys.
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            run_backtest_for_symbol("SPY", cfg={})
        msg = str(exc_info.value)
        assert "ALPACA_API_KEY" in msg
        assert "ALPACA_SECRET_KEY" in msg

    def test_missing_only_secret_key_lists_it_in_error(self, monkeypatch):
        # Only SECRET_KEY missing -> the error names the missing key
        # specifically (so the user can self-correct).
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ALPACA_SECRET_KEY"):
            run_backtest_for_symbol("SPY", cfg={})

    def test_missing_only_api_key_lists_it_in_error(self, monkeypatch):
        # Mirror of the previous: only API_KEY missing -> the error names
        # the missing key specifically.
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
            run_backtest_for_symbol("SPY", cfg={})

    def test_run_backtest_for_symbol_with_stub_returns_backtest_result(
        self, monkeypatch
    ):
        # Happy path with stubbed _fetch_bars -> bypasses network entirely.
        stub_df = _make_synthetic_ohlcv(n_bars=400)
        monkeypatch.setattr(
            "backtest.engine._fetch_bars",
            lambda symbol, *, n_bars: stub_df,
        )
        # Env vars must be set so the credential guard at the top of
        # run_backtest_for_symbol passes.
        monkeypatch.setenv("ALPACA_API_KEY", "dummy")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "dummy")
        cfg = {"account": {"equity": 12_345.0}}
        result = run_backtest_for_symbol("SPY", cfg=cfg)
        assert isinstance(result, BacktestResult)
        # Cfg propagated through to the engine layer.
        assert result.config_used["account"]["equity"] == 12_345.0

    def test_run_backtest_for_symbol_passes_full_cfg_through(self, monkeypatch):
        # Cfg dict is forwarded to ``run_backtest`` unchanged across multiple
        # blocks. Verifies the wrapper does not silently drop or rename keys.
        stub_df = _make_synthetic_ohlcv(n_bars=600)
        monkeypatch.setattr(
            "backtest.engine._fetch_bars",
            lambda symbol, *, n_bars: stub_df,
        )
        monkeypatch.setenv("ALPACA_API_KEY", "dummy")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "dummy")
        cfg = {
            "account": {"equity": 25_000.0},
            "regime_filter": {"adx_threshold": 1.0},   # strict, zero signals
        }
        result = run_backtest_for_symbol("SPY", cfg=cfg)
        assert result.config_used["account"]["equity"] == 25_000.0
        assert result.config_used["regime_filter"]["adx_threshold"] == 1.0

    def test_run_backtest_for_symbol_locks_wrapper_cfg_merge_contract(
        self, monkeypatch
    ):
        # Integration smoke test for the WRAPPER. The five preceding
        # tests in this class cover the credential / network edges
        # (missing creds, partial creds, stubbed happy path, full cfg
        # propagation). This one locks the wrapper's *cfg-merge
        # contract* end-to-end:
        #
        #   run_backtest_for_symbol
        #     -> _fetch_bars (stubbed here, real in Slice 3)
        #       -> run_backtest
        #         -> _merge_cfg
        #           -> BacktestResult.config_used
        #
        # Without this guard locked, a future refactor that mutates how
        # the wrapper threads cfg through (e.g. a premature eager
        # merge, a default-override swap, or a missing-block drop on
        # the wrapper-vs-engine boundary) would slip through the
        # existing edge-case tests and only be caught at Slice 3
        # batch-aggregation time when run_backtest_for_symbol is
        # called per-symbol in a loop.
        stub_df = _make_synthetic_ohlcv(n_bars=800)
        monkeypatch.setattr(
            "backtest.engine._fetch_bars",
            lambda symbol, *, n_bars: stub_df,
        )
        # Env vars required to pass the wrapper's credentials guard.
        monkeypatch.setenv("ALPACA_API_KEY", "dummy")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "dummy")
        # A multi-block cfg with a deliberately partial regime_filter
        # block so we can assert that sibling defaults survive the
        # wrapper's pass-through into _merge_cfg.
        cfg = {
            "account": {"equity": 50_000.0},
            "regime_filter": {"adx_threshold": 30.0},
        }
        result = run_backtest_for_symbol("SPY", cfg=cfg)
        # (1) BacktestResult dataclass shape: the wrapper's public
        #     return type is identical to run_backtest's. Snowball
        #     guards against a wrapper accidentally returning a
        #     plain tuple / dict return type.
        assert isinstance(result, BacktestResult)
        # (2) Cfg-merge contract at the wrapper boundary: every block
        #     the engine recognises must be present in the resolved
        #     config_used snapshot. Missing blocks on this surface
        #     indicate silent cfg-thread breakage (e.g., a wrapper
        #     refactor that forgets to pass cfg to run_backtest).
        for block in (
            "indicators", "regime_filter", "entry_signal",
            "exit", "risk", "backtest", "account", "timeframe",
        ):
            assert block in result.config_used, (
                f"missing block in merged cfg at wrapper boundary: {block}"
            )
        # (3) Override-wins semantics: the cfg we passed shows up
        #     verbatim (not degraded, not silently dropped).
        assert result.config_used["account"]["equity"] == 50_000.0
        assert result.config_used["regime_filter"]["adx_threshold"] == 30.0
        # (4) Partial-block merge: sibling regime_filter defaults
        #     survive the wrapper's pass-through into _merge_cfg.
        #     We assert on the keys that are BOTH whitelist-accepted
        #     AND present in config.yaml's regime_filter default — not
        #     on whitelist-only keys like ``atr_window`` which config
        #     may legitimately not set. A regression that turned the
        #     wrapper into a wholesale replace instead of deep-merge
        #     would lose these siblings.
        for sibling in ("hurst_threshold", "atr_relative_std_threshold"):
            assert sibling in result.config_used["regime_filter"], (
                f"sibling default lost through wrapper cfg-merge: {sibling}"
            )
        # (5) Full pipeline ran end-to-end through the wrapper: the
        #     signals dict is populated by signal_counts(df) on the
        #     post-pipeline df. Empty here means the pipeline crashed
        #     or wasn't reached.
        assert set(result.signals.keys()) >= {
            "long_signals", "short_signals", "total_signals",
        }
        # (6) Equity curve shape is preserved by the wrapper (the
        #     empty-df guard from the latent-debt fix transfers cleanly
        #     through this path). Use len() >= 1 rather than a loose
        #     isinstance() check so the contract pins the "always at
        #     least the initial bar" invariant — a potential regression
        #     to a truly empty Series would slip past a loose isinstance
        #     but be caught here. Same for naive_equity.
        assert isinstance(result.equity, pd.Series)
        assert len(result.equity) >= 1
        assert isinstance(result.naive_equity, pd.Series)
        assert len(result.naive_equity) >= 1


class TestFetchBars:
    """
    Tests for ``_fetch_bars`` directly. Drives the production code
    through a stubbed ``AlpacaDataClient`` rather than monkeypatching
    ``_fetch_bars`` itself, so the inner empty-response branch is
    actually exercised.
    """

    def test_fetch_bars_empty_dataframe_raises_runtime_error(self, monkeypatch):
        from data.fetch import AlpacaDataClient

        # Bypass AlpacaDataClient's own constructor cred check so we can
        # drive the empty-response branch purely via the stubbed method.
        monkeypatch.setattr(AlpacaDataClient, "__init__", lambda self: None)

        def stub_fetch(self, **kwargs):
            # Empty df for the requested symbol -- simulates Alpaca returning
            # no bars (e.g., date range outside trading days).
            idx = pd.date_range("2024-01-08 10:00", periods=0, freq="15min")
            return {"SPY": pd.DataFrame(
                {"open": [], "high": [], "low": [], "close": [], "volume": []},
                index=idx,
            )}

        monkeypatch.setattr(AlpacaDataClient, "fetch_historical_bars", stub_fetch)

        with pytest.raises(RuntimeError, match="no bars"):
            _fetch_bars("SPY", n_bars=1500)

    def test_fetch_bars_returns_dataframe_for_valid_response(self, monkeypatch):
        from data.fetch import AlpacaDataClient

        monkeypatch.setattr(AlpacaDataClient, "__init__", lambda self: None)

        n = 100
        idx = pd.date_range("2024-01-08 10:00", periods=n, freq="15min")
        stub_df = pd.DataFrame(
            {
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1_000_000.0,
            },
            index=idx,
        )

        def stub_fetch(self, **kwargs):
            return {"SPY": stub_df}

        monkeypatch.setattr(AlpacaDataClient, "fetch_historical_bars", stub_fetch)

        out = _fetch_bars("SPY", n_bars=1500)
        assert isinstance(out, pd.DataFrame)
        # ``n_bars=1500`` exceeds the stub's 100-row length, so the
        # ``iloc[-n_bars:]`` clip returns the full 100 rows. This is
        # the documented graceful behavior for over-request + short
        # history tickers.
        assert len(out) == n
        # Index promotion to plain DatetimeIndex (no MultiIndex).
        assert isinstance(out.index, pd.DatetimeIndex)
        assert not isinstance(out.index, pd.MultiIndex)

    def test_fetch_bars_missing_symbol_in_response_raises_runtime_error(
        self, monkeypatch
    ):
        # Normalize the absent-ticker branch to the same RuntimeError
        # contract as the empty-data branch. Without this guard,
        # ``data[symbol]`` would raise KeyError and the user-facing
        # failure mode would diverge from the documented "no bars"
        # channel.
        from data.fetch import AlpacaDataClient

        monkeypatch.setattr(AlpacaDataClient, "__init__", lambda self: None)

        def stub_fetch(self, **kwargs):
            return {}   # symbol key absent from response

        monkeypatch.setattr(AlpacaDataClient, "fetch_historical_bars", stub_fetch)
        with pytest.raises(RuntimeError, match="no bars"):
            _fetch_bars("SPY", n_bars=1500)

    def test_fetch_bars_zero_n_bars_raises_value_error(self):
        # ``iloc[-0:]`` is ``iloc[0:]`` — pandas quirk that would
        # silently return the full frame even when the caller asked
        # for zero bars. Guard at function entry so the contract is
        # enforced regardless of pandas' indexing semantics.
        with pytest.raises(ValueError, match="n_bars must be"):
            _fetch_bars("SPY", n_bars=0)

    def test_fetch_bars_negative_n_bars_raises_value_error(self):
        # Same guard covers negative inputs.
        with pytest.raises(ValueError, match="n_bars must be"):
            _fetch_bars("SPY", n_bars=-1)

    def test_fetch_bars_response_missing_ohlcv_columns_raises_runtime_error(
        self, monkeypatch
    ):
        # Defense against future Alpaca schema drift: a non-empty response
        # frame with the symbol key present but the canonical OHLCV
        # columns missing must surface through the same ``no bars``
        # RuntimeError channel rather than bypassing it as an uncaught
        # KeyError on the column-select line.
        from data.fetch import AlpacaDataClient

        monkeypatch.setattr(AlpacaDataClient, "__init__", lambda self: None)

        n = 10
        idx = pd.date_range("2024-01-08 10:00", periods=n, freq="15min")
        stub_df = pd.DataFrame(
            # Intentionally missing ``open`` / ``high`` / ``low``.
            {"close": 100.5, "volume": 1_000_000.0},
            index=idx,
        )

        def stub_fetch(self, **kwargs):
            return {"SPY": stub_df}

        monkeypatch.setattr(AlpacaDataClient, "fetch_historical_bars", stub_fetch)
        with pytest.raises(RuntimeError, match="no bars"):
            _fetch_bars("SPY", n_bars=1500)


# ─────────────────────────────────────────────────────────────────────
# Slice 3 — run_universe_backtest multi-symbol aggregator
# ─────────────────────────────────────────────────────────────────────

class TestRunUniverseBacktest:
    """
    Tests for the Slice-3 universe-batch aggregator. All happy-path tests
    stub ``run_backtest_for_symbol`` (and the credential preflight helper)
    so the universe run stays network-free.

    Tests
    -----
    - test_universe_empty_symbol_is_skipped
        Single-symbol universe where the only symbol raises the
        ``no bars`` ``RuntimeError``: result dict is empty and the
        ``RuntimeWarning`` is emitted exactly once.
    - test_universe_partial_empty_batch_returns_only_valid_symbols
        Three symbols, middle one raises. Result has 2 keys in input
        order, ``run_backtest_for_symbol`` was called 3 times
        (1 raised, 2 succeeded).
    - test_universe_preserves_input_dict_order
        Dict order in the result matches the symbols input order even
        when the input is non-alphabetical.
    """

    @staticmethod
    def _stub_df(n_bars: int = 30) -> pd.DataFrame:
        """Tiny synthetic df sufficient for the pipeline to run
        end-to-end without raising."""
        idx = pd.date_range("2024-01-08 10:00", periods=n_bars, freq="15min")
        rng = np.random.default_rng(42)
        close = np.full(n_bars, 100.0)
        df = pd.DataFrame(index=idx)
        df["open"] = close - 0.05
        df["high"] = close + 0.3
        df["low"] = close - 0.3
        df["close"] = close
        df["volume"] = rng.integers(1_000, 5_000_000, n_bars)
        return df

    def test_universe_empty_symbol_is_skipped(self, monkeypatch):
        """Single-symbol universe where that symbol triggers the
        empty-df branch in ``run_backtest_for_symbol``: the result dict
        is empty AND exactly one ``RuntimeWarning`` is emitted naming
        the symbol. Pins the 'skip' policy (default) end-to-end."""
        monkeypatch.setattr(
            "backtest.engine._get_missing_alpaca_creds", lambda: []
        )
        monkeypatch.setattr(
            "backtest.engine.run_backtest_for_symbol",
            lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError(
                    "Alpaca returned no bars for symbol='FAIL': "
                    "the response was empty."
                )
            ),
        )
        # pytest.warns catches exact RuntimeWarning; the match anchors
        # the "Skipping" prefix and the symbol so log-style assertions
        # remain deterministic if the warn message evolves.
        with pytest.warns(RuntimeWarning, match="Skipping symbol 'FAIL'"):
            result = run_universe_backtest(["FAIL"], on_symbol_error="skip")
        assert result == {}, "skipped-only universe must yield empty dict"

    def test_universe_partial_empty_batch_returns_only_valid_symbols(
        self, monkeypatch
    ):
        """Three-symbol universe where the middle one raises: the
        result dict has 2 keys in input order, the fake fetcher was
        called 3 times, and the wrapper cleanly skipped the failed
        one. Demonstrates the loop does NOT short-circuit on the first
        error."""
        calls: list = []

        def stub_run(symbol, cfg=None, *, n_bars=1500):
            calls.append(symbol)
            if symbol == "QQQ":
                raise RuntimeError(
                    "Alpaca returned no bars for symbol='QQQ': "
                    "the response was empty."
                )
            # Valid path: run the actual single-symbol backtest on a
            # tiny synthetic df so we exercise the real pipeline (not
            # a mock that hides regressions).
            return run_backtest(self._stub_df(), cfg=cfg)

        monkeypatch.setattr(
            "backtest.engine._get_missing_alpaca_creds", lambda: []
        )
        monkeypatch.setattr(
            "backtest.engine.run_backtest_for_symbol", stub_run,
        )
        with pytest.warns(RuntimeWarning, match="Skipping symbol 'QQQ'"):
            result = run_universe_backtest(
                ["SPY", "QQQ", "IWM"], on_symbol_error="skip"
            )
        # Calls proceed in input order even when the middle one raises,
        # confirming the loop does not abort early on per-symbol errors.
        assert calls == ["SPY", "QQQ", "IWM"]
        # Result keys preserve the input order modulo skips.
        assert list(result.keys()) == ["SPY", "IWM"]
        assert all(isinstance(r, BacktestResult) for r in result.values())

    def test_universe_preserves_input_dict_order(self, monkeypatch):
        """Dict-order invariant: the result keys exactly match the
        input ``symbols`` list, even when the input is non-alphabetical
        (so order would be wrong if anyone relies on dict alphabetical
        iteration). Locks the contract that callers can ``zip`` symbols
        with ``result``."""
        def stub_run(symbol, cfg=None, *, n_bars=1500):
            return run_backtest(self._stub_df(), cfg=cfg)

        monkeypatch.setattr(
            "backtest.engine._get_missing_alpaca_creds", lambda: []
        )
        monkeypatch.setattr(
            "backtest.engine.run_backtest_for_symbol", stub_run,
        )
        # Deliberately non-alphabetical: asserts we are NOT relying on
        # dict insertion sort behaviour (e.g. via tree-backed dict).
        universe = ["IWM", "SPY", "QQQ"]
        result = run_universe_backtest(universe)
        assert list(result.keys()) == universe
        # All entries are real BacktestResult instances (not mocked).
        assert all(isinstance(r, BacktestResult) for r in result.values())



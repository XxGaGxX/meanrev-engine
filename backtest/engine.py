"""
Backtest Engine — Mean Reversion Intraday (FASE 4, Slice 1)
============================================================

Single entry point that runs the FULL strategy pipeline against an
in-memory OHLCV ``DataFrame`` and returns a :class:`BacktestResult`
that bundles the final ``df``, the sized trade log, the equity curves
(both SIZED volatility-targeted and NAIVE equal-weight), and a
``calculate_all_metrics`` summary.

This module does NOT perform data fetching (that comes in Slice 2) and
does NOT aggregate across symbols (that comes in Slice 3). It is the
smallest vertical slice that takes a single-symbol ``df`` + config and
returns trades + equity + metrics — the same outcome that today lives
inline inside ``scripts/demo_e2e.py::run_pipeline``.

Determinism
-----------
Given the same ``df_raw`` and ``cfg`` the function produces bit-identical
``trades``, ``equity`` and ``metrics`` values on re-run. The deep copy in
``_merge_cfg`` prevents user overrides from mutating the global config
singleton returned by ``utils.config.config``.

Usage
-----
    from backtest.engine import run_backtest
    result = run_backtest(
        df_raw,
        cfg={
            "account": {"equity": 25_000.0},
            "regime_filter": {"adx_threshold": 30.0},   # permissive
        },
    )
    final = result.equity.iloc[-1]
    print(result.metrics["sharpe_ratio"], result.metrics["max_drawdown"])
"""

from __future__ import annotations

import copy
import math
import os
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import pandas as pd

from data.clean import clean_data, filter_session_hours
from data.fetch import AlpacaDataClient
from filters.regime import apply_regime_filter
from indicators.pipeline import build_all_indicators
from risk.sizing import (
    apply_position_sizing,
    build_equity_curve,
    build_pct_curve,
)
from signals.entry import generate_entry_signals, signal_counts
from signals.exit import simulate_all_trades
from utils.config import config
from utils.metrics import calculate_all_metrics


# Default annualized periods for 15-minute bars. 252 trading days × ~22
# 15-minute bars/day = ~5544 bars/year. Kept here as a single source of
# truth; demo_e2e.py uses the same value.
_DEFAULT_BARS_PER_YEAR = 5544
# Bars per regular-trading-hours day, derived from the annualized basis so
# the two numbers stay in sync if the timeframe ever switches (e.g., to
# 5-min bars where ``_DEFAULT_BARS_PER_YEAR`` would scale accordingly).
_BARS_PER_RTH_DAY = max(1, int(_DEFAULT_BARS_PER_YEAR / 252))
# Required OHLCV columns on the Alpaca response. Anything missing from
# this tuple is treated as "no usable data" by ``_fetch_bars`` so future
# API schema drift routes through the same ``match="no bars"``
# RuntimeError channel rather than an uncaught KeyError.
_REQ_OHLCV_COLS = ("open", "high", "low", "close", "volume")


@dataclass
class BacktestResult:
    """
    Aggregated output of a single ``run_backtest`` call.

    Attributes
    ----------
    df : pd.DataFrame
        Final DataFrame after `clean → indicators → regime → entry`.
        Carries `signal_long` / `signal_short` columns at this point.
    trades : pd.DataFrame
        Trade log returned by ``risk.sizing.apply_position_sizing``.
        Empty (with the ``TRADE_LOG_COLUMNS`` schema) when no signals
        fire on the input.
    equity : pd.Series
        Sized equity curve (volatility-targeted, dollar-P&L accurate).
        Falls back to equal-weight compounding when the trade log was
        never passed through position sizing.
    naive_equity : pd.Series
        Equal-weight naive curve (``build_pct_curve``). Always present
        so callers can compare the two side-by-side.
    metrics : dict
        Output of ``utils.metrics.calculate_all_metrics``. Sharpe / Sortino
        are only populated when ``cfg["timeframe"]["bars_per_year"]`` is
        set (defaults to 5544 for 15-min bars).
    config_used : dict
        Snapshot of the merged configuration actually applied during
        the run. Useful for reproducibility and audit trails.
    signals : dict
        Counts of long / short / total signals that fired on the input
        before exit simulation (``{"long_signals": int,
        "short_signals": int, "total_signals": int}``).
    """

    df: pd.DataFrame
    trades: pd.DataFrame
    equity: pd.Series
    naive_equity: pd.Series
    metrics: Dict[str, Any]
    config_used: Dict[str, Any]
    signals: Dict[str, int] = field(default_factory=dict)


def _default_cfg() -> Dict[str, Any]:
    """
    Snapshot of the global ``config.yaml`` defaults relevant to a single
    engine call. Each block is a fresh shallow copy so consumer-side
    mutation in ``_merge_cfg`` cannot propagate back to the singleton.
    """
    raw = config.raw
    regime_keep = {
        "adx_threshold", "hurst_threshold",
        "atr_relative_std_threshold", "atr_window",
    }
    return {
        "indicators": dict(raw.get("indicators") or {}),
        "regime_filter": {
            k: v for k, v in (raw.get("regime_filter") or {}).items()
            if k in regime_keep
        },
        "entry_signal": dict(raw.get("entry_signal") or {}),
        "exit": dict(raw.get("exit") or {}),
        "risk": dict(raw.get("risk") or {}),
        "backtest": dict(raw.get("backtest") or {}),
        "account": {"equity": float(config.get("account.equity", 10_000))},
        "timeframe": {
            "skip_first_minutes": int(config.get("timeframe.skip_first_minutes", 30)),
            "skip_last_minutes": int(config.get("timeframe.skip_last_minutes", 30)),
            "market_open": config.get("timeframe.market_open", "09:30"),
            "market_close": config.get("timeframe.market_close", "16:00"),
            "bars_per_year": config.get("timeframe.bars_per_year", _DEFAULT_BARS_PER_YEAR),
        },
    }


def _merge_cfg(user_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deep-merge ``user_cfg`` over :func:`_default_cfg` so global defaults
    are preserved but user-supplied keys take precedence. Returns a fresh
    dict so the singleton config is never mutated.

    Raises
    ------
    ValueError
        If ``user_cfg`` contains any top-level block that is not in the
        default config. Catches typos (``rejime_filter`` for
        ``regime_filter``) and unsolicited blocks early. Within a
        validated block, unknown leaf keys are still tolerated — they
        propagate to the downstream function which will TypeError on
        truly unrecognized kwargs.
    """
    base = copy.deepcopy(_default_cfg())
    if not user_cfg:
        return base
    valid_blocks = set(base.keys())
    for k, v in user_cfg.items():
        if k not in valid_blocks:
            raise ValueError(
                f"Unknown engine cfg block: {k!r}. "
                f"Valid blocks: {sorted(valid_blocks)}"
            )
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    return base


def run_backtest(
    df_raw: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> BacktestResult:
    """
    Run the full mean-reversion pipeline against a single-symbol OHLCV df.

    Pipeline order is the canonical one used by ``scripts/demo_e2e.py``:
    *clean → indicators → regime → entry → exit → risk-based sizing →
    equity curves → metrics*. The function performs no I/O — callers in
    higher slices are responsible for sourcing the input DataFrame.

    Parameters
    ----------
    df_raw : pd.DataFrame
        In-memory OHLCV bars. Required columns: ``open``, ``high``,
        ``low``, ``close``, ``volume``. Must be indexed by a
        ``DatetimeIndex`` for ``filter_session_hours`` to apply its
        day-of-week and time-of-day masks.
    cfg : dict, optional
        Per-block overrides; deep-merged over :func:`_default_cfg`.
        Recognized top-level blocks:

        - ``indicators``       (forwarded to ``build_all_indicators``)
        - ``regime_filter``    (forwarded to ``apply_regime_filter``)
        - ``entry_signal``     (forwarded to ``generate_entry_signals``)
        - ``exit``             (forwarded to ``simulate_all_trades``)
        - ``risk``             (forwarded to ``apply_position_sizing``)
        - ``backtest``         (commission / slippage for sizing)
        - ``account``          (initial equity; default 10 000)
        - ``timeframe``        (session bounds, bars-per-year)

        Pass ``cfg={}`` to take all defaults; pass ``None`` to do the same.

    Returns
    -------
    BacktestResult
        Dataclass bundling ``df`` (post-pipeline), ``trades`` (post-sizing),
        both equity curves, the metrics dict, the merged config and the
        signal counts. Always returns a fully-populated result — even when
        no signals fire (in which case ``trades`` is empty and ``equity``
        is a single-point series anchored at the initial equity).

    Raises
    ------
    ValueError
        If ``df_raw`` is missing the required OHLCV columns or the index
        is not a ``DatetimeIndex``.
    """
    cfg_merged = _merge_cfg(cfg)
    tf = cfg_merged["timeframe"]
    initial_equity = float(cfg_merged["account"]["equity"])

    # --- 1. Clean + filter session hours ---
    df = clean_data(df_raw)
    df = filter_session_hours(
        df,
        skip_first_minutes=tf["skip_first_minutes"],
        skip_last_minutes=tf["skip_last_minutes"],
        market_open=tf["market_open"],
        market_close=tf["market_close"],
    )

    # --- 2. Indicators ---
    df = build_all_indicators(df, cfg=cfg_merged["indicators"])

    # --- 3. Regime filter ---
    df = apply_regime_filter(df, **cfg_merged["regime_filter"])

    # --- 4. Entry signals ---
    df = generate_entry_signals(df, cfg=cfg_merged["entry_signal"])
    sig_counts = signal_counts(df)

    # --- 5. Exit simulation ---
    trades = simulate_all_trades(df, cfg=cfg_merged["exit"])

    # --- 6. Position sizing ---
    exit_cfg = cfg_merged["exit"]
    risk_cfg = {
        "risk_per_trade_pct": cfg_merged["risk"].get("risk_per_trade_pct", 1.0),
        "max_risk_per_trade_pct": cfg_merged["risk"].get("max_risk_per_trade_pct", 2.0),
        "atr_multiplier": exit_cfg.get("atr_multiplier", 1.5),
        "allow_fractional": True,
        "max_position_pct": 1.0,
        "kelly_fraction": cfg_merged["risk"].get("kelly_fraction", 0.0),
        "commission_per_side": cfg_merged["backtest"].get("commission_per_side", 0.0),
        "slippage_pct": cfg_merged["backtest"].get("slippage_pct", 0.0005),
    }
    trades = apply_position_sizing(
        trades, df, initial_equity=initial_equity, risk_cfg=risk_cfg
    )

    # --- 7. Equity curves ---
    equity = build_equity_curve(trades, df, initial_equity=initial_equity)
    naive = build_pct_curve(trades, df, initial_equity=initial_equity)

    # --- 8. Metrics ---
    # Prefer the cost-aware column when sizing actually produced it,
    # otherwise fall back to the exit-derived raw percentage so the
    # engine still returns a non-trivial metrics dict for un-sized logs.
    if not trades.empty and "pnl_pct_slip" in trades.columns \
            and trades["pnl_pct_slip"].notna().any():
        trade_returns = trades["pnl_pct_slip"].dropna()
    elif not trades.empty and "pnl_pct" in trades.columns:
        trade_returns = trades["pnl_pct"]
    else:
        trade_returns = pd.Series(dtype=float)
    periods_per_year = cfg_merged["timeframe"].get("bars_per_year")
    metrics = calculate_all_metrics(
        trade_returns, equity, periods_per_year=periods_per_year
    )

    return BacktestResult(
        df=df,
        trades=trades,
        equity=equity,
        naive_equity=naive,
        metrics=metrics,
        config_used=cfg_merged,
        signals=sig_counts,
    )


def _get_missing_alpaca_creds() -> list[str]:
    """Return the list of Alpaca env-var names whose values are unset or empty."""
    missing: list[str] = []
    for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        if not (os.getenv(name) or "").strip():
            missing.append(name)
    return missing


def _fetch_bars(symbol: str, *, n_bars: int = 1500) -> pd.DataFrame:
    """
    Fetch OHLCV bars for a single symbol from Alpaca and return a flat
    ``DataFrame`` ready to feed into :func:`run_backtest`.

    Parameters
    ----------
    symbol : str
        Ticker, e.g. ``"SPY"``.
    n_bars : int, keyword-only
        Strictly positive (>0) target number of 15-minute bars
        requested. Translated into a trailing calendar-day window
        (assumes ``_BARS_PER_RTH_DAY`` fifteen-minute bars per
        regular-trading-hours day and 1.5x calendar-day padding for
        weekends and U.S. holidays), then trimmed to the last ``n_bars``
        rows so the engine sees exactly the requested size. Default
        ``1500`` matches the historical demo script's request and
        resolves to ~103 calendar days of over-fetch (well above the
        requested count even after holiday blockages). End is anchored
        at yesterday in NY time so intraday partial bars are not
        included.

    Returns
    -------
    pd.DataFrame
        Flat OHLCV frame with a plain ``DatetimeIndex`` (no ``symbol``
        MultiIndex level), columns ``['open', 'high', 'low', 'close',
        'volume']`` ready for ``clean_data`` and the rest of the pipeline.

    Raises
    ------
    RuntimeError
        If Alpaca returns zero bars for ``symbol`` (date range outside
        trading days, unknown symbol, missing key in response dict, etc.).
        All "no usable data" paths converge on the same ``no bars``
        message so callers have a single diagnostic handle.
    ValueError
        If ``n_bars`` is not strictly positive. Propagated from
        ``AlpacaDataClient.__init__`` when credentials are missing —
        the wrapper ``run_backtest_for_symbol`` performs a friendlier
        preflight check before reaching here.
    """
    if n_bars <= 0:
        raise ValueError(
            f"n_bars must be strictly positive (got {n_bars})."
        )
    # Translate ``n_bars`` fifteen-minute bars into a calendar-day window.
    # Use the trading-day math (1 bar per RTH-day slot × 1.5x calendar-day
    # padding for weekends and U.S. holidays) so a 1500-bar request
    # reliably returns more than the requested volume. Anchor to
    # America/New_York so the window is identical regardless of the
    # host's timezone — Alpaca's data is NY-aligned and downstream
    # ``filter_session_hours`` keys off NY-local time via
    # ``data.fetch._to_ny_tz``.
    n_trading_days = max(1, math.ceil(n_bars / _BARS_PER_RTH_DAY))
    calendar_days = math.ceil(n_trading_days * 1.5)
    now_ny = pd.Timestamp.now(tz="America/New_York")
    end = (now_ny - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start = (now_ny - pd.Timedelta(days=calendar_days)).strftime("%Y-%m-%d")
    client = AlpacaDataClient()
    data = client.fetch_historical_bars(
        symbols=[symbol], timeframe="15Min", start=start, end=end,
    )
    # Normalize two flavors of "no data" to the same RuntimeError contract:
    # the symbol key may be absent from the response dict (truly invalid
    # ticker / API quirk) or it may map to a zero-row frame (empty-check
    # below). Both go through the ``match="no bars"`` channel so callers
    # have one single diagnostic handle instead of guessing between
    # KeyError and RuntimeError.
    if symbol not in data:
        raise RuntimeError(
            f"Alpaca returned no bars for symbol={symbol!r}: "
            f"the response did not include the requested ticker."
        )
    df = data[symbol]
    # Defense against a future Alpaca response shape where the symbol key
    # is present and the frame is non-empty but the canonical OHLCV
    # columns are missing. Without this check, the column-select below
    # would surface as an uncaught KeyError and bypass the ``no bars``
    # diagnostic channel that the rest of ``_fetch_bars`` funnels
    # through. Keeping all "no usable data" flavors under one regex
    # makes log triage and caller-side remediation uniform.
    missing_cols = [c for c in _REQ_OHLCV_COLS if c not in df.columns]
    if missing_cols:
        raise RuntimeError(
            f"Alpaca returned no bars for symbol={symbol!r}: "
            f"the response is missing required OHLCV columns {missing_cols}."
        )
    # ``AlpacaDataClient.fetch_historical_bars`` returns a MultiIndex df
    # keyed by ``symbol`` — flatten it so downstream indexing, selection
    # and timestamp alignment work uniformly with synthetic test data.
    if isinstance(df.index, pd.MultiIndex):
        df = df.droplevel("symbol")
    df = df[["open", "high", "low", "close", "volume"]]

    if df.empty:
        raise RuntimeError(
            f"Alpaca returned no bars for symbol={symbol!r}: "
            f"the response was empty. Check the ticker is valid and the "
            f"date range covers trading days (or lower the requested bar count)."
        )
    # Trim to ``n_bars`` rows so the engine sees exactly the requested
    # size. The over-fetch from ``calendar_days`` padding exists for
    # SAFETY against holiday/weekend gaps, not data fidelity — we
    # always deliver exactly what was asked for. ``iloc[-n_bars:]``
    # silently returns the full frame if ``len(df) < n_bars`` (short
    # history tickers), so no additional guard is needed.
    df = df.iloc[-n_bars:]
    return df


def run_backtest_for_symbol(
    symbol: str,
    cfg: Optional[Dict[str, Any]] = None,
    *,
    n_bars: int = 1500,
) -> BacktestResult:
    """
    End-to-end single-symbol wrapper: fetch historical OHLCV bars from
    Alpaca, then delegate to :func:`run_backtest` for the in-memory
    pipeline. Network and credentials are validated at the wrapper
    boundary so failures happen with a clear, actionable message instead
    of surfacing at the first HTTP call.

    Parameters
    ----------
    symbol : str
        Ticker to fetch and backtest, e.g. ``"SPY"``.
    cfg : dict, optional
        Forwarded verbatim to :func:`run_backtest`. Pass per-block
        overrides (``regime_filter``, ``entry_signal``, ``account``,
        etc.) just like the in-memory path.
    n_bars : int, keyword-only
        Forwarded to :func:`_fetch_bars`. Default ``1500`` matches the
        demo. Multi-symbol slicing is not yet supported — that lands in
        Slice 3.

    Returns
    -------
    BacktestResult
        Same dataclass as :func:`run_backtest`. ``signals``, ``trades``,
        ``equity`` and ``metrics`` are populated from the fetched bars.

    Raises
    ------
    RuntimeError
        If ``ALPACA_API_KEY`` or ``ALPACA_SECRET_KEY`` is unset/empty,
        or if Alpaca returns zero bars for ``symbol``. Both messages list
        the missing piece so callers can self-correct without grep'ing
        the source.
    """
    missing = _get_missing_alpaca_creds()
    if missing:
        raise RuntimeError(
            f"Alpaca credentials missing: {missing}. "
            f"Set these environment variables (or add them to .env) "
            f"before calling run_backtest_for_symbol."
        )

    df = _fetch_bars(symbol, n_bars=n_bars)
    return run_backtest(df, cfg=cfg)


def run_universe_backtest(
    symbols: List[str],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    n_bars: int = 1500,
    on_symbol_error: Literal["skip", "raise"] = "skip",
) -> Dict[str, BacktestResult]:
    """
    Slice-3 multi-symbol aggregator: iterate ``run_backtest_for_symbol``
    across an arbitrary universe and return the per-symbol results keyed
    by ticker. Credential preflight happens ONCE before the first fetch
    so a missing key fails fast on the whole batch rather than failing
    per-symbol inside the loop.

    Important
    ---------
    This is dict-level aggregation only. It does NOT combine equity
    curves or apply portfolio-level constraints like
    ``max_open_positions``. Portfolio semantics live in Slice 4 — use
    this helper to measure per-symbol performance on a shared config,
    then reach for `run_portfolio_backtest` once Slice 4 lands for
    combined-equity + cross-symbol cap simulation.

    Parameters
    ----------
    symbols : list of str
        Tickers to fetch and backtest. Insertion order is preserved in
        the returned dict (Python ≥ 3.7).
    cfg : dict, optional
        Forwarded verbatim to each ``run_backtest_for_symbol`` call.
        A single shared config is applied across the universe in this
        iteration (per-symbol overrides are deferred to Slice 4).
    n_bars : int, keyword-only
        Forwarded to each ``run_backtest_for_symbol`` call. Default
        ``1500`` matches the demo.
    on_symbol_error : {"skip", "raise"}, keyword-only, default ``"skip"``
        Policy when an individual symbol's fetch layer raises an
        error. ``"skip"`` emits a ``RuntimeWarning`` and continues
        with the remaining symbols; ``"raise"`` propagates the first
        such error immediately. The catch covers ``(RuntimeError,
        OSError)`` so transient network failures (``ConnectionError``,
        ``RequestException`` from the underlying ``alpaca-py`` SDK,
        ``KeyError`` from response-parsing edge cases) honor the
        policy too — ``"skip"`` will not abort on a single flaky
        fetch. ``ValueError`` from `_merge_cfg` (malformed cfg blocks)
        is NOT caught in either mode — bad config is fatal for the
        whole batch because all symbols would hit the same error.

    Returns
    -------
    dict[str, BacktestResult]
        Mapping ticker → :class:`BacktestResult`. Insertion order
        matches the input ``symbols`` list (modulo skips). Empty dict
        when every symbol was skipped/failed; the function never
        raises on the all-skipped path with ``on_symbol_error="skip"``.

    Raises
    ------
    RuntimeError
        If Alpaca credentials are missing (preflighted once before the
        loop). With ``on_symbol_error="raise"`` this is also raised on
        the first per-symbol fetch failure.
    """
    # Single preflight — credentials fail fast on the whole batch
    # rather than redundantly per symbol. Reuses the helper exposed
    # by ``run_backtest_for_symbol`` so the message stays in sync.
    missing = _get_missing_alpaca_creds()
    if missing:
        raise RuntimeError(
            f"Alpaca credentials missing: {missing}. "
            f"Set these environment variables (or add them to .env) "
            f"before calling run_universe_backtest."
        )

    out: Dict[str, BacktestResult] = {}
    for symbol in symbols:
        try:
            out[symbol] = run_backtest_for_symbol(
                symbol, cfg=cfg, n_bars=n_bars,
            )
        except (RuntimeError, OSError) as e:
            if on_symbol_error == "skip":
                # Use RuntimeWarning so pytest.warns(RuntimeWarning)
                # can pin the policy exactly without sweeping up unrelated
                # DeprecationWarnings or ImportWarnings. The message
                # keeps the symbol + the underlying RuntimeError text
                # so log grep remains deterministic.
                warnings.warn(
                    f"Skipping symbol {symbol!r}: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            raise
    return out

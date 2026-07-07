"""
Position Sizing Module — Mean Reversion Intraday
================================================
Implements risk-based share sizing so that the equity curve reflects real
dollar P&L instead of equal-weight position returns.

Core formula (volatility-targeted, 1% rule):
    StopDistance = ATR × atr_multiplier
    RiskDollar   = Equity × (risk_per_trade_pct / 100)
    Shares       = RiskDollar / StopDistance

The underlying `signals/exit.py` is kept pure: it produces a trade log with
percentage P&L only. This module wraps that log, computing actual share
counts at entry time and dollar P&L at exit time, returning an enriched
DataFrame plus a chronological equity curve.

Usage:
    from risk.sizing import apply_position_sizing, calculate_shares

    sized = apply_position_sizing(
        trades=trades,
        df=df_clean,
        initial_equity=10_000.0,
        risk_cfg={
            "risk_per_trade_pct": 1.0,
            "max_risk_per_trade_pct": 2.0,
            "atr_multiplier": 1.5,
            "allow_fractional": True,
            "kelly_fraction": 0.25,    # 0 = disable Kelly; else use this fraction
        },
    )
    equity = sized["equity_after"].tolist()
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


_REQUIRED_TRADE_COLS = {
    "entry_idx", "exit_idx", "entry_price", "exit_price",
    "direction", "pnl_pct",
}


# ─────────────────────────────────────────────────────────────────────
# 1. Core sizing formula
# ─────────────────────────────────────────────────────────────────────

def calculate_shares(
    equity: float,
    risk_pct: float,
    atr: float,
    multiplier: float,
    price: float,
    allow_fractional: bool = True,
    max_position_pct: float = 1.0,
) -> float:
    """
    Compute the number of shares to buy for one trade.

    Parameters
    ----------
    equity : float
        Account equity available at entry, in dollars.
    risk_pct : float
        Fraction of equity to risk as a percentage (e.g. 1.0 for 1%).
    atr : float
        ATR value at entry, in price units.
    multiplier : float
        Stop-loss distance = atr × multiplier (e.g. 1.5).
    price : float
        Entry price per share.
    allow_fractional : bool
        True → round to 4 decimals (Alpaca fractional);
        False → floor to whole shares.
    max_position_pct : float
        Hard cap on notional size as fraction of equity (1.0 = no leverage).

    Returns
    -------
    float
        Number of shares (0 if inputs are invalid or unaffordable).
    """
    # Guard rails — degraded but valid behavior on bad input
    if not np.isfinite(equity) or equity <= 0:
        return 0.0
    if not np.isfinite(risk_pct) or risk_pct <= 0:
        return 0.0
    if not np.isfinite(atr) or atr <= 0:
        return 0.0
    if not np.isfinite(multiplier) or multiplier <= 0:
        return 0.0
    if not np.isfinite(price) or price <= 0:
        return 0.0
    if not np.isfinite(max_position_pct) or max_position_pct <= 0:
        return 0.0

    stop_distance = atr * multiplier
    risk_dollar = equity * (risk_pct / 100.0)
    raw_shares = risk_dollar / stop_distance

    # Cap by available equity (no leverage)
    max_shares_by_equity = (equity * max_position_pct) / price
    shares = min(raw_shares, max_shares_by_equity)

    if not allow_fractional:
        shares = math.floor(shares)
    else:
        # Alpaca allows up to 9 decimal places; 4 is plenty for equities
        shares = round(shares, 4)

    return float(shares) if shares > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────
# 2. Kelly fraction adjustment (optional cap on risk_pct)
# ─────────────────────────────────────────────────────────────────────

def kelly_risk_pct(
    trade_returns: pd.Series,
    fraction: float = 0.25,
    risk_cap_pct: float = 2.0,
) -> float:
    """
    Compute a Kelly-fractioned risk-per-trade percentage from observed
    trade returns.

    Returns ``fraction × kelly_pct`` clamped to ``[0, risk_cap_pct]``.

    Parameters
    ----------
    trade_returns : pd.Series
        Per-trade fraction returns (e.g. 0.01 = +1%).
    fraction : float
        Kelly fraction (1/4 or 1/2 Kelly recommended).
    risk_cap_pct : float
        Hard ceiling on the returned percentage. Caps Kelly to a sane
        level even when the data suggests betting the farm.

    Returns
    -------
    float
        Risk percentage in [0, risk_cap_pct]. Returns 0.0 if there are
        no losses or insufficient data.
    """
    if trade_returns is None or len(trade_returns) == 0:
        return 0.0
    if fraction <= 0 or risk_cap_pct <= 0:
        return 0.0

    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]
    if len(wins) == 0 or len(losses) == 0:
        return 0.0

    win_rate_f = len(wins) / len(trade_returns)
    avg_win = float(wins.mean())
    avg_loss = float(abs(losses.mean()))
    if avg_loss == 0:
        return 0.0

    b = avg_win / avg_loss
    kelly_pct = (win_rate_f - ((1.0 - win_rate_f) / b)) * 100.0  # percent
    kelly_pct = max(0.0, kelly_pct * fraction)
    return float(min(kelly_pct, risk_cap_pct))


# ─────────────────────────────────────────────────────────────────────
# 3. Apply sizing over the whole trade log
# ─────────────────────────────────────────────────────────────────────

def apply_position_sizing(
    trades: pd.DataFrame,
    df: pd.DataFrame,
    initial_equity: float = 10_000.0,
    risk_cfg: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Enrich a trade log with risk-based share counts and dollar P&L.

    Iterates trades chronologically; equity is updated after every trade
    so subsequent positions reflect the running account balance. The
    ATR used for sizing is taken from ``df['atr'].iloc[entry_idx]`` at
    the entry bar.

    Parameters
    ----------
    trades : pd.DataFrame
        Output of ``signals.exit.simulate_all_trades``. Must contain
        the columns ``entry_idx``, ``exit_idx``, ``entry_price``,
        ``exit_price``, ``direction`` and ``pnl_pct``.
    df : pd.DataFrame
        Cleaned + indicators DataFrame providing ``df['atr']``.
    initial_equity : float
        Starting equity in dollars.
    risk_cfg : dict, optional
        Risk configuration overrides:

        - ``risk_per_trade_pct`` (float, default 1.0)
        - ``max_risk_per_trade_pct`` (float, default 2.0)
        - ``atr_multiplier`` (float, default 1.5)
        - ``allow_fractional`` (bool, default True)
        - ``max_position_pct`` (float, default 1.0)
        - ``kelly_fraction`` (float, default 0.0; 0 disables Kelly)
        - ``commission_per_side`` (float, default 0.0)
        - ``slippage_pct`` (float, default 0.0)

    Returns
    -------
    pd.DataFrame
        Copy of ``trades`` with these extra columns appended:
        shares, position_value, risk_dollar, pnl_dollar, commission_cost,
        equity_after, kelly_risk_pct, pnl_pct_slip.

        The original ``pnl_pct`` column is left untouched (it still
        represents the exit-derived return before transaction costs);
        ``pnl_pct_slip`` carries the same value adjusted for entry/exit
        slippage so callers can choose between clean returns and
        cost-aware returns without re-deriving them.
    """
    risk_cfg = risk_cfg or {}

    # Use transaction cost config from backtest block when caller
    # doesn't override
    commission_per_side = float(risk_cfg.get(
        "commission_per_side", 0.0))
    slippage_pct = float(risk_cfg.get("slippage_pct", 0.0))

    out = trades.copy()

    if out.empty:
        for col in (
            "shares", "position_value", "risk_dollar",
            "pnl_dollar", "commission_cost", "equity_after",
            "kelly_risk_pct", "pnl_pct_slip",
        ):
            out[col] = pd.Series(dtype=float)
        return out

    # Reset index so positional .iloc[i] below is unambiguous
    out = out.reset_index(drop=True)

    n = len(out)
    shares_arr = np.zeros(n, dtype=float)
    pos_val_arr = np.zeros(n, dtype=float)
    risk_dol_arr = np.zeros(n, dtype=float)
    pnl_dol_arr = np.zeros(n, dtype=float)
    comm_arr = np.zeros(n, dtype=float)
    eq_after_arr = np.zeros(n, dtype=float)
    kelly_arr = np.full(n, np.nan, dtype=float)

    pnl_pct_slip_arr = np.full(n, np.nan, dtype=float)

    base_risk_pct = float(risk_cfg.get("risk_per_trade_pct", 1.0))
    max_risk_pct = float(risk_cfg.get("max_risk_per_trade_pct", 2.0))
    atr_multiplier = float(risk_cfg.get("atr_multiplier", 1.5))
    allow_fractional = bool(risk_cfg.get("allow_fractional", True))
    max_position_pct = float(risk_cfg.get("max_position_pct", 1.0))
    kelly_fraction = float(risk_cfg.get("kelly_fraction", 0.0))
    kelly_min_trades = int(risk_cfg.get("kelly_min_trades", 5))
    halt_after_wipe = bool(risk_cfg.get("halt_after_wipe", True))

    running_equity = float(initial_equity)
    wiped = False  # set to True once equity hits 0; tail trades get 0 shares

    # Iterate chronologically; build returns-to-date for Kelly estimate
    completed_returns: List[float] = []

    for i in range(n):
        row = out.iloc[i]
        entry_idx = int(row["entry_idx"])
        entry_price = float(row["entry_price"])
        exit_price = float(row["exit_price"])
        direction = float(row["direction"])
        pnl_pct_raw = float(row["pnl_pct"])

        # ATR at entry — the same value used by simulate_exit to compute SL
        atr_at_entry = float(df["atr"].iloc[entry_idx])
        if not np.isfinite(atr_at_entry) or atr_at_entry <= 0:
            atr_at_entry = 1e-8  # synthetic floor; shares will collapse via guards

        # Optional Kelly override on the per-trade risk %
        effective_risk_pct = base_risk_pct
        kelly_arr[i] = np.nan
        if kelly_fraction > 0.0 and len(completed_returns) >= kelly_min_trades:
            kelly_pct = kelly_risk_pct(
                pd.Series(completed_returns),
                fraction=kelly_fraction,
                risk_cap_pct=max_risk_pct,
            )
            kelly_arr[i] = kelly_pct
            if kelly_pct > 0.0:
                effective_risk_pct = min(kelly_pct, base_risk_pct)

        # Hard cap on per-trade risk (max_risk_pct is the absolute ceiling,
        # not the wider-of-the-two: a user setting max=0.5 and base=1.0 gets
        # the cap honored, otherwise it would silently widen).
        effective_risk_pct = float(np.clip(effective_risk_pct, 0.0, max_risk_pct))

        # Drop tail trades once the account is wiped
        if wiped:
            shares = 0.0
            effective_entry = entry_price
            effective_exit = exit_price
            pnl_pct_with_slip = pnl_pct_raw
            position_value = 0.0
            pnl_dollar = 0.0
            commission_cost = 0.0
            equity_after = running_equity
        else:
            shares = calculate_shares(
                equity=running_equity,
                risk_pct=effective_risk_pct,
                atr=atr_at_entry,
                multiplier=atr_multiplier,
                price=entry_price,
                allow_fractional=allow_fractional,
                max_position_pct=max_position_pct,
            )

            # Apply slippage on entry price (adverse direction)
            slip = slippage_pct
            effective_entry = entry_price * (1.0 + slip * direction)
            effective_exit = exit_price * (1.0 - slip * direction)
            if effective_entry > 0:
                pnl_pct_with_slip = (
                    direction * (effective_exit - effective_entry) / effective_entry
                )
            else:
                pnl_pct_with_slip = pnl_pct_raw

            position_value = shares * effective_entry
            pnl_dollar = shares * direction * (effective_exit - effective_entry)

            # Commission: per-side, applied on entry + exit notionals
            commission_cost = (
                shares * effective_entry * commission_per_side
                + shares * effective_exit * commission_per_side
            )

            # Floor equity_after at zero so the curve doesn't go negative in
            # worst-case backtests; mark the account as wiped so subsequent
            # trades get 0 shares instead of phantom positions.
            equity_after = max(0.0, running_equity + pnl_dollar - commission_cost)
            if equity_after <= 0.0 and halt_after_wipe:
                wiped = True

        shares_arr[i] = shares
        pos_val_arr[i] = position_value
        risk_dol_arr[i] = running_equity * (effective_risk_pct / 100.0)
        pnl_dol_arr[i] = pnl_dollar - commission_cost
        comm_arr[i] = commission_cost
        eq_after_arr[i] = equity_after
        pnl_pct_slip_arr[i] = pnl_pct_with_slip

        running_equity = equity_after
        completed_returns.append(pnl_pct_with_slip)

    out["shares"] = shares_arr
    out["position_value"] = pos_val_arr
    out["risk_dollar"] = risk_dol_arr
    out["pnl_dollar"] = pnl_dol_arr
    out["commission_cost"] = comm_arr
    out["equity_after"] = eq_after_arr
    out["kelly_risk_pct"] = kelly_arr
    # Cost-aware return kept separate from exit-derived pnl_pct so callers
    # are not surprised by an in-place mutation of the latter.
    out["pnl_pct_slip"] = pnl_pct_slip_arr

    return out


# ─────────────────────────────────────────────────────────────────────
# 4. Equity curve convenience builder
# ─────────────────────────────────────────────────────────────────────

def build_equity_curve(
    trades: pd.DataFrame,
    df: pd.DataFrame,
    initial_equity: float = 10_000.0,
) -> pd.Series:
    """
    Build the equity curve from a trade log.

    If ``trades`` carries an ``equity_after`` column (i.e. it has been
    processed by :func:`apply_position_sizing`), that column drives the
    curve so dollar P&L is reflected faithfully. Otherwise the curve
    falls back to multiplying the initial equity by ``(1 + pnl_pct)``
    across trades — convenient for raw exit simulations but somewhat
    misleading because it assumes equal-weight positions.

    Returns
    -------
    pd.Series
        Indexed by the exit timestamp of each trade (plus one initial bar),
        values in dollars.

        If ``df`` is completely empty (the indicator pipeline emitted
        zero rows), returns a 1-element Series anchored at ``pd.NaT``
        containing ``initial_equity``. The single-element shape keeps
        downstream ``utils/metrics.calculate_all_metrics`` honest:
        ``max_drawdown`` on a 1-element Series resolves to 0.0 (no
        drawdown observed) instead of returning NaN as it would on a
        truly empty Series. A fully-empty Series would also defeat the
        contract documented above that callers can ``iloc[-1]`` the
        initial bar.
    """
    # Defense-in-depth guard: the very first line of the body does
    # ``df.index[0]`` which raises IndexError on an empty DatetimeIndex.
    # Pre-fix this path crashed when the entire input was zero-volume or
    # otherwise filtered out by ``data.clean.clean_data``. Returning a
    # 1-element NaT Series preserves the dataclass contract that
    # ``result.equity`` always has ≥1 element, so downstream metrics and
    # callers can rely on it without special-casing.
    if df.empty:
        return pd.Series(
            [float(initial_equity)],
            index=pd.DatetimeIndex([pd.NaT]),
            name="equity",
        )
    timestamps: List[pd.Timestamp] = [df.index[0]]
    equity: List[float] = [float(initial_equity)]

    if trades is None or trades.empty:
        return pd.Series(equity, index=timestamps, name="equity")

    use_dollar_pnl = "equity_after" in trades.columns
    running = float(initial_equity)
    for _, t in trades.iterrows():
        idx_pos = min(int(t["exit_idx"]), len(df) - 1)
        timestamps.append(df.index[idx_pos])
        if use_dollar_pnl:
            running = float(t["equity_after"])
        else:
            running = running * (1.0 + float(t["pnl_pct"]))
        equity.append(running)

    return pd.Series(equity, index=pd.DatetimeIndex(timestamps), name="equity")


def build_pct_curve(
    trades: pd.DataFrame,
    df: pd.DataFrame,
    initial_equity: float = 10_000.0,
) -> pd.Series:
    """
    Legacy equal-weight naive curve: compound ``(1 + pnl_pct)`` across every
    trade, ignoring share counts and ATR volatility targeting.

    **Comparison helper — do NOT use this for risk decisions.** The naive
    curve hides the effect of FASE 3: every trade is implicitly treated
    as a full-equity position so large losses compound proportionally
    onto a smaller base. It exists only to make the divergence with
    :func:`build_equity_curve` (when ``equity_after`` is present) visible
    in plots such as the one in ``scripts/demo_e2e.py`` and the
    regression smoke test in ``scripts/visual_check_sizing.py``.

    Returns
    -------
    pd.Series
        Indexed by ``df.index[0]`` followed by the exit timestamp of each
        trade. Values are dollar equity, starting at ``initial_equity``.

        If ``df`` is completely empty, returns a 1-element Series
        anchored at ``pd.NaT`` containing ``initial_equity``. See
        :func:`build_equity_curve` for the contract rationale — the
        NaT-anchored single-element shape is mirrored here so Sized vs
        Naive overlays plot on the same x-axis baseline in the
        ``visual_check_sizing`` smoke test even when the engine fully
        empties rows out.
    """
    # Mirror guard of ``build_equity_curve`` (comment there explains why
    # the NaT-anchored single-element shape was chosen over a truly empty
    # Series). Without this, the engine would also IndexError on
    # ``df.index[0]`` for fully-empty input through this helper.
    if df.empty:
        return pd.Series(
            [float(initial_equity)],
            index=pd.DatetimeIndex([pd.NaT]),
            name="equity_naive",
        )
    timestamps: List[pd.Timestamp] = [df.index[0]]
    equity: List[float] = [float(initial_equity)]

    if trades is None or trades.empty:
        return pd.Series(equity, index=pd.DatetimeIndex(timestamps), name="equity_naive")

    running = float(initial_equity)
    for _, t in trades.iterrows():
        idx_pos = min(int(t["exit_idx"]), len(df) - 1)
        timestamps.append(df.index[idx_pos])
        running = running * (1.0 + float(t["pnl_pct"]))
        equity.append(running)

    return pd.Series(equity, index=pd.DatetimeIndex(timestamps), name="equity_naive")

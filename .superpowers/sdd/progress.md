# SDD Progress Ledger

## BRANCH B — Fix + Momentum Pilot (Sprint 1)         2026-07-07
**Status:** DONE — Pilot executed, PF=1.06 vs MR PF=0.40
**Branch:** `feature/path-2-validation-infra`
**Base:** `f3550ef` (docs-only, analysis/)
**Head:** (to be committed)
**Tests:** 277/277 green (+1 regime_stop test vs 276 baseline)

**Changes:**
  - signals/exit.py: +regime_stop param (default True, backward compat),
    +tp_atr_target<=0 validation, updated docstring
  - signals/__init__.py: -momentum_signal_counts from exports (dead code)
  - backtest/engine.py: top-level momentum import, strategy_type before
    step 3, +engine +momentum_entry blocks in _default_cfg,
    regime_stop=False for momentum, regime_ok=True stub for momentum
  - tests/test_exit_tp_modes.py: adx_stop_threshold 25→40 (6 tests),
    .loc[] chain-assignment fix (2 tests), +test_regime_stop_false_bypasses
  - tests/test_momentum_entry.py: assertion tightened >=1→==1,
    .loc[] chain-assignment fix for test_both_mode_emits_short_breakout
  - scripts/run_momentum_12mo.py: Unicode fix, switched to
    run_backtest_for_symbol (handles MultiIndex flattening)

**Pilot result (SPY 2024-10..2025-09, 15-min):**
  - 41 signals → 17 trades
  - PF=1.06, Sharpe=0.17, win rate=41.18%, return=+0.27%
  - Exit reasons: 7 time, 8 SL, 2 open_gap_sl
  - Time-stop trades are the most profitable — momentum edge IS there
    but execution (SL tightness) erodes it.
  - Verdict: MARGINAL (PF>1.0 N<20) — extends to multi-symbol or daily
    per NEXT_DEV_PLAN §4.

---

## PATH 2: Validation Infrastructure — Sprint 1
**Status:** Abandoned — strategy structurally unviable (pivoted to BRANCH B)
**Date:** 2026-07-07
**Branch:** `feature/path-2-validation-infra`
**Plan:** `PATH_2_VALIDATION_INFRASTRUCTURE_PLAN.md`

**Sprint 1.1 result:** 0-24 trades in 5/5 historical regimes, PF<1.0.
Mean-reversion structurally dead on SPY/QQQ/IWM 15-min.

---

## Prior work

## Task 1-5: diagnose_entries.py (full script)
**Status:** Complete
**Branch:** feature/diagnose-entries
**Worktree:** .worktrees/diagnose-entries
**Review:** Fixed 4 issues (--top dead code, strftime-safe dates, Vol(x) in Section 3, signals_skipped backward compat)
**Validation:**
  - Q2 2026 default: 0 signals, 0 trades (production thresholds → no signals fire)
  - Q2 2026 --cfg override (z=1.5, oversold=40): 4L signals, 2 trades
  - Q4 2023: 0 signals, graceful "No signals fired" message
**Files:** scripts/diagnose_entries.py (single file, 370 lines)

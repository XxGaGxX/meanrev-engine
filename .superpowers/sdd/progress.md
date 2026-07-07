# SDD Progress Ledger

## PATH 2: Validation Infrastructure — Sprint 1
**Status:** In progress (pre-flight complete, branch opened, doc updated)
**Date:** 2026-07-07
**Branch:** `feature/path-2-validation-infra` (NEW, opened from `master`)
**Plan:** `PATH_2_VALIDATION_INFRASTRUCTURE_PLAN.md`
**Design decisions (resolved 2026-07-07):**
  - Branch: NEW `feature/path-2-validation-infra` (not continuation of feature/remediation-sprint-1)
  - Timeframe-discretizzazione: tutti 15-min allineati (merge outer su timestamp)
  - Mark-to-market: prezzo corrente posizioni aperte (price lookup continuo, curva MTM continua)
  - Priority di selezione: FIFO cronologico

**Sprint target:** 259 → 264 baseline (+5 unit-test), Portfolio backtest ship-ready con MTM.

**Pre-requisites met:**
  - Slice 3 `run_universe_backtest` ship-ready in `backtest/engine.py` (3 test verdi)
  - 259/259 baseline test verde
  - `config.yaml::walk_forward.*` (6mo train / 1mo test / min 4 finestre / 20% OOS degradation tolerance) pre-configurato
  - `config.yaml::monte_carlo.*` (10k sims / percentili 5/50/95) pre-configurato

**Sub-task tracking:**
  - 1.1 — historical_test.py regime check (2022 Q1-Q3 bear + 2023 Q2-Q3 range): pending
  - 1.2 — `risk/portfolio.py` con `compute_unrealized_pnl` (no-touch su `risk/sizing.py`): pending
  - 1.3 — `run_portfolio_backtest` + `PortfolioResult` con MTM equity + FIFO selection: pending
  - 1.4 — `scripts/run_portfolio_12mo.py` E2E smoke + log: pending
  - Tests — 5 nuovi (cap-3, shared equity, empty skip, skip_reasons, MTM current price): pending
  - Code review — `code-reviewer-minimax-m3` su Sprint 1: pending

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

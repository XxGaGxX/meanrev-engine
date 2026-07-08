# Project Status — Mean Reversion Intraday (quant_trd)

**Data:** 2026-07-07
**Branch corrente:** `feature/path-2-validation-infra`
**Test baseline (pre-pivot):** 259 verdi
**Verdict strategico:** Mean Reversion è strutturalmente non viable su SPY/QQQ/IWM. Pivot in-place a momentum in corso ma con architectural bug noto.

---

## 1. TL;DR

Across **5 finestre storiche × multiple configurazioni**, la strategia mean-reversion intraday non ha mai prodotto edge misurabile:

| Window | Best config | Trades | PF |
|---|---|---|---|
| 2024-10→2025-09 | Sprint 1 (soglie rilassate) | 24 | 0.40 |
| 2024-10→2025-09 | Step 1.6 (vol_confirm off) | 11 | 0.013 |
| 2023-10→2024-09 | Baseline cross-val | 0 | undef |
| 2022 Q1-Q3 (bear) | historical_test.py | 8 | 0.0 (Sharpe=-1.98) |
| 2023 Q2-Q3 (range) | historical_test.py | 0 | undef |

**regime_ok pass rate 6-9%** in TUTTI i window testati. PF<1.0 ovunque. Nessuna combinazione migliora il pattern. Il problema è **strutturale, non parametrico**.

**Diagnostics (statistical):**
- **Regime-predictive test** (Welch t-test + Cohen d, 4 orizzonti N=6/12/24/48 bars, random control): `regime_ok` bars revert *less* than random → **d=-0.25 al primary N=12**, 4/4 orizzonti NEGATIVE, **binom p=0.0625**. Il filtro è **mildly COUNTER-predittivo** sulla mean-reversion.
- **Cointegration test** (Engle-Granger, daily 12mo, p=SPY/QQQ=0.13, p=SPY/IWM=0.93, p=QQQ/IWM=0.86). **Nessun pair viable.** Rolling 60-day persistence 5-18% (target ≥60%).

→ **Option A (regime-conditional wrapper)** e **Option B (pairs su SPY/QQQ/IWM)** ruled out data-driven.

**Current action:** Pivot in-place a **momentum** (Donchian breakout su 15-min) — codice scritto ma con **5 test failures** causati da un **bug architetturale** (`regime_stop` semantics non-corrispondenti tra logica MR e logica momentum).

**Next step consigliato:** Fix + pilot momentum → decide basato su PF/N → recommend next branch (WFA+MC vs abbandono intraday).

---

## 2. Sviluppo timeline (FASE 0-9)

| Fase | Modulo | Stato | Note |
|---|---|---|---|
| **FASE 0** | `data/`, `utils/config.py`, `utils/metrics.py` | ✅ Completa | |
| **FASE 1** | `indicators/`, `filters/regime.py` | ✅ Completa | Hurst slow+fast, ADX, ATR |
| **FASE 2** | `signals/entry.py`, `signals/exit.py` | ✅ Completa | MR entry; exit con TP/SL/time/regime |
| **FASE 3** | `risk/sizing.py` | ✅ Completa | 1% rule vol-targeted, Kelly-cap |
| **FASE 4 Slice 1** | `backtest/engine.py::run_backtest` | ✅ Completa | Single-symbol pipeline |
| **FASE 4 Slice 2** | `run_backtest_for_symbol` | ✅ Completa | Preflight credenziali |
| **FASE 4 Slice 3** | `run_universe_backtest` | ✅ Completa | Dict-level aggregator (3 test verdi) |
| **FASE 4 Slice 4** | `run_portfolio_backtest` + MTM | ⏸️ Pianificato solo | PATH 2 Sprint 1.2-1.4 mai iniziato |
| **FASE 5** | `backtest/walk_forward.py` | ⏸️ Solo piano | NEXT_STEPS_PLAN §6 |
| **FASE 6** | `backtest/monte_carlo.py` | ⏸️ Solo piano | NEXT_STEPS_PLAN §7 |
| **FASE 7** | `live/paper.py` | ❌ Non iniziato | |
| **FASE 8** | `live/live.py` | ❌ Non iniziato | |

**Test count:** 259 baseline verdi (predecessore del pivot momentum).

---

## 3. Documenti di piano esistenti

| File | Scopo | Stato |
|---|---|---|
| `documentation.md` | Documentazione tecnica della strategia MR | Reference |
| `IMPLEMENTATION_PLAN.md` | Master plan FASE 0-9 | Reference |
| `NEXT_STEPS_PLAN.md` | Slice 3-4 + WFA + MC + Paper/Live | Reference (vecchio) |
| `BACKTEST_REMEDIATION_PLAN.md` | Sprint 1-3 della remediation (completata) | Storico |
| `FIX_PLAN.md`, `FIX_PLAN_v2.md`, `BOTTLENECK_FIX_PLAN.md` | Bug fix storici | Storico |
| `PATH_2_VALIDATION_INFRASTRUCTURE_PLAN.md` | 3-sprint Validation Infra plan (Pivot-B Plan) | Aggiornato 2026-07-07 (Sprint 1.1 done) |
| `BUG_REPORT.md` | Resoconto bug cronologico | Storico |

---

## 4. Risultati diagnostici del 2026-07-07

### 4.1 Backtest matrix (5 finestre x multiple configurazioni)

| Window | Config | Trades | PF | Sharpe | Regime OK% |
|---|---|---|---|---|---|
| 2024-10→2025-09 | Sprint 1 (soglie rilassate) | 24 | 0.40 | neg | ~15% |
| 2024-10→2025-09 | Step 1.6 (vol_confirm off) | 11 | 0.013 | neg | ~15% |
| 2023-10→2024-09 | Baseline cross-val | 0 | undef | n/a | ~9% |
| 2022 Q1-Q3 (bear) | historical_test.py | 8 | 0.0 | −1.98 | 7.2% |
| 2023 Q2-Q3 (range) | historical_test.py | 0 | undef | n/a | 6.3% |

**Pattern strutturale:** regime_ok pass rate 6-9% in TUTTI i window; PF<1.0 ovunque; nessuna combinazione migliora il pattern emerso.

### 4.2 Test statistici (in `analysis/`)

| Test | Risultato | Script | Implicazione |
|---|---|---|---|
| Regime-predictive (random control, 4 orizzonti) | d=-0.25 @ primary N=12, 4/4 NEGATIVE, binom p=0.0625 | `scripts/check_regime_predictive.py` | Filter COUNTER-predittivo |
| Cointegration EG (Daily 12mo SPY/QQQ/IWM) | p: SPY/QQQ=0.13, SPY/IWM=0.93, QQQ/IWM=0.86 | `scripts/check_cointegration.py` | No pair viable |

JSON diagnostici: `analysis/cointegration_20241001_20250930.json`, `analysis/regime_predictive_SPY_20241001_20250930.json`.

---

## 5. Codice del pivot PATH 3 (Momentum Donchian Breakout)

**Branch:** `feature/path-2-validation-infra` (working tree, uncommitted)

### 5.1 File modificati / creati

| File | Tipo | Note |
|---|---|---|
| `signals/momentum_entry.py` | NEW | Donchian breakout, ADX≥25, vol_confirm, direction_mode |
| `signals/exit.py` | MOD | `tp_mode` + `tp_atr_target` params per simulate_exit |
| `backtest/engine.py` | MOD | `engine.strategy_type` router (mean_reversion\|momentum) |
| `signals/__init__.py` | MOD | Export `generate_momentum_entry_signals` |
| `config.yaml` | MOD | Aggiunto `engine:` + `momentum_entry:` blocks |
| `tests/test_momentum_entry.py` | NEW | 10 test per breakout signals |
| `tests/test_exit_tp_modes.py` | NEW | 7 test per zscore\|atr_target\|none |
| `scripts/run_momentum_12mo.py` | NEW | Pilot driver (SPY 12mo via Alpaca) |

### 5.2 Risultati test (mid-implementation)

```
282 attempted / 270 passed / 5 FAILED (test_exit_tp_modes.py)
```

**Root cause dei 5 failures:** fixture `trending_up_df` / `trending_down_df` settano `adx=30.0`. `simulate_exit` default `adx_stop_threshold=25.0`. La condition `adx > adx_stop_threshold or not regime_ok` → **regime_stop fires at bar 1**, prima che TP o time stop possano agire. Tutte e 5 le assertions su TP firing / time stop firing falliscono perché `exit_reason == "regime"`.

Affected test:

1. `test_tp_zscore_default_fires_when_zscore_crosses_zero`
2. `test_tp_atr_target_long_triggers_at_target_price`
3. `test_tp_atr_target_short_triggers_at_target_price`
4. `test_tp_atr_target_propagates_through_simulate_all_trades`
5. `test_tp_none_still_exits_via_time_stop`

### 5.3 Architectural bug (PIÙ GRAVE dei test failures, scoperta da code-reviewer-minimax-m3)

**Problema:** la semantica `if adx > adx_stop_threshold or not regime_ok: exit` è Mean-Reversion-specific ("ADX crosses above = trend forming = bad for MR"). Per Momentum:
- ADX corre alto (20-40+) durante trend sani per ore.
- Con `momentum_entry.adx_stop_threshold=20.0` (default in config) + ADX reale 30+ in SPY trending windows.
- **OGNI momentum trade uscirebbe al bar 1** indipendentemente dalla qualità dell'entry breakout.
- `scripts/run_momentum_12mo.py` produrrebbe ~zero trade nel pilot, **anche con entry corrette**.

**Fix richiesto:**

1. Aggiungere param `regime_stop: bool = True` a `simulate_exit` in `signals/exit.py`.
2. Modificare la condition in `if regime_stop and (adx > adx_stop_threshold or not regime_ok): exit`.
3. Propagare via `simulate_all_trades(cfg)` block + validation.
4. `engine.py` set `regime_stop=False` per modalità momentum.
5. ~10 LOC totali.

### 5.4 Other findings del code-reviewer (hygiene, non bloccanti per pilot)

- **Step 3 (`apply_regime_filter`) dead-work per momentum mode**: build `regime_ok` column che `generate_momentum_entry_signals` ignora. Compute waste (~2s su 5.5k barre).
- **Lazy import** di `signals/momentum_entry` nel conditional block di `engine.py` — inconsistente con stile top-of-file del file.
- **`momentum_signal_counts` exported ma non usato** — engine.py chiama `signal_counts(df)` per entrambi i tipi di strategia.
- **Validation gap** per `tp_atr_target <= 0` in `atr_target` mode.
- **Loose assertion** in `test_momentum_signal_counts_helper` (`>= 1` invece di `== 1`).

---

## 6. Open questions

| ID | Domanda | Stato |
|---|---|---|
| Q1 | `regime_ok` predice mean-reversion? | ❌ **NO** (counter-predictive) — analysis/strategy-fit.md §11 |
| Q2 | SPY/QQQ/IWM cointegrati? | ❌ **NO** — analysis/strategy-fit.md §10 |
| Q3 | Momentum funziona su 15-min SPY? | ⏳ Need pilot (architectural bug da fixare prima) |
| Q4 | Pairs su universo espanso (XLE, DBA, FXE, UUP)? | ⏳ Need fresh cointegration test — non eseguito |
| Q5 | Time budget per prossima iterazione? | Open |
| Q6 | Timeframe alternativi (5-min, daily)? | Open |

---

## 7. Reference files (dove trovare i dati)

- **Strategy verdict (loggetto di analysis/strategy-fit):** documentato in `PATH_2_VALIDATION_INFRASTRUCTURE_PLAN.md §15` e aggregato in questo file §4. Riassunto TL;DR + 5-window matrix.
- **Diagnostic JSONs:** `analysis/cointegration_*.json`, `analysis/regime_predictive_*.json`.
- **Diagnostic logs:** `scripts/output/run_coint_*.log`, `run_regime_predictive_*.log`, `run_*.log`.
- **Progress ledger:** `.superpowers/sdd/progress.md`.

---

## 8. Sintesi dello stato

**Cosa funziona:**

- Architettura pipeline (clean → indicators → regime → entry → exit → sizing → equity → metrics) è solida.
- Engine, sizing, MTM equity curve, realistic-fill contracts sono riutilizzabili.
- `run_universe_backtest` (Slice 3) è ship-ready.
- Test infrastructure (pytest, fixtures, contract tests) è matura.

**Cosa NON funziona:**

- La mean-reversion hypothesis è morta. Né param-tuning né regime-conditional wrapper né pairs lo hanno salvato.

**Cosa è in sospeso:**

- Pivot momentum mid-implementation: 5 test failures + 1 architectural bug → ship-ready in ~1 sprint (1-2 sessioni).
- Se pilot momentum valida → proseguire con WFA/MC su dati VIVI momentum.
- Se pilot fallisce → abbandonare equity-index intraday → altre branch (pairs espanso, daily, strategy nuova).

---

## 9. Prossimo passo

Vedi `analysis/DECISION_TREE_2026_07_07.md` per il fork decisionale e `analysis/NEXT_DEV_PLAN_2026_07_07.md` per il piano operativo.

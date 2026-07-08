# NEXT STEP ANALYSIS — 2026-07-07

**Branch:** `master` (HEAD: `703ec4c`)
**Context:** Post-merge of `feature/path-2-validation-infra` (BRANCH B Sprint 1).
**Tests:** 277/277 green.

---

## 1. Codebase State

### Moduli attivi

| Modulo | File | Stato |
|---|---|---|
| **Data fetch** | `data/fetch.py` | ✅ Alpaca 15-min OHLCV |
| **Data clean** | `data/clean.py` | ✅ Session filter + dedup |
| **Indicators** | `indicators/pipeline.py` | ✅ ADX, Hurst, RSI, BB, zscore, vol, ATR |
| **Regime filter** | `filters/regime.py` | ✅ MR-only (skipped for momentum) |
| **Entry — MR** | `signals/entry.py` | ✅ Soft-scoring, vol confirm |
| **Entry — Momentum** | `signals/momentum_entry.py` | ✅ Donchian breakout (NEW) |
| **Exit** | `signals/exit.py` | ✅ tp_mode (zscore/atr_target/none), regime_stop param |
| **Risk sizing** | `risk/sizing.py` | ✅ Vol-targeted, Kelly fraction |
| **Backtest engine** | `backtest/engine.py` | ✅ `run_backtest`, `run_backtest_for_symbol`, `run_universe_backtest` |
| **Metrics** | `utils/metrics.py` | ✅ Sharpe, Sortino, drawdown, Calmar, VaR, CVaR |
| **Config** | `config.yaml` | ✅ engine.strategy_type router, momentum_entry block |

### Pipeline

```
fetch → clean → indicators → [regime filter MR-only] → entry (MR | momentum)
→ exit simulation → position sizing → equity curve → metrics
```

---

## 2. Backtest Results Summary

### Mean-Reversion (strutturalmente morta)

| Window | Trades | PF | Sharpe | Exit Reason |
|---|---|---|---|---|
| 2024-10 → 2025-09 (Sprint 1) | 24 | 0.40 | negativo | — |
| 2023-10 → 2024-09 (cross-val) | 0 | undef | — | — |
| 2024-10 → 2025-09 (Step 1.6) | 11 | 0.013 | — | — |
| 2022 Q1-Q3 (bear) | 8 | 0.0 | −1.98 | 5 SL, 1 time, 2 end_of_data |
| 2023 Q2-Q3 (range) | 0 | undef | — | — |

**Diagnostica completata:**
- Regime filter counter-predittivo (d=−0.25, 4/4 orizzonti neg, binom p=0.0625)
- SPY/QQQ/IWM non cointegrate (p=0.13/0.93/0.86)
- `regime_ok` pass rate 6-9% in tutti i window (config min=8%)
- `|z|>2` su 15-min: 1-2% delle barre

**Verdetto:** MR intraday su equity ETF non ha edge dimostrabile in 5/5 finestre storiche.

### Momentum Donchian (Pilot — Sprint 1)

| Metrica | Valore |
|---|---|
| **Simbolo** | SPY |
| **Timeframe** | 15-min |
| **Periodo** | 2024-10 → 2025-09 (~12mo) |
| **Segnali** | 41 long |
| **Trade** | 17 |
| **Win rate** | 41.18% (7/17) |
| **Profit Factor** | **1.06** |
| **Sharpe** | 0.17 |
| **Return** | +0.27% |
| **Max drawdown** | −1.83% |

**Exit reasons breakdown:**

| Reason | Count | Avg PnL | Note |
|---|---|---|---|
| **time** (25 bars) | 7 | **+0.89%** | ✅ Consistentemente profittevole |
| **sl** | 8 | −0.39% | ❌ SL a 2×ATR erode i trade |
| **open_gap_sl** | 2 | −0.72% | ❌ Gap fill peggiore dello SL normale |

**Key insight:** I trade che arrivano al time-stop (25 barre, ~6 ore) sono TUTTI profittevoli. La tesi momentum ha edge, ma l'esecuzione (SL troppo stretto, gap fill) lo erode.

### Confronto MR vs Momentum

| | MR | Momentum |
|---|---|---|
| Trade | 24 | 17 |
| PF | 0.40 | **1.06** |
| Win rate | 16.7% | **41.18%** |
| Return | negativo | **+0.27%** |
| Edge direction | ❌ Contrarian fallito | ⚠️ Trend marginale |

---

## 3. Decision Tree Status

Dal `ai_docs/DECISION_TREE_2026_07_07.md`, stato attuale:

```
MR strutturalmente non viable (5/5 finestre fallite)
  └─ Pivot in-place: Momentum Donchian ✅
       └─ Pilot PF=1.06, N=17 ⚠️ MARGINAL
            └─ NEXT: Estensione multi-symbol (SPY+QQQ+IWM)
                 └─ Se N aggregato > 50 e PF > 1.10:
                      └─ PATH 2 WFA/MC su momentum (re-purpose)
                 └─ Se PF < 1.0 aggregato:
                      └─ Pivot daily timeframe o nuova strategia
```

---

## 4. Raccomandazione: PROSSIMO SPRINT

### Obiettivo: Validare momentum multi-symbol

Usare `run_universe_backtest` (già ship-ready in `backtest/engine.py`) su **SPY + QQQ + IWM** per lo stesso periodo 12mo (2024-10 → 2025-09), con la stessa configurazione momentum Donchian.

**Razionale:**
1. **Aumenta N statistico:** 17 trade single-symbol → potenzialmente 40-60 aggregati, sufficienti per significatività statistica.
2. **Diversificazione di regime:** QQQ (tech-heavy) e IWM (small-cap) hanno dinamiche trending diverse da SPY — se momentum funziona su tutti e 3, la tesi è robusta.
3. **Costo implementativo zero:** `run_universe_backtest` è già testato (3 test verdi) e pronto all'uso. Basta uno script driver di ~30 linee.

### Sub-task Sprint 2

| # | Task | Effort |
|---|---|---|
| 1 | `scripts/run_momentum_universe.py`: driver per `run_universe_backtest` con `strategy_type=momentum` su SPY/QQQ/IWM | 30 min |
| 2 | Eseguire backtest multi-symbol; aggregare metriche per-simbolo e totali | 5 min |
| 3 | Se PF aggregato > 1.10 e N > 50 → proseguire con WFA (re-purpose PATH 2) | — |
| 4 | Se PF aggregato < 1.0 → pivot daily timeframe (Donchian daily ha più spazio statistico) | — |
| 5 | **Quick win**: testare `tp_mode="atr_target"` con `tp_atr_target=1.5` (take profit al 1.5×ATR) — riduce l'esposizione al time-stop e potrebbe stabilizzare il PF | 10 min |

### Quick Win immediato (pre-Sprint 2)

Prima dello Sprint 2 multi-symbol, testare **due varianti rapide** sul pilot single-symbol per capire se l'edge migliora:
- **Variante A:** `tp_mode="atr_target"`, `tp_atr_target=1.5` (TP a 1.5×ATR ≈ +3% su SPY)
- **Variante B:** `atr_multiplier=3.0` (SL più largo, meno whipsaw)

Se una delle due varianti porta PF > 1.20 su SPY, lo Sprint 2 multi-symbol parte con quella configurazione.

---

## 5. File Organizzati

Tutti i documenti di pianificazione spostati in `ai_docs/`:
- `IMPLEMENTATION_PLAN.md` — piano originale
- `NEXT_STEPS_PLAN.md` — fasi 5-8 originali
- `BACKTEST_REMEDIATION_PLAN.md` — root cause analysis MR + 3 sprint
- `BOTTLENECK_FIX_PLAN.md` — fix colli di bottiglia
- `FIX_PLAN.md` / `FIX_PLAN_v2.md` — piani di fix iterativi
- `BUG_REPORT.md` — bug report
- `PATH_2_VALIDATION_INFRASTRUCTURE_PLAN.md` — piano PATH 2
- `documentation.md` — documentazione originale
- `DECISION_TREE_2026_07_07.md` — albero decisionale
- `NEXT_DEV_PLAN_2026_07_07.md` — piano BRANCH B
- `PROJECT_STATUS_2026_07_07.md` — sintesi stato

---

## 6. Riferimenti

- `ai_docs/DECISION_TREE_2026_07_07.md` — contesto decisionale completo
- `ai_docs/PROJECT_STATUS_2026_07_07.md` — sintesi stato progetto
- `ai_docs/NEXT_DEV_PLAN_2026_07_07.md` — BRANCH B sub-task detail
- `scripts/output/run_momentum_12mo.log` — pilot output completo
- `config.yaml` — configurazione corrente (strategy router)

# NEXT_DEV_PLAN — Pivot In-Place (Momentum Donchian + PATH 2-Ready)

**Data:** 2026-07-07
**Branch corrente:** `feature/path-2-validation-infra`
**Decisione di riferimento:** **BRANCH B** del `analysis/DECISION_TREE_2026_07_07.md`
**Effort stimato:** 1-2 sessioni
**Goal:** validare (o confutare) momentum su 15-min SPY 12mo con 1 architectural fix + 5 test fix + 1 pilot run.

---

## 1. Motivazione & Contesto

La mean-reversion è strutturalmente morta su SPY/QQQ/IWM 15-min. PATH 2 con mock data ha ROI discutibile. PATH 3 momentum ha 5 test failures per un singolo bug architetturale noto. L'opzione a **costo minimo con ROI massimo atteso** è:

1. Fixare l'architectural bug + i 5 test failures (~1 sessione).
2. Eseguire il pilot momentum (scripts/run_momentum_12mo.py).
3. Decidere data-driven (PF/N) → proseguire con WFA/MC o pivotare.

Vantaggi strategici:

- **Pilot su dati VIVI** (non mock) → stress test reale dell'infrastruttura Portfolio + WFA future.
- **Tesi differente (contrarian vs momentum)** — momentum presuppone trend continuations, non contrarian. Il regime Q4 2025 trending che ha ammazzato MR è ESATTAMENTE dove momentum DEVE funzionare.
- **Fail-fast** — 1 sprint, output binario.

---

## 2. Sub-tasks Sprint 1

### 2.1 Fix `simulate_exit::regime_stop` semantics (REQUIRED)

**Problema:** default `if adx > adx_stop_threshold or not regime_ok: exit` è MR-specific.
Per momentum, ADX corre alto (20-40+) durante trend sani; con `momentum_entry.adx_stop_threshold=20.0`
e ADX reale 30+ durante trend SPY, il regime_stop MR fire al bar 1 e chiude ogni trade momentum.

**Fix in `signals/exit.py::simulate_exit`:**

```python
def simulate_exit(
    df, entry_idx, direction,
    atr_multiplier=1.5, max_bars=25, adx_stop_threshold=25.0,
    tp_mode="zscore", tp_atr_target=4.0,
    regime_stop: bool = True,  # ← NEW
) -> ExitResult:
    ...
    # Modificare la condition:
    if regime_stop and (adx > adx_stop_threshold or not regime_ok):
        return _build_result(entry_idx, i, entry_price, close, direction, "regime")
```

**Fix in `signals/exit.py::simulate_all_trades`:**

```python
regime_stop = bool(cfg.get("regime_stop", True))
...
result = simulate_exit(
    df, entry_idx=pos, direction=direction,
    atr_multiplier=atr_multiplier, max_bars=max_bars,
    adx_stop_threshold=adx_stop_threshold,
    tp_mode=tp_mode, tp_atr_target=tp_atr_target,
    regime_stop=regime_stop,
)
```

**Effort:** ~10 LOC. **Critical per il pilot.**

### 2.2 Set `regime_stop=False` per momentum in `engine.py`

In `backtest/engine.py::run_backtest` modalità momentum:

```python
exit_cfg["regime_stop"] = mcfg.get("regime_stop", False)  # momentum: regime_stop off
```

**Effort:** 1 riga. **Critical.**

### 2.3 Fix 5 failing test (fixtures ADX vs threshold)

In `tests/test_exit_tp_modes.py`, nelle 5 funzioni interessate, settare
`adx_stop_threshold` a un valore alto che NON e' triggerabile dal fixture:

Fix pattern (5 occorrenze):

- `test_tp_zscore_default_fires_when_zscore_crosses_zero`: `adx_stop_threshold=40.0`
- `test_tp_atr_target_long_triggers_at_target_price`: `adx_stop_threshold=40.0`
- `test_tp_atr_target_short_triggers_at_target_price`: `adx_stop_threshold=40.0`
- `test_tp_atr_target_propagates_through_simulate_all_trades`: dict key `"adx_stop_threshold": 40.0`
- `test_tp_none_still_exits_via_time_stop`: `adx_stop_threshold=40.0`

**Effort:** 5 modifiche da 1 riga ciascuna.

### 2.4 Validation gap per `tp_atr_target <= 0` in atr_target mode

In `signals/exit.py::simulate_all_trades`, aggiungere dopo il check tp_mode:

```python
if tp_mode == "atr_target" and tp_atr_target <= 0:
    raise ValueError(
        f"tp_atr_target must be > 0 for tp_mode='atr_target', got {tp_atr_target!r}"
    )
```

**Effort:** 3 righe.

### 2.5 Hygiene refactor (engine.py)

- **Lazy import → top-level** in `backtest/engine.py`:
  spostare `from signals.momentum_entry import generate_momentum_entry_signals`
  da conditional block a top-level import.
- **Dead code removal:** rimuovere `momentum_signal_counts` da `signals/__init__.py` exports
  (engine.py chiama `signal_counts(df)` per entrambi i tipi, helper mai usato).
- **Tighten test assertion:** in `test_momentum_signal_counts_helper`,
  cambiare `assert counts["long_signals"] >= 1` → `assert counts["long_signals"] == 1`.

**Effort:** ~10 righe totali. (Non-blocking per pilot ma migliora la qualità.)

### 2.6 Opzionale: gate step 3 (regime filter) per momentum

In modalità momentum, il regime filter (Hurst slow + scoring) è dead-work.
Per risparmiare ~2s di compute su 5.5k barre:

```python
# In engine.py::run_backtest, dopo indicato passo 2:
if engine_cfg.get("strategy_type", "mean_reversion") == "mean_reversion":
    df = apply_regime_filter(df, **cfg_merged["regime_filter"])
```

**Effort:** 2-3 righe. **Priorità bassa** (non blocca pilot). Fare DOPO 2.1-2.5.

### 2.7 Pilot run + metriche

```bash
python scripts/run_momentum_12mo.py > scripts/output/run_momentum_12mo.log 2>&1
```

Output atteso nel log: numero segnali, trades, PF, Sharpe, trade log.

**Effort:** 1 comando + verifica. ~30 sec esecuzione (Alpaca fetch).

### 2.8 Documenta risultati + aggiorna SDD ledger

- Aggiorna `.superpowers/sdd/progress.md` con lo status del pilot + exit reason.
- Se PF >= 1 e N >= 20: scrivi `analysis/PATH_3_NEXT.md` con WFA/MC plan su momentum.
- Se PF < 1 o regime_stop persistance: scrivi `analysis/ABANDON_INTRADAY.md` con pivot recommendation.

---

## 3. Acceptance Criteria (Sprint 1)

| Criterio | Target | Se fallisce |
|---|---|---|
| `pytest tests/` full suite | **277/277** (270 baseline + 7 nuovi exit_tp_modes) | iterare sui Required findings |
| Tutti e 5 i `test_exit_tp_modes` failed | ✅ passing dopo fixture fix | blocca pilot run |
| `regime_stop` architectural param in `simulate_exit` | ✅ presente, validation OK, docstring | Required |
| `scripts/run_momentum_12mo.py` pilot output | ✅ non crash, log scritto | blocca decision |
| Trade count dal pilot | >= 5 (criterio minimo statistico) | se 0 → architectural fix non risolto |
| Pilot PF | >= 1.0 (criterio minimo) | se < 1 → aborta momentum; pivot |

---

## 4. Cancellation / Extension Path

| Pilot outcome | Next action |
|---|---|
| **PF >= 1.0 e N >= 20** ✅ | Entrare in PATH 2 WFA/MC su momentum (re-purpose del piano). Sprint 2 = WFA, Sprint 3 = MC. Validazione real-data. |
| **PF >= 1.0 e N < 20** ⚠️ | Marginal. Estendere a: (a) daily timeframe; (b) multi-symbol aggregation. Sprint 2 = daily+momentum. |
| **PF < 1.0 e N >= 20** ❌ | Momentum non viable in equity-intraday. Pivot **BRANCH C** (pairs universo espanso) o **BRANCH E** (strategy nuova). |
| **0 trade prodotti** 🐛 | Bug architetturale non risolto. Debug regime_stop su dati reali. Escalatione. |
| **PF ~ 1 borderline** | Estendere il periodo di test (24mo invece di 12mo) per N migliore. |

### Se pytest NFLY outcomes

- 5 test fail anche dopo fixture fix → altri parametri `adx_stop_threshold` richiesti,
  oppure `regime_stop` param non integrato correttamente → iterare.

---

## 5. Architectural Hygiene (incluso anche se test passano)

- Lazy import → top-level in `engine.py`.
- Dead code removal (`momentum_signal_counts`).
- Loose assertion → tight assertion in `test_momentum_signal_counts_helper`.
- Validation gap per `tp_atr_target <= 0`.

Questi non bloccanti ma prevengono debt accumulation che peggiorerà la prossima iterazione.

---

## 6. Note di Architettura (per evitare il debito dei piani precedenti)

**Cosa è andato STORTO nei piani precedenti:**

- **PATH 2 mock data**: scrivere portfolio backtest su stringhe casuali produce test fragili
  e morale basso. Evita over-engineering senza feedback empirico.
- **NEXT_STEPS_PLAN §6/§7 (WFA/MC)**: metriche predefinite (es. OOS degradation tolerance 20%)
  sono sensate per mean-reversion ma NON per momentum (Payoff profile molto asimmetrico).
  → Quando si entra in PATH 2 re-purposed, aggiornare tolerance metriche per momentum.
- **`run_momentum_12mo.py` non testato**: prima di commit, almeno 1 test smoke che asserisca
  che lo script si avvia e fallisce gracefully se Alpaca creds mancanti.

**Cosa fare diversamente in Sprint 1 di PATH 2 re-purposed (Sprint 2 di questo piano):**

- WFA 1° deve essere testato su dati VIVI momentum, non mock.
- MC 1° acceptance gate deve essere adattato al payoff asimmetrico del momentum.
- Multi-symbol aggregation in Sprint 2 simultaneo (non Sprint separato).

---

## 7. Critical Risks & Defensive Design

### Risk #1 — Il momentum exit (time stop) non cattura trend reali

`tp_mode="none"` + time stop 25 bars = ~6 ore. SPY trending moves sometimes durano giorni.
Una thesis momentum seria richiede trailing stop dinamico.

**Mitigation:** monitorare trade log nel pilot; se la maggior parte esce per time stop con bassa expectancy, è segnale che il momentum exit è sub-ottimale.

### Risk #2 — `regime_stop=False` espone al lato opposto (trend death)

Senza `regime_stop`, se ADX crolla improvvisamente (trend muore), il momentum trade
può restare aperto indefinitamente finché SL/time-stop non fire.

**Mitigation:** in Sprint 2 (WFA su momentum), valutare aggiungere **regime stop INVERSO** per momentum (esce se `adx < adx_min` ⇒ trend morto). Refactor futuro: sostituire `regime_stop: bool` con `regime_stop_mode: Literal["none", "mean_reversion", "momentum"]`.

### Risk #3 — Pilot su 12 mesi troppo corto (1 regime)

SPY 2024-10→2025-09 trending bull. Pilot valida momentum SU QUESTO regime, non su altri.

**Mitigation:** se pilot passes, Sprint 2 deve includere WFA su ≥ 3 finestre storiche con regimi diversi (trend up, trend down, range) per evitare overfitting su 1 regime.

---

## 8. Effort Breakdown (1 session = ~2 ore)

| Sub-task | Effort | Blocking? |
|---|---|---|
| 2.1 regime_stop param | 15 min | Sì |
| 2.2 engine.py set | 5 min | Sì |
| 2.3 5 test fix | 15 min | Sì |
| 2.4 tp_atr_target validation | 5 min | No |
| 2.5 hygiene refactor | 20 min | No |
| 2.6 step 3 gate (optional) | 5 min | No |
| 2.7 pilot run | 5 min + fetch | Sì |
| 2.8 documentation | 10 min | No |
| **Totale** | **~80 min** | 1 session |

---

## 9. References

- `analysis/PROJECT_STATUS_2026_07_07.md` — synthesis
- `analysis/DECISION_TREE_2026_07_07.md` — BRANCH B context
- `PATH_2_VALIDATION_INFRASTRUCTURE_PLAN.md §15` — regime check 2022/2023
- `analysis/strategy-fit.md` (storico in conversazione) — MR verdict con diagnostics
- `scripts/check_regime_predictive.py` — diagnostic statistico MR
- `scripts/check_cointegration.py` — diagnostic statistico pairs
- `scripts/run_momentum_12mo.py` — pilot driver
- `signals/momentum_entry.py` (NEW) — entry module
- `signals/exit.py` (MOD) — tp_mode/regime_stop extension
- `backtest/engine.py` (MOD) — strategy_type router

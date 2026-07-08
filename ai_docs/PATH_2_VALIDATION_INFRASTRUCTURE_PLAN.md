# PATH 2 Implementation Plan — Validation Infrastructure

**Data:** 2026-07-07
**Branch corrente:** `feature/remediation-sprint-1`
**Trigger:** Option A (regime-conditional) e Option B (pairs su SPY/QQQ/IWM) **ruled out** dai diagnostics del 2026-07-07. La strategia mean-reversion corrente non ha edge misurabile in nessuna delle 4 configurazioni testate.
**Stato test attuale:** 259 verdi (rimasti stabili dopo le diagnostiche; nessun engine change).
**Decisione guida:** investire in **infrastruttura di validazione** invece che continuare a tuneare la strategia.

---

## 1. TL;DR

PATH 2 consegna, in **3 sprint**, l'infrastruttura minima per valutare **qualsiasi strategia futura** con rigore statistico: walk-forward su portafoglio multi-symbol + Monte Carlo sui trade log out-of-sample. Al termine, un **Cancellation Gate** decide se:

- (a) la strategia mean-reversion ha edge in qualche regime storico → si prosegue con FASE 7/8 (paper/live trading);
- (b) la strategia mean-reversion non ha edge in nessun regime testato → **si abbandona la thesis** e si pivotà a una nuova famiglia (momentum, breakout, pairs su universo espanso) usando l'infrastruttura appena costruita.

**Costo totale stimato:** 3 sprint (vs 6+ di NEXT_STEPS_PLAN perché FASE 7/8 sono deferred).

**Trade-off esplicito:** costruire WFA/MC su una strategia attualmente morta è un investimento con ritardo di 6+ mesi sul primo trade live. È giustificato solo perché ogni tentativo di fixare la strategia corrente ha peggiorato le metriche (4 test, ognuno peggio del precedente) — quindi il **costo di continuare a tuneare è superiore al costo di costruire l'infrastruttura**.

---

## 2. Perché PATH 2 (riepilogo)

I risultati documentati in `analysis/strategy-fit.md` §10-11 hanno risposto a 2 domande aperte con esito negativo:

| Domanda | Risultato | Implicazione |
|---|---|---|
| `regime_ok` ha valore predittivo per mean-reversion? | NO — d=-0.25, 4/4 orizzonti NEGATIVE, binom p=0.0625 | Option A (regime-conditional wrapper) non produce edge |
| SPY/QQQ/IWM sono cointegrati? | NO — p=0.13/0.93/0.86, rolling persistence 5-18% vs 60% richiesto | Option B (pairs su universo corrente) non viable |

Routing logico:
1. Se l'unico fix possibile (regime filter) è **contro-produttivo**, ulteriori tuning del regime non aiuteranno.
2. Se l'unico universo (SPY/QQQ/IWM) **non è cointegrato**, ulteriori tuning delle soglie entry/exit non aiuteranno.
3. **Il problema è strutturale**, non parametrico.

→ PATH 2 costruisce gli strumenti per **verificare strutturalmente** ipotesi future, prima di scrivere logica di strategia. Questo inverte l'ordine abituale (prima strategia, poi validation) ed è la risposta corretta al fallimento corrente.

---

## 3. Principi guida dei 3 sprint

1. **Slice discipline** — uno sprint alla volta, ship-ready (test verdi + code-reviewer approvato).
2. **Sequenza stretta** — Sprint 1 → 2 → 3 in serie; **non parallelizzarli** (Sprint 2 dipende da Sprint 1; Sprint 3 dipende da Sprint 2).
3. **Niente strategy tuning** — gli sprint operano sull'infrastruttura, NON sui parametri di `config.yaml`.
4. **Test count come metrica** — ogni sprint deve incrementare il totale test verso i target (§7).
5. **Cancellation gate visibile** — la decisione di proseguire o pivotare è quantitativa, non narrativa.

---

## 4. Sprint 1 — Portfolio Backtest (Slice 4 di NEXT_STEPS_PLAN)

**Goal:** abilitare backtest su portafoglio multi-symbol con equity condivisa, **prerequisito** per la WFA in Sprint 2.

**Dipendenze:** Slice 3 (`run_universe_backtest`) ship-ready in `backtest/engine.py` (3 test verdi).

### Sub-task

| # | Task | Criterio done |
|---|---|---|
| 1.1 | **Verification prep**: eseguire `historical_test.py` su SPY in 2022 Q1-Q3 (bear) e 2023 Q2-Q3 (range-bound). Output: numero trade per regime. Scopo: determinare se la strategia ha edge in qualche regime storico (pre-requisito logico per usare il portfolio backtest su dati "vivi" vs mock). Se N=0 anche qui, **l'infrastruttura Sprint 1 verrà testata con mock DataFrame** in Sprint 2 — non è bloccante. | `output/run_regime_check_2022Q1Q3.log` + `output/run_regime_check_2023Q2Q3.log` |
| 1.2 | **Creare `risk/portfolio.py`** con sizing per portafoglio multi-symbol (refactor verticale, NON modificare `risk/sizing.py::apply_position_sizing` in-place). Mantiene equity pool condiviso, mark-to-market delle posizioni aperte, `max_open_positions` a livello portafoglio. | Modulo + 2 unit-test |
| 1.3 | **`run_portfolio_backtest(datasets, cfg, max_open_positions=N)`** → `PortfolioResult` con: equity portafoglio aggregato, trade log cross-symbol, skip_reasons (`max_positions_reached`, `regime_not_ok`, `insufficient_equity`), metriche aggregate. Interleaving cronologico dei segnali su timeline unificata. | 3 unit-test (vedi sotto) |
| 1.4 | **Smoke test E2E**: `run_portfolio_backtest` su SPY/QQQ/IWM 12 mesi deve produrre: ≥1 trade OR skip_reasons loggati (entrambi sono esiti validi — la strategia può non funzionare, ma il portfolio code deve funzionare). | Script `scripts/run_portfolio_12mo.py` (≈30 righe), log in `output/run_portfolio_12mo.log` |

### Unit-test target (4 nuovi → 263 totali)

| Test | Cosa valida |
|---|---|
| `test_four_simultaneous_signals_cap_3_rejects_fourth` | Con 4 entry signals allo stesso timestamp e `max_open_positions=3`, il 4° è in `skip_reasons`. |
| `test_shared_equity_drawdown_reduces_next_trade_size` | Dopo un drawdown del 20%, la size del trade successivo è ridotta proporzionalmente all'equity disponibile, NON all'equity iniziale. |
| `test_empty_symbol_excluded_from_portfolio` | Se uno dei `datasets` è vuoto/`df.empty`, quel simbolo è escluso dal portafoglio senza crash. |
| `test_skip_reasons_logged_for_rejected_trades` | Ogni trade rifiutato ha un motivo esplicito nel campo `skip_reasons`. |

### Decisioni di design (richiedono conferma utente PRIMA di iniziare Sprint 1)

1. **Timeframe-discretizzazione**: tutti i simboli sono 15-min allineati? Default: SI (universum corrente), ma serve conferma per non scoprirlo a Sprint 1 già in corso.
2. **Mark-to-market**: usa `equity_after` dell'ultimo trade chiuso (più semplice) vs prezzo corrente delle posizioni aperte (più corretto ma richiede price lookup). Default proposto: `equity_after`.
3. **Priority di selezione quando >max_open_positions segnali simultanei**: FIFO cronologico (default proposto — più semplice e non richiede magia) vs priority per symbol configurabile.

---

## 5. Sprint 2 — Walk-Forward Analysis (FASE 5 di NEXT_STEPS_PLAN)

**Goal:** sliding-window engine che esegue portfolio backtest su ogni finestra OOS e aggrega metriche solo out-of-sample. **Prerequisito** per Monte Carlo (i trade log OOS sono l'input).

**Dipendenze:** Sprint 1 (Portfolio) ship-ready con trade log cross-symbol OOS.

### Sub-task

| # | Task | Criterio done |
|---|---|---|
| 2.1 | **Creare `backtest/walk_forward.py`** con `walk_forward_windows(datasets, train_months, test_months)`. Sliding-window (default 6mo train / 1mo test). Min 4 finestre OOS. | Modulo + 1 unit-test su `window_count` |
| 2.2 | **`walk_forward_run(cfg)`** → `WFAReport{windows, oos_aggregate, in_sample_aggregate, degradation_pct, symbols}`. Per ogni finestra: esegue `run_portfolio_backtest` sullo slice OOS. Aggrega OOS-only. | 2 unit-test (vedi sotto) |
| 2.3 | **Calcolo `degradation_pct`** per metrica: `oos_metric / in_sample_metric`. Output: dict `{"sharpe": -0.37, "profit_factor": -0.16, "max_dd": +0.44}`. | 1 unit-test |
| 2.4 | **Config-driven defaults** da `config.yaml::walk_forward.*` (parametri già presenti secondo `NEXT_STEPS_PLAN §15`). | Smoke test di default load |
| 2.5 | **No grid search automatica** in questo sprint. La WFA processa UNA sola `cfg` per tutte le finestre. L'utente decide la cfg. | Codepath assente → test assente (verificato manualmente con grep) |

### Unit-test target (3 nuovi → 266 totali)

| Test | Cosa valida |
|---|---|
| `test_walk_forward_window_count` | Con 12 mesi di dati, train=6, test=1, min_windows=4 → almeno 4 finestre generate correttamente. |
| `test_oos_metrics_exclude_in_sample` | Le metriche aggregate in `oos_aggregate` NON contengono dati dei periodi train. |
| `test_degradation_calculation` | `degradation_pct["sharpe"] = oos_aggregate["sharpe"] / in_sample_aggregate["sharpe"]` (correttezza della formula). |

### Decisioni di design

- Symbol resolution: usa `config.yaml::universe.symbols` (default `["SPY", "QQQ", "IWM"]`).
- Fetching: riusa il pattern Slice 3 (preflight credenziali una sola volta).

---

## 6. Sprint 3 — Monte Carlo (FASE 6 di NEXT_STEPS_PLAN)

**Goal:** stress test indipendente dalla strategia sul **PnL % dei trade OOS** aggregati dalla WFA. Produce distribuzione drawdown con guardrail anti-overconfidence.

**Dipendenze:** Sprint 2 (WFA) ship-ready; input = `oos_trades` aggregati.

### Sub-task

| # | Task | Criterio done |
|---|---|---|
| 3.1 | **Creare `backtest/monte_carlo.py`** con `monte_carlo_run(trades: DataFrame, n_simulations=10000, confidence_levels=(5,50,95), seed=None)`. Bootstrap con sostituzione su `pnl_pct` (NON su `equity_after` — preserva indipendenza). | Modulo + 2 unit-test |
| 3.2 | **Calcolo `max_drawdown`** per ogni percorso simulato (running peak → cumulative sum of returns → max DD = max(running_peak - current)). | 1 unit-test |
| 3.3 | **Estrazione percentili** via `numpy.percentile`. Output: `DrawdownDist{percentile_5, percentile_50, percentile_95, mean, n_simulations, n_trades, low_confidence}`. | 1 unit-test |
| 3.4 | **Guardrail**: se `n_trades < 50`, warning esplicito + `low_confidence=True`. NON bloccare (la WFA di 1 mese non produce mai n≥50 trade). | 1 unit-test |
| 3.5 | **Seed deterministico** (`np.random.default_rng(seed)`) per riproducibilità. | 1 unit-test |
| 3.6 | **End-to-end script**: `scripts/demo_portfolio_wfa.py` (output minimale matching NEXT_STEPS_PLAN §11 "MVd"). | Script funzionante + log dimostrativo |

### Unit-test target (5 nuovi → 271 totali)

| Test | Cosa valida |
|---|---|
| `test_bootstrap_produces_n_resampled_paths` | Con `n_simulations=1000`, output ha esattamente 1000 path. |
| `test_max_drawdown_per_path` | `max_drawdown` è ≤ 0 e ≥ -1 (bounded). |
| `test_percentile_extraction` | `percentile_5 ≤ percentile_50 ≤ percentile_95`. |
| `test_low_confidence_flag_below_threshold` | Con n_trades=30, flag è True. Con n_trades=100, flag è False. |
| `test_seeded_run_is_deterministic` | Stesso seed → stesso output (bit-identico). |

---

## 7. Cancellation Gate (al termine Sprint 3)

Dopo lo Sprint 3, l'infrastruttura minima è completa. **NON si procede automaticamente a FASE 7 (Paper Trading)**. Si valuta quantitativamente:

### Domanda del gate

> La strategia mean-reversion produce un **OOS Sharpe ≥ 0** E **Monte Carlo percentile 5 di max-DD ≥ -25%** su **almeno 2 di 3 finestre storiche** (current 2024-2025, prep regime 2022 Q1-Q3, range-bound 2023 Q2-Q3)?

### Esiti possibili

| Esito | Significato | Azione |
|---|---|---|
| **PASS** | La strategia ha edge misurabile in almeno un regime storico train/test OOS | Procedere con FASE 7 (Paper Trading). Pianificare separatamente in `PATH_3_PAPER_TRADING_PLAN.md`. |
| **MARGINAL** | Sharpe OOS positivo ma MC mostra rischio di drawdown > 25% (soglia non sostenibile) | Rivalutare `risk/sizing.py` (size conservative, stop-loss più stretto). Re-run WFA. Se ancora marginal dopo 1 iterazione → FAIL. |
| **FAIL** | Sharpe OOS ≤ 0 OPPURE low_confidence=True in tutte le finestre OPPURE MC max-DD >25% in tutte le finestre | **Abbandonare la thesis mean-reversion intraday su equity-index ETF.** Pivotare a: (i) pairs trading su **universo espanso** (SPY vs XLE, vs DBA, vs FXE); OPPURE (ii) **strategy familia diversa** (momentum, breakout). L'infrastruttura WFA/MC viene riusata per validare la nuova thesis dal giorno 1. |

### Criterio quantitativo (espresso come gate testabile)

```python
# pseudocodice (NON codice reale, è un decision contract)
def cancellation_gate(wfa_report, mc_dist_by_window):
    sharpe_oos = wfa_report.oos_aggregate["sharpe"]
    mc_p5_max_dd = mc_dist_by_window.percentile_5  # negativo

    conditions = [
        sharpe_oos > 0,
        mc_p5_max_dd >= -0.25,
        mc_dist_by_window.low_confidence == False,
    ]

    if all(conditions):
        return "PASS"
    elif sharpe_oos > 0 and not mc_dist_by_window.low_confidence:
        return "MARGINAL"
    else:
        return "FAIL"
```

→ Questo pseudocodice è il **decision contract** del gate. Sarà implementato come unit-test in Sprint 3.

---

## 8. Cross-cutting risks (adattato da NEXT_STEPS_PLAN §10)

### 8.1 CRITICAL — Refactor di `risk/sizing.py` per portfolio

**Azione esplicita:** quando Sprint 1 entra in gioco, il refactor deve essere **verticale** (estrai un nuovo `risk/portfolio.py` con la logica di multi-symbol, NON modificare `apply_position_sizing` per renderlo multi-symbol in-place). Rischio: regressioni sui 259 test esistenti.

**Mitigazione:** mantenere `apply_position_sizing` single-symbol **immutato**; `risk/portfolio.py` chiama `apply_position_sizing(symbol_df, available_equity)` per ogni trade.

### 8.2 Combinatorial explosion nella WFA

3 simboli × 24 finestre (2 anni / 1 mese) × 1 cfg = 72 portfolio backtest. Senza grid search automatica (Sprint 2 §5) è OK. Se in futuro si introduce grid search, sarà problema per Sprint successivi (non Sprint 2).

**Mitigazione Sprint 2:** `walk_forward_run` accetta UNA cfg per tutte le finestre. Niente loop interno di cfg.

### 8.3 Monte Carlo illude confidenza sotto soglia

Con meno di 50 trade, i percentili bootstrap sono statisticamente fragili. Il guardrail `low_confidence=True` (Sprint 3 §6.4) è già in NEXT_STEPS_PLAN §10.3 come "warning non bloccante".

**Mitigazione:** il Cancellation Gate (§7) interpreta `low_confidence=True` come segnale di FAIL — non si procede con Paper Trading sotto soglia.

### 8.4 Tick-vs-vectorized paradigm shift (DEFERRED)

`PaperTrader` richiede ricalcolo incrementale su barra-per-barra. **Non è in PATH 2.** Verrà affrontato in `PATH_3_PAPER_TRADING_PLAN.md` se il Cancellation Gate passa. Hurst resta il caso più lento (~1s per barra) ma è irrilevante per 15-min cadence.

**Mitigazione PATH 2:** nessuna. Paper/Live non in scope.

### 8.5 Single-symbol semantics vs portfolio (rischio regressioni in Sprint 1)

`apply_position_sizing` oggi assume singolo `df['atr']`. Sprint 1.2 introduce `risk/portfolio.py` che accetta `dict[entry_idx → symbol → atr]`. Rischio: `apply_position_sizing` riceve input diversi e rompe i 259 test esistenti.

**Mitigazione:** nuova funzione `apply_portfolio_position_sizing(entry_signal, available_equity, atr)` in `risk/portfolio.py`; `apply_position_sizing` rimane single-symbol e intatto.

---

## 9. Metriche di progresso

| Milestone | Test verdi | Moduli nuovi | Output principale |
|---|---|---|---|
| Baseline (oggi) | 259 | 0 | — |
| Fine Sprint 1 | 263 (+4) | `risk/portfolio.py`, `run_portfolio_backtest` | `output/run_portfolio_12mo.log` |
| Fine Sprint 2 | 266 (+3) | `backtest/walk_forward.py` | `WFAReport` su 12mo |
| Fine Sprint 3 | 271 (+5) | `backtest/monte_carlo.py`, `scripts/demo_portfolio_wfa.py` | `scripts/demo_portfolio_wfa.py --symbols SPY,QQQ,IWM` |
| Cancellation Gate | 271 | — | decision PASS / MARGINAL / FAIL documentata in `analysis/post_path2_decision.md` |

**Traguardo cumulativo (PATH 2 done):** infrastructure minima di validazione strategica. **Qualsiasi strategia futura** può ora essere valutata con rigore OOS + confidence intervals prima di qualsiasi deployment.

---

## 10. Sequenza operativa

```
[Setup]
   └─── pytest tests/ -q   # baseline 259/259 OK
   └─── (opzionale) git checkout -b feature/path-2-validation-infra

[Sprint 1] ~1-2 sessioni
   └─── Confirmare 3 decisioni di design con utente (ask_user)
   └─── Sub-task 1.1 → eseguire regime check 2022 Q1-Q3 + 2023 Q2-Q3
   └─── Sub-task 1.2 → risk/portfolio.py
   └─── Sub-task 1.3 → run_portfolio_backtest
   └─── Sub-task 1.4 → smoke test E2E
   └─── code-reviewer-minimax-m3
   └─── pytest tests/ -q   # 263/263 OK
   └─── git commit -m "feat(backtest): portfolio backtest with shared equity [PATH2-S1]"

[Sprint 2] ~1-2 sessioni
   └─── Sub-task 2.1 → walk_forward_windows
   └─── Sub-task 2.2 → walk_forward_run + WFAReport dataclass
   └─── Sub-task 2.3 → degradation_pct
   └─── Sub-task 2.4 → config defaults
   └─── code-reviewer-minimax-m3
   └─── pytest tests/ -q   # 266/266 OK
   └─── git commit -m "feat(backtest): walk-forward analysis (OOS-only aggregation) [PATH2-S2]"

[Sprint 3] ~1-2 sessioni
   └─── Sub-task 3.1 → monte_carlo_run + DrawdownDist dataclass
   └─── Sub-task 3.2 → max_drawdown per path
   └─── Sub-task 3.3 → percentile extraction
   └─── Sub-task 3.4 → low_confidence guardrail
   └─── Sub-task 3.5 → seed deterministico
   └─── Sub-task 3.6 → scripts/demo_portfolio_wfa.py + run + log
   └─── code-reviewer-minimax-m3
   └─── pytest tests/ -q   # 271/271 OK
   └─── git commit -m "feat(backtest): monte carlo on OOS trade log [PATH2-S3]"

[Cancellation Gate]
   └─── Analizzare risultati WFA OOS Sharpe + MC percentile 5
   └─── Test su 2-3 finestre storiche (current + 2022 bear + 2023 range-bound)
   └─── Documentare esito in analysis/post_path2_decision.md
   └─── Se PASS  → pianificare PATH_3_PAPER_TRADING_PLAN.md
   └─── Se MARGINAL → rivalutare risk/sizing, iterazione
   └─── Se FAIL → abbandono mean-reversion + pivot strategy (vedi §7)
```

---

## 11. Metriche di dettaglio per sprint

| Sprint | Criterio Ship-Ready | Se fallisce |
|---|---|---|
| S1 | 4 unit-test verdi, smoke test E2E produce output OR skip_reasons, nessuna regressione sui 259 baseline | Iterare su sub-task fallito (NON procedere a S2). Se iterazioni > 2, escalation utente. |
| S2 | 3 unit-test verdi, `walk_forward_run` su 12mo produce `WFAReport` con ≥ 4 finestre, nessuna regressione sui 263 | Iterare (vedi sopra). Se OOS Sharpe è NaN per insufficient data, accettabile ma documentare. |
| S3 | 5 unit-test verdi, `scripts/demo_portfolio_wfa.py` end-to-end produce output completo, nessuna regressione sui 266 | Iterare. Se MC percentile_5 è NaN per trade vuoti, è OK ma documentare nel log. |

**Importante**: nessuno di questi sprint richiede che la **strategia** produca risultati positivi. Gli sprint sono sull'**infrastruttura**. I criteri di ship-ready sono sul codice/funzionalità, non sulla strategia.

---

## 12. Defer (esplicito "non in questo piano")

- ❌ **FASE 7 — Paper Trading** (`live/paper.py`). Richiede tick-vs-vectorized paradigm shift + Alpaca real-time + paper account attivo. Trattato in `PATH_3_PAPER_TRADING_PLAN.md` (DA SCRIVERE) solo se Cancellation Gate passa.
- ❌ **FASE 8 — Live Trading** (`live/live.py`). Stessa architettura di Paper + OAuth + sizing reduction. Trattato in `PATH_3_PAPER_TRADING_PLAN.md` o successivo.
- ❌ **Grid search automatica in WFA**. Combinatorial explosion (§8.2). Out of scope finché non esiste almeno UNA cfg che produce Sharpe OOS > 0.
- ❌ **Strategy tuning** di `filters/regime.py`, `signals/entry.py`, `signals/exit.py`. PATH 2 è infrastruttura; tuning è tema separato (PATH 4 o abbandono mean-reversion).
- ❌ **Espansione universo** (XLE, DBA, FXE). Tema del PATH post-FAIL.
- ❌ **Multi-timeframe simultaneo**. NEXT_STEPS_PLAN §12 già lo deferisce.
- ❌ **Modifiche a `risk/sizing.py::apply_position_sizing`**. Resta single-symbol; il multi-symbol è in `risk/portfolio.py`.

---

## 13. References

- `analysis/strategy-fit.md` §10-11 — i 2 diagnostics che hanno motivato PATH 2.
- `NEXT_STEPS_PLAN.md` §5-7 — design dettagliato di Slice 4, WFA, MC (PATH 2 ne è un sottoinsieme operativo).
- `NEXT_STEPS_PLAN.md` §10 — 5 cross-cutting risks (PATH 2 eredita §10.1, §10.2, §10.3, adatta §10.4 e §10.5).
- `BACKTEST_REMEDIATION_PLAN.md` — Sprint 1-3 della remediation (completati, hanno prodotto i diagnostics).
- `IMPLEMENTATION_PLAN.md` §3 — quadro FASE 0-9 ad alto livello.
- `config.yaml::walk_forward.*`, `config.yaml::monte_carlo.*` — parametri pre-configurati da NEXT_STEPS_PLAN.
- `documentation.md` §8, §12.8, §12.9 — filosofia walk-forward + Monte Carlo + esempi di codice.
- `backtest/engine.py` `run_universe_backtest` (Slice 3 già ship-ready, da cui parte Sprint 1).

---

## 14. Design decisions risolte (2026-07-07)

Le 4 decisioni di design sono state risolte dall'utente prima dell'esecuzione (batch ask_user). Le scelte sono vincolanti per il codice e non riapriranno durante gli sprint:

| # | Decisione | Scelta | Implicazione architetturale |
|---|---|---|---|
| 1 | **Branch** | Nuova `feature/path-2-validation-infra` aperta da `master` | PATH 2 vive isolato; la diagnostica resta su `feature/remediation-sprint-1` (referenziata da `analysis/strategy-fit.md` §10-11 e i 2 JSON diagnostici) |
| 2 | **Timeframe-discretizzazione** | Tutti 15-min allineati | Merge outer su timestamp; nessuna discretizzazione custom |
| 3 | **Mark-to-market** | Prezzo corrente posizioni aperte (price lookup) | Curva equity portafoglio **continua** (non stair-step ai trade chiusi). Richiede nuova funzione pura `compute_unrealized_pnl(open_positions, current_bar_prices)` in `risk/portfolio.py` e lookup del `close` per ogni posizione aperta ad ogni barra |
| 4 | **Priority di selezione** | FIFO cronologico (primo arriva, primo served) | I primi N segnali cronologici accettati; i restanti → `skip_reasons='max_positions_reached'` |

**Impatto concreto sul codice di Sprint 1** (per decisione #3 MTM):

- `PortfolioResult.equity` è una curva MTM continua: `equity = settled_equity + sum(unrealized_pnl over open_positions)`. Ad ogni barra del loop, per ogni posizione aperta si fa lookup del `close` corrente e si calcola `unrealized = (current_close - entry_close) * direction * shares`.
- `risk/portfolio.py::compute_unrealized_pnl(open_positions, current_bar_prices)` è una funzione pura (input: dict di posizioni, dict di prezzi correnti; output: float in $).
- I unit-test di Sprint 1 (§4 sub-task 1.3) includono un test MTM dedicato: verificare che `equity` cambia tra due barre consecutive quando c'è una posizione aperta il cui prezzo è variato anche con zero trade nuovi.
- Costo runtime: O(bars × open_positions) lookup. Per i numeri attesi (`bars≈5544`, `open_positions≤3`) è accettabile (≈17k lookup totali).
- Edge case: se il prezzo corrente di un simbolo non è disponibile sulla barra (es. NaN), usa l'ultimo prezzo noto (forward-fill) e marca `mtm_degraded=True` nel PortfolioResult per trasparenza.

**Impatto operativo** (per decisione #1 branch):

- Tutti i commit PATH 2 vanno su `feature/path-2-validation-infra`. Niente merge con `feature/remediation-sprint-1`.
- I commit diagnostici su `feature/remediation-sprint-1` restano dove sono e vengono referenziati da questo piano via path relativi.
- La chiusura del work avviene via `finishing-a-development-branch` o merge diretto a `master` dopo validazione del Cancellation Gate.

---

## 15. Update Sprint 1.1 — Regime Check (2026-07-07)

**Comando eseguito sul branch `feature/path-2-validation-infra` (commit `2fb0a25`):**

```
python scripts/historical_test.py SPY 2022-01-01 2022-09-30  # bear market
python scripts/historical_test.py SPY 2023-04-01 2023-09-30  # range-bound
```

**Risultati:**

| Window | Tipo regime | Barre | regime_ok% | Trades | PF | Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
| 2022 Q1-Q3 | bear | 4.301 | 7.2% | **8** | 0.0000 | −1.9798 | ❌ tutti losing |
| 2023 Q2-Q3 | range | 2.875 | 6.3% | **0** | undef | N/A | ❌ nessun trade |

Aggiungendo questi ai risultati già noti:

| Window | Trades | PF | Sorgente |
|---|---|---|---|
| 2024-10 → 2025-09 (Sprint 1) | 24 | 0.40 | BACKTEST_REMEDIATION_PLAN §2 |
| 2023-10 → 2024-09 (cross-val) | 0 | undef | BACKTEST_REMEDIATION_PLAN §2 |
| 2024-10 → 2025-09 (Step 1.6) | 11 | 0.013 | BACKTEST_REMEDIATION_PLAN §2 |
| 2022 Q1-Q3 (bear) | 8 | 0.0000 | PATH 2 §15 |
| 2023 Q2-Q3 (range) | 0 | undef | PATH 2 §15 |

→ **La strategia mean-reversion ha mostrato 0-24 trade in 5 di 5 finestre storiche testate**, con PF<1.0 in ogni finestra che ha prodotto ≥1 trade. regime_ok pass rate è 6-9% in tutti i window.

**Implicazione architetturale:**

Il piano prevedeva (Sprint 1 §1 "Contingency") che se N<50 in entrambi i window 2022/2023, l'infrastruttura Sprint 1-3 venga testata con **mock DataFrame** (generati da una distribuzione nota di trade logs, oppure carry-trade su portafoglio sintetico). Questa contingency si applica: Sprint 1.2-1.4 può procedere con mock data.

**Implicazione strategica (sull'esito atteso del Cancellation Gate):**

Il Cancellation Gate (§7) richiede Sharpe OOS > 0 E MC percentile 5 ≥ −25% E `low_confidence=False` su almeno 2 di 3 finestre storiche. Data la scarsità cronica di trade (<50 per finestra storica), WFA produrrà sempre `low_confidence=True` per la strategia mean-reversion corrente. → **Il gate è strutturalmente destinato a FAIL** per la strategia corrente.

Questo non è un fallimento di PATH 2 ma una **conferma quantitativa** della diagnosi in `analysis/strategy-fit.md` §1: la strategia non ha edge misurabile in nessuna finestra storica.

**Implicazione su PATH 2 ROI:**

L'infrastruttura costruita (Portfolio + WFA + MC) rimane **strategy-agnostic e riutilizzabile integralmente** per la prossima famiglia di strategie. PATH 2 è un investimento sulla capacità di validazione, non sulla strategia attuale.

**Decisione pendente per utente (sospesa fino a risposta):**

Procedere con Sprint 1.2-1.4 (mock DataFrame, infrastructure-only) o pivotare anticipatamente a una nuova famiglia di strategie (momentum / breakout / pairs su universo espanso)? Le tre opzioni operative sono documentate nei followup di sessione.

---

*Questo piano è operativo per i prossimi 3 sprint. Si aggiorna con i risultati del Cancellation Gate al termine di Sprint 3 e le decisioni di pivot se necessario.*

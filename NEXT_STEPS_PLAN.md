# Piano dei Prossimi Step — quant_trd

**Data:** 2026-07-07
**Branch:** `mean_reversion`
**Stato test:** 189 verdi (12 file)
**Documenti di riferimento:** `IMPLEMENTATION_PLAN.md` (piano di fase), `FIX_PLAN.md` (review del 2026-07-06), `documentation.md` (specifica strategia)

> Questo documento è operativo: dice **cosa fare nella prossima iterazione**, non cosa è stato fatto. Per il quadro di fase complessivo vedere `IMPLEMENTATION_PLAN.md`. Per il quadro dei fix puntuali già applicati vedere `FIX_PLAN.md`.

---

## 1. Stato corrente (snapshot)

| Fase | Modulo | Stato |
|---|---|---|
| FASE 0 — Infrastruttura | `data/`, `utils/config.py`, `utils/metrics.py` | ✅ Completa |
| FASE 1 — Indicatori + Filtro regime | `indicators/`, `filters/regime.py` | ✅ Completa |
| FASE 2 — Segnali ingresso/uscita | `signals/entry.py`, `signals/exit.py` | ✅ Completa |
| FASE 3 — Position sizing | `risk/sizing.py` | ✅ Completa |
| **FASE 4 Slice 1** — Engine single-symbol | `backtest/engine.py::run_backtest` | ✅ Completa |
| **FASE 4 Slice 2** — Wrapper + latenti | `backtest/engine.py::run_backtest_for_symbol`, guardie `df.empty` | ✅ Completa (189 test) |
| **Slice 3** — Universe batch | da scrivere | ⏳ Imminente |
| **Slice 4** — Portfolio aggregation | da scrivere | ⏳ Bloccante per WFA |
| **FASE 5** — Walk-forward | `backtest/walk_forward.py` mancante | ⏳ |
| **FASE 6** — Monte Carlo | `backtest/monte_carlo.py` mancante | ⏳ |
| **FASE 7** — Paper trading | `live/paper.py` mancante | ⏳ |
| **FASE 8** — Live trading | `live/live.py` mancante | ⏳ |

**Slice 2 recap (l'ultima slice completata):**
- `run_backtest_for_symbol(symbol, cfg)` con preflight credenziali + `_fetch_bars(symbol, n_bars)` size-aware
- Guardia `if df.empty:` sia su `build_equity_curve` che su `build_pct_curve` (Series 1-elemento NaT-ancorata)
- 6 test in `TestRunBacktestForSymbol` di cui l'ultimo (`test_run_backtest_for_symbol_locks_wrapper_cfg_merge_contract`) blocca il contratto di cfg-merge end-to-end
- `atr_window` confermato whitelisted ma non popolato da `config.yaml` → contratto di merge documentato nel test

---

## 2. Principi guida delle prossime slice

1. **Slice discipline** — una slice verticale alla volta, ship-ready (test in verde + code-reviewer approvato) prima di passare alla successiva.
2. **Sequenza stretta** — Slice 3, Slice 4, WFA, MC sono in serie; **non parallelizzarli**. Paper/Live possono partire in parallelo tra loro ma solo dopo Slice 4.
3. **Niente scope creep** — ogni slice ha un perimetro minimo ship-ready. Niente "approfittiamo per aggiungere X".
4. **Ogni slice lascia la codebase uno stato più pulito di prima** — guardie, test, docstring aggiornate. Mai "fixato dopo".
5. **Test count come metrica di progresso** — ogni slice deve portare il totale a un numero target (vedi tabella §3).

---

## 3. Slice table (il piano operativo)

| ID | Deliverable | Modulo/funzione | Dipendenze | Ship-readiness criteria | Test target |
|---|---|---|---|---|---|
| **Slice 3** | `run_universe_backtest(symbols, cfg)` → `Dict[str, BacktestResult]` | `backtest/engine.py` (nuova export) | Slice 2 (`run_backtest_for_symbol`) | Esegue `run_backtest_for_symbol` per ogni simbolo. Salta (warn, non crash) simboli che restituiscono `df.empty`. Ordine del dict preservato. Nessuna aggregazione di portafoglio (è Slice 4). Credenziali già preflightate al primo simbolo, non ad ogni chiamata. | 195 test (3 nuovi: empty-symbol skip, partial-empty batch, dict-ordering invariant) |
| **Slice 4** | `run_portfolio_backtest(datasets: Dict[str, pd.DataFrame])` → `PortfolioResult` con curva di equity portafoglio + log trade aggregato | `backtest/engine.py` + refactor mirato di `risk/sizing.py` e `signals/exit.py` | Slice 3; richiede refactor del loop di sizing (vedi §6 rischio CRITICAL) | Interleaving cronologico dei segnali di tutti i simboli su un'unica timeline. Equity pool condiviso tra simboli. `max_open_positions=N` rispettato a livello di portafoglio (se 4 segnali simultanei con cap=3, il 4° viene scartato). PnL di ogni trade dimensionato sull'equity disponibile al momento dell'entry, NON sull'equity iniziale. | 205 test (4 nuovi: cap-rifiuto al 4°, shared-equity drawdown impatta prossimo trade, empty-symbol escluso da portafoglio, determinismo con seed) |
| **FASE 5** | `walk_forward_run(cfg, symbols)` → `WFAReport` | `backtest/walk_forward.py` (nuovo) | Slice 4 (la WFA opera sul portfolio, non sul singolo simbolo) | Iteratore sliding-window (train 6 mesi → test 1 mese) su simboli di `config.yaml::universe.symbols`. Esegue `run_portfolio_backtest` su ogni finestra test. Aggrega SOLO metriche OOS. Ritorna `in_sample_metrics`, `oos_metrics`, `degradation_pct`, lista di trade per finestra. Grid search parametri limitata a `cfg` di input — niente ottimizzazione automatica su tutta la griglia in questa iterazione. | 215 test (3 nuovi: split-points corretti, aggregazione OOS-only, determinismo sezioni temporali) |
| **FASE 6** | `monte_carlo_run(wfa_report)` → `DrawdownDist` | `backtest/monte_carlo.py` (nuovo) | FASE 5 (input = trade log OOS di WFA) | Bootstrap con sostituzione sul PnL% delle trade OOS aggregate. 10.000 simulazioni (configurabile). Calcola `max_drawdown` per ogni percorso simulato. Ritorna percentile 5/50/95 di max-DD + perdita attesa per trade. **Guardrail: se `len(trade_log) < 50`, warning esplicito + percentile marcato come "low-confidence" nel report.** | 220 test (3 nuovi: zero-trade safe exit, determinismo con seed, guardrail attivo sotto soglia) |
| **FASE 7** | `PaperTrader` che gira la stessa pipeline `clean→indicators→regime→entry→exit` su barre real-time Alpaca con ordini paper | `live/paper.py` (nuovo) | Slice 4 (logica pipeline già factorizzata); `scripts/demo_portfolio_wfa.py` come reference run per calibrazione | Loop a cadenza fissa (15 min di default). Mantiene DataFrame trailing con le ultime N barre. Applica la pipeline. Per ogni entry, invia ordine market su Alpaca paper API. Log JSON per ogni trade (timestamp, symbol, direction, entry/exit price, motivo uscita). Espone `paper_vs_backtest_metrics()` che paragona le metriche live vs quelle di WFA. | 230 test (4 nuovi: trailing-window update, doppio-entry prevention, mock WS, metric comparison output) |
| **FASE 8** | `LiveTrader` con scaling prudente (50% size prime 4 settimane) | `live/live.py` (nuovo) | FASE 7 (riusa tutta l'infrastruttura paper, cambia solo l'endpoint Alpaca) | Stessa architettura di `PaperTrader`. Flag `live_mode=True` che attiva: riduzione size, halt-on-degradation checks settimanali (confronta Sharpe live vs Sharpe WFA, halt se degrada > 30%), autenticazione OAuth + refresh token. | 235 test (3 nuovi: size-scaling factor corretto, halt-on-degradation trigger, OAuth refresh stub) |

---

## 4. Slice 3 — Dettaglio operativo

**Scope minimo:**

```python
# backtest/engine.py
def run_universe_backtest(
    symbols: List[str],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    n_bars: int = 1500,
    on_symbol_error: Literal["skip", "raise"] = "skip",
) -> Dict[str, BacktestResult]:
    """Esegui backtest su multipli simboli.

    Returns
    -------
    dict[str, BacktestResult]
        Mappa simbolo → risultato. Simboli che producono df.empty
        o errore di rete sono OMESSI se on_symbol_error="skip",
        altrimenti l'errore si propaga al chiamante.
    """
```

**Sub-task:**

| # | Task | Criterio done |
|---|---|---|
| 3.1 | Funzione `run_universe_backtest` con loop seriale su `run_backtest_for_symbol` | Compila + smoke test |
| 3.2 | Gestione `df.empty` per simbolo (warn + skip) — riusa la guardia già in `build_equity_curve` | Test `test_universe_with_one_invalid_symbol_returns_n_minus_1_results` |
| 3.3 | Preflight credenziali UNICO (non per simbolo) — verificare prima dell'inizio del loop | Test `test_universe_fails_fast_when_missing_credentials` |
| 3.4 | `on_symbol_error` opzionale per sollevare invece di skippare | Test `test_universe_propagates_runtime_error_when_on_symbol_error_raise` |
| 3.5 | Ordine dict preservato (`dict` Python ≥ 3.7) | Test `test_universe_preserves_input_order` |

**Esplicitamente NON in Slice 3:**
- Aggregazione portafoglio (`Slice 4`)
- Correlazione cross-symbol
- Allocazione equity condivisa
- Parallelismo (vettoriale o multiprocessing)

---

## 5. Slice 4 — Dettaglio operativo

**Scope minimo:**

```python
@dataclass
class PortfolioResult:
    symbol_results: Dict[str, BacktestResult]
    equity: pd.Series                    # equity portafoglio aggregato
    trades: pd.DataFrame                  # trade log aggregato cross-symbol
    skip_reasons: Dict[str, str]          # perché un trade è stato scartato
    metrics: Dict[str, Any]
    config_used: Dict[str, Any]

def run_portfolio_backtest(
    datasets: Dict[str, pd.DataFrame],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    max_open_positions: int = 3,
) -> PortfolioResult: ...
```

**Sub-task:**

| # | Task | Criterio done |
|---|---|---|
| 4.1 | Estrarre segnali raw da ogni dataset (post `generate_entry_signals`) | Helper `extract_signals(datasets)` |
| 4.2 | Interleaving cronologico dei segnali su una timeline unificata | Test `test_signals_interleaved_chronologically` |
| 4.3 | Loop portafoglio cronologico: per ogni bar, controlla segnali pending, applica `max_open_positions` cap | Test `test_four_simultaneous_signals_with_cap_3_rejects_fourth` |
| 4.4 | Equity pool condiviso (NON equity iniziale per simbolo) | Test `test_shared_equity_drawdown_reduces_next_trade_size` |
| 4.5 | Log strutturato di trade saltati (`skip_reasons`: "max_positions_reached", "regime_not_ok", "insufficient_equity") | Test `test_skip_reasons_logged_for_rejected_trades` |
| 4.6 | Curva equity portafoglio = unione temporale delle equity per-simbolo, mark-to-market sulle posizioni aperte | Test `test_portfolio_equity_curve_aggregation` |

**Decisioni di design da confermare prima di iniziare Slice 4** (vedi anche §6):

1. **Timeframe-discretizzazione:** tutti i simboli sono 15-min allineati? Se sì, basta un merge su timestamp. Se no (es. SPY chiude presto, futures 24h), serve discretizzazione comune.
2. **Mark-to-market:** per le posizioni aperte tra un exit e un altro, l'equity portafoglio usa l'`equity_after` dell'ultimo trade chiuso (più semplice) oppure il prezzo corrente della posizione aperta (più corretto ma richiede price lookup)?
3. **Priority di selezione quando >max_open_positions segnali:** FIFO cronologico? Priorità per symbol configurabile? Sharpe-priority? Default consigliato: cronologico (più semplice e non richiede magia).

→ Porre queste 3 domande all'utente prima di iniziare Slice 4 (uso `ask_user`).

---

## 6. FASE 5 — Walk-forward analysis

**Scope minimo:**

```python
@dataclass
class WFAWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    in_sample_metrics: Dict[str, Any]
    oos_metrics: Dict[str, Any]
    oos_trades: pd.DataFrame

@dataclass
class WFAReport:
    windows: List[WFAWindow]
    oos_aggregate: Dict[str, Any]
    in_sample_aggregate: Dict[str, Any]
    degradation_pct: Dict[str, float]
    symbols: List[str]

def walk_forward_run(
    cfg: Dict[str, Any],
    *,
    train_months: int = 6,
    test_months: int = 1,
    min_windows: int = 4,
) -> WFAReport: ...
```

**Sub-task:**

| # | Task | Criterio done |
|---|---|---|
| 5.1 | Helper `walk_forward_windows(datasets, train_months, test_months)` — sliding-window su timeline portafoglio | Test `test_walk_forward_window_count` |
| 5.2 | Esecuzione `run_portfolio_backtest` su ogni finestra OOS | Smoke test (chiamata effettiva) |
| 5.3 | Aggregazione metriche OOS-only (mai mischiare train+test) | Test `test_oos_metrics_exclude_in_sample` |
| 5.4 | Calcolo `degradation_pct` per metrica (OOS ÷ InSample) | Test `test_degradation_calculation` |
| 5.5 | Config da `config.yaml::walk_forward.*` (parametri default) | Smoke test di default load |

**Decisione di design:**
- La WFA usa UNA singola `cfg` per tutte le finestre. Niente grid search automatica in questa iterazione (vedi §10 deferred).

---

## 7. FASE 6 — Monte Carlo

**Scope minimo:**

```python
@dataclass
class DrawdownDist:
    percentile_5: float
    percentile_50: float
    percentile_95: float
    mean: float
    n_simulations: int
    n_trades: int
    low_confidence: bool   # True se n_trades < 50

def monte_carlo_run(
    trades: pd.DataFrame,
    *,
    n_simulations: int = 10_000,
    confidence_levels: Tuple[int, ...] = (5, 50, 95),
    seed: Optional[int] = None,
) -> DrawdownDist: ...
```

**Sub-task:**

| # | Task | Criterio done |
|---|---|---|
| 6.1 | Bootstrap con sostituzione su `pnl_pct` (o `pnl_pct_slip`) delle trade OOS | Test `test_bootstrap_produces_n_resampled_paths` |
| 6.2 | Calcolo `max_drawdown` per ogni percorso | Test `test_max_drawdown_per_path` |
| 6.3 | Percentili (numpy) | Test `test_percentile_extraction` |
| 6.4 | Guardrail `low_confidence=True` se `len(trades) < 50` | Test `test_low_confidence_flag_below_threshold` |
| 6.5 | Seed deterministico | Test `test_seeded_run_is_deterministic` |

**Attenzione:** non bootstrap su `equity_after` direttamente (perdita di indipendenza). Usa SEMPRE i ritorni per-trade.

---

## 8. FASE 7 — Paper trading

**Scope minimo:**

```python
# live/paper.py
class PaperTrader:
    def __init__(self, symbols: List[str], cfg: Dict[str, Any]): ...
    def on_bar(self, bar: Dict[str, Any]) -> None: ...
    def run_for_one_session(self) -> List[Dict[str, Any]]: ...
    def paper_vs_backtest_metrics(self) -> Dict[str, Any]: ...
```

**Sub-task:**

| # | Task | Criterio done |
|---|---|---|
| 7.1 | Refactor della pipeline (estrai da `run_backtest` le fasi `clean→indicators→regime→entry→exit`) in funzioni pure synchronized con un trailing DataFrame | Test `test_pipeline_incremental` |
| 7.2 | Adapter Alpaca WebSocket → `on_bar(bar)` callback | Test con mock WS che emette N barre |
| 7.3 | Double-entry prevention (no nuovo trade se già in posizione su quel simbolo) | Test `test_no_double_entry_on_same_symbol` |
| 7.4 | Order submission via Alpaca paper trading API (con dryrun mode per test) | Smoke test in dryrun mode |
| 7.5 | Trade log JSON (timestamp, symbol, direction, entry/exit, reason) strutturato in `output/paper_trades.jsonl` | Test `test_trade_log_json_structure` |
| 7.6 | `paper_vs_backtest_metrics()` paragona win rate / profit factor / Sharpe live vs WFA OOS | Test della shape dell'output |

**Paradigm shift:** la pipeline attuale è **vettoriale** (DataFrame intero). Paper/Live richiede **tick-incremental** (compute on trailing window). Per evitare di riscrivere tutti gli indicatori, il pattern consigliato è: **mantieni un DataFrame trailing di 300 barre**, ricalcola gli indicatori sull'intero trailing window ogni nuovo bar. È O(N × W) per indicatore dove W è la finestra — accettabile per 15-min.

---

## 9. FASE 8 — Live trading

**Scope minimo:** `live/live.py::LiveTrader` che eredita tutto da `PaperTrader` e aggiunge:
- `live_mode=True` flag
- `size_scale=0.5` per le prime 4 settimane (configurabile)
- `halt_on_degradation` check settimanale (Sharpe live vs Sharpe WFA, halt se degrada > 30%)
- OAuth + refresh token (Alpaca richiede questo, non più API key semplici come il paper account)

**Sub-task:**

| # | Task | Criterio done |
|---|---|---|
| 8.1 | Implementazione `size_scaling_factor(weeks_since_start)` → 0.5 → 1.0 linear su 4 settimane | Test `test_size_scaling_factor_curve` |
| 8.2 | Halt-on-degradation check che confronta Sharpe running (ultimi 30 trade) vs WFA baseline | Test `test_halt_triggered_when_sharpe_degrades_30pct` |
| 8.3 | Auth refresh (OAuth) — stub minimo sufficiente, non implementare flusso completo | Test `test_oauth_refresh_called_before_expiry` |

**Vincolo operativo:** FASE 8 viene avviata SOLO DOPO aver completato 4-6 settimane di paper trading positivo (criterio: scostamento < 15% tra metriche paper e metriche WFA OOS).

---

## 10. Cross-cutting risks (da affrontare SUBITO, prima di Slice 3)

### 10.1 CRITICAL — Slice 4 richiede un refactor di `risk/sizing.py`

Il loop di `apply_position_sizing` oggi assume **un singolo dataset** con il suo `df['atr']`. Quando Slice 4 entrerà in gioco, serve:
- Equity condiviso tra simboli → il loop `for i in range(n)` diventa un loop `for bar in timeline: check signals across all symbols; open trades respecting cap; size using shared equity`
- Marcatura a mercato delle posizioni aperte tra un exit e l'altro → serve un meccanismo di "posizione corrente" che non esiste oggi

**Azione esplicita:** quando arriverà Slice 4, il refactor deve essere **verticale** (estrai un nuovo `risk/portfolio.py` con la logica di multi-symbol, NON modificare `apply_position_sizing` per renderlo multi-symbol in-place). Slice 3 invece non tocca il sizing — si limita a iterare la single-symbol pipeline.

### 10.2 Combinatorial explosion nella WFA

3 simboli × 24 finestre (2 anni / 1 mese) × 1 cfg = 72 backtest. Se si introduce grid search anche minima (es. 5 valori per 3 parametri = 125 combinazioni) si arriva a ~9000 backtest. Alpaca API fetching deve essere cached localmente o Slice 3 deve permettere di passare DataFrame già fetchati (quest'ultima è la strada giusta).

→ **Slice 3 API design:** accettare sia `symbols: List[str]` (fetch da Alpaca) sia `datasets: Dict[str, pd.DataFrame]` (già fetchati, riusabile in WFA).

### 10.3 Monte Carlo illude confidenza sotto soglia

Con meno di 50 trade, i percentili bootstrap sono statisticamente fragili. Risposta onesta: marcare come `low_confidence=True` nel dataclass result, NON bloccare l'esecuzione (altrimenti la WFA di 1 mese non produce mai un MC utile).

→ **Guardrail implementato come warning, non come errore.**

### 10.4 Tick-vs-vectorized paradigm shift

La pipeline `indicators/pipeline.py` lavora su DataFrame interi via rolling windows. Paper/Live richiedono **ricalcolo incrementale**. Non tutti gli indicatori si aggiornano facilmente in modo incrementale (Hurst è il caso peggiore).

→ **Strategia:** mantieni un DataFrame trailing di 300 barre, ricalcola tutto ogni nuovo bar. È O(N × W) ma per 15-min è accettabile (1 calcolo ogni 15 min). Hurst resta lento — documentare il costo.

### 10.5 Single-symbol ≠ portfolio semantics nel sizing

`risk/sizing.py::apply_position_sizing` oggi **accetta un singolo `df`** e usa `df['atr'].iloc[entry_idx]`. In Slice 4 serve una variante che accetti un `dict[entry_idx → symbol → atr]` oppure un DataFrame multi-symbol con colonna `atr`. Decidere la forma in anticipo per non duplicare la logica.

---

## 11. Minimal Viable Demo (MVd) — il traguardo visibile

A fine FASE 6 (Monte Carlo), il progetto ha UN script `scripts/demo_portfolio_wfa.py` che dimostra end-to-end:

```bash
$ python scripts/demo_portfolio_wfa.py --symbols SPY,QQQ,IWM --train-months 6 --test-months 1
```

Output atteso (formato semplificato):

```
=== Mean Reversion Intraday — Portfolio WFA Demo ===
Symbols: SPY, QQQ, IWM   Train: 6mo   Test: 1mo   Windows: 24

In-Sample aggregate (avg across train windows):
  Sharpe:  1.82    Profit Factor:  1.45    Max DD: -8.2%

Out-of-Sample aggregate (avg across test windows, 24 windows):
  Sharpe:  1.14    Profit Factor:  1.22    Max DD: -11.8%

OOS Degradation:
  Sharpe:        -37.4%   (>20% tolerance ≈ param overfitting risk ⚠️)
  Profit Factor: -15.9%   (within tolerance ✓)
  Max DD:        +43.9%   (worse than tolerance — expected)

Monte Carlo on OOS trade log (n=487 trades, 10k sims):
  Max DD percentile 5:  -19.4%
  Max DD percentile 50: -12.1%
  Max DD percentile 95: -6.3%
  Low confidence: False (n=487 ≥ 50 ✓)

Recommendation: Sanity-check the Sharpe degradation. If -37% persists across
different OOS seeds, consider tightening regime_filter parameters or running
a mini-grid on a few promising params.
```

Questo script è l'output principale da FASE 6; tutto ciò che viene dopo (Paper, Live) dipende da questo MVd che funzioni.

---

## 12. Defer (esplicito "non in questo piano")

Per evitare scope creep, le seguenti funzionalità sono **esplicitamente fuori perimetro** fino a nuova pianificazione:

- ❌ Grid search automatica in WFA (eseguiamo UNA cfg per finestra, l'utente decide la cfg)
- ❌ Multi-timeframe simultaneo (15-min E 5-min nella stessa run) — il `secondary` in config resta commentato fino a quando non serve
- ❌ Settore-correlazione cap (escludi APERTURA se 3 energy stock sono già in posizione) — Slice 4+ forse
- ❌ Frazionamento Kelly live (Slice 4 usa 1% rule costante, Kelly opzionale da cfg)
- ❌ Order types diversi (limit, stop) — solo market orders per ora
- ❌ Time-of-day filter orari (prime/ultime 30 min di sessione) — rilevante per live ma non ancora in backtest
- ❌ Backtrader come motore alternativo — `run_backtest` è la nostra pipeline custom, backtrader resta in `requirements.txt` ma non è integrato
- ❌ Earnings calendar / event filter — la documentazione lo menziona ma è fuori ambito per le prossime 6 slice
- ❌ Multi-currency / forex / futures — universum è `us_equity` per le prossime 6 slice

---

## 13. Metriche di progresso complessivo

| Milestone | Test verdi | Moduli esistenti |
|---|---|---|
| Slice 2 (raggiunto) | 189 | 8 (data×2, indicators×7, filters×1, signals×2, risk×1, utils×2, backtest×1) + 12 file di test |
| Fine Slice 3 | ~195 | + `run_universe_backtest` in `backtest/engine.py` |
| Fine Slice 4 | ~205 | + `run_portfolio_backtest` in `backtest/engine.py` (+ nuovo `PortfolioResult`) |
| Fine FASE 5 | ~215 | + `backtest/walk_forward.py` (+ `WFAReport`, `WFAWindow`) |
| Fine FASE 6 | ~220 | + `backtest/monte_carlo.py` (+ `DrawdownDist`) + `scripts/demo_portfolio_wfa.py` |
| Fine FASE 7 | ~230 | + `live/paper.py` (+ `PaperTrader`) |
| Fine FASE 8 | ~235 | + `live/live.py` (+ `LiveTrader`) |

**Traguardo di deployment** (FASE 8 done + 4-6 settimane paper positive + 1 mese live con 50% size) = trading live effettivo su capitale ridotto.

---

## 14. Note operative

1. **Per ogni slice** che si apre, il workflow è sempre:
   - `write_todos` per i sub-task dello slice
   - Implementazione
   - Validazione parallela: `py_compile` + `pytest` (target slice) + `visual_check_sizing` + `code-reviewer-minimax-m3`
   - Fix eventuali findings del reviewer
   - Sommario + 3 followup
2. **Three-required-fix policy:** ogni finding del reviewer marcato Required viene applicato prima di marcare lo slice done. Findings Facoltativi/FYI possono essere differiti allo slice successivo (se rilevanti) o abbandonati.
3. **Slice 3 può partire SUBITO** — non ha dipendenze non soddisfatte.
4. **Slice 4 richiede decisioni di design upfront** (vedi §5). Porre le 3 domande all'utente prima di iniziare.
5. **FASE 5/6/7/8** richiedono Slice 4 done.

---

## 15. Riferimenti interni

- `IMPLEMENTATION_PLAN.md` §3 — quadro FASE 0-9 ad alto livello
- `FIX_PLAN.md` §5 — sprint già completati (Sprint 1 CRITICAL, 2 MEDIUM, 3 LOW)
- `backtest/__init__.py` docstring — roadmap Slice 1-4 verbatim, confermato dal codice
- `config.yaml::walk_forward.*` — parametri WFA configurati
- `config.yaml::monte_carlo.*` — parametri MC configurati
- `config.yaml::live.*` — parametri paper/live configurati
- `documentation.md` §8 — filosofia walk-forward + Monte Carlo + costi realistici
- `documentation.md` §10 — checklist pre-live delle 9 voci

---

*Questo piano è operativo per le prossime 6 iterazioni. Si aggiorna alla fine di ogni slice con i risultati effettivi (test count raggiunto, finder del reviewer differiti, slip della sequenza).*

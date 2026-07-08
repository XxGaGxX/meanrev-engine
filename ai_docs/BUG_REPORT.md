# Bug Report — Mean Reversion Intraday Backtest

**Date:** 2026-07-07  
**Backtest:** SPY, 1500 barre 15-min, Alpaca paper account, realistic-fill contract  
**Test Suite:** 201 test, tutti passati

---

## Riepilogo Backtest

| Metrica | Valore |
|---|---|
| Barre fetchate | 3.712 (1.334 dopo pipeline) |
| Regime OK | 213 barre (16.0%) |
| Segnali generati | 7 long, 9 short |
| Trade eseguiti | 7 (9 segnali skippati per overlap) |
| Final equity | $9.948,01 (-0,52%) |
| Win rate | 42,86% (3W / 4L) |
| Profit factor | 0,51 |
| **Sharpe ratio** | **−22,68** ⚠️ |
| **Sortino ratio** | **−147,70** ⚠️ |
| Max drawdown | −0,73% |
| Exit: SL / TP / open_gap_sl | 4 (57%) / 3 (43%) / 0 |

---

## Bug #1 — Sharpe/Sortino calcolati su equity curve sparsa

**Severità:** 🔴 CRITICAL  
**File:** `utils/metrics.py::calculate_all_metrics` (righe 128-141)  
**File:** `backtest/engine.py::run_backtest` (righe 175-183)

### Descrizione

`calculate_all_metrics` calcola Sharpe e Sortino così:

```python
periodic_returns = equity.pct_change().dropna()
metrics["sharpe_ratio"] = sharpe_ratio(periodic_returns, periods_per_year=periods_per_year)
```

Ma `equity` è costruita da `build_equity_curve`, che produce una Series con **solo N+1 punti** (1 start + N trade exit), non una curva per-bar. Quando fai `pct_change()` su questa Series con un DatetimeIndex di 1.334 barre, ottieni:

- **~1.327 valori = 0.0** (equity piatta tra un trade e l'altro)
- **~7 valori = salti reali** (i trade)

Il `mean()` di questi ritorni è ~0 (dominato dagli zeri), la `std()` è minuscola, e annualizzando con `np.sqrt(5544)` ottieni rapporti astronomicamente negativi senza alcun significato finanziario.

Esempio concreto dal backtest:
```
Equity diff mean: ~0.000000 (dominato da 1327 zeri)
Equity diff std:  ~0.000001 (minuscola)
Sharpe annualized = mean/std * sqrt(5544) ≈ −22.68
Sortino annualized = mean/downside_std * sqrt(5544) ≈ −147.70
```

### Fix proposto

Due opzioni:

**Opzione A (minima):** Calcolare Sharpe/Sortino sui trade return, non sull'equity curve. Passare `pnl_pct_slip` (o `pnl_pct`) direttamente a `sharpe_ratio()` con `periods_per_year` = numero medio di trade all'anno.

```python
# In calculate_all_metrics o in run_backtest:
if periods_per_year is not None and len(trade_returns) > 1:
    metrics["sharpe_ratio"] = sharpe_ratio(trade_returns, periods_per_year=periods_per_year)
    metrics["sortino_ratio"] = sortino_ratio(trade_returns, periods_per_year=periods_per_year)
```

**Opzione B (completa):** Costruire una equity curve mark-to-market per-bar (vedi Bug #4), poi calcolare Sharpe/Sortino sui ritorni per-bar di quella curva.

**Raccomandazione:** Opzione A subito (una riga da cambiare), Opzione B come enhancement strutturale futuro.

---

## Bug #2 — Regime filter troppo restrittivo

**Severità:** 🟠 HIGH  
**File:** `filters/regime.py::apply_regime_filter`  
**File:** `config.yaml` (blocco `regime_filter`)

### Descrizione

Il filtro regime combina tre condizioni AND:

1. `adx < adx_threshold` (default: 22)
2. `hurst < hurst_threshold` (default: 0.45)
3. `atr_rel_z < atr_relative_std_threshold` (default: 2.0)

Con i default di produzione, su SPY (che è fortemente trend-following nei periodi recenti), la copertura `regime_ok` è **vicina allo 0%**. Anche con gli override permissivi del demo (ADX 30, Hurst 0.6, ATR 3.0), la copertura è solo del **16%** (e scende allo 0.8% su finestre leggermente diverse).

Su 1.500 barre (circa 68 giorni di trading), il regime filter lascia passare solo ~213 barre, e i segnali che si generano sono concentrati in cluster. Questo rende la strategia essenzialmente inutilizzabile senza override estremi.

### Analisi delle componenti

Il collo di bottiglia principale è probabilmente **Hurst**: su dati intraday a 15 minuti, l'esponente di Hurst tende a fluttuare intorno a 0.5 (random walk), non a scendere sotto 0.45. La condizione `hurst < 0.45` è molto stringente per un timeframe così corto.

### Fix proposto

1. **Rilassare Hurst threshold** nel config.yaml: portare `hurst_threshold` da 0.45 a 0.55, o rimuovere del tutto la condizione Hurst e tenerla solo come metrica diagnostica
2. **Aggiungere diagnostica per-componente** in `apply_regime_filter`: loggare quante barre falliscono ciascuna delle tre condizioni separatamente, così da identificare il collo di bottiglia
3. **Considerare una versione "soft"** del regime filter dove le tre condizioni sono pesate anziché AND binarie

---

## Bug #3 — Signal overlap eccessivo (56% di segnali persi)

**Severità:** 🟠 MEDIUM  
**File:** `signals/exit.py::simulate_all_trades` (righe 203-225)

### Descrizione

`simulate_all_trades` applica un vincolo no-overlap: se un segnale fire mentre un trade precedente è ancora aperto (`pos <= last_exit_pos`), il segnale viene skippato.

Con `max_bars=25`, un trade può durare fino a 25 barre. Considerando che le barre `regime_ok` sono solo il 16% del totale (213 su 1.334), e che i segnali tendono a concentrarsi nei pochi periodi favorevoli, l'overlap è inevitabile:

- 16 segnali generati
- 7 trade eseguiti
- **9 segnali (56%) persi per overlap**

### Fix proposto

1. **Ridurre `max_bars`** nel config.yaml da 25 a 10-15. Trade più brevi = meno overlap. Il trade-off è che alcuni trade potrebbero essere chiusi per time-stop anziché TP/SL.
2. **Aggiungere una metrica `signals_skipped`** nel `BacktestResult` per rendere visibile il fenomeno
3. **Opzionale:** permettere posizioni multiple sullo stesso asset (ma questo richiede logica di portfolio aggiuntiva che è fuori scope per FASE 4)

---

## Bug #4 — Drawdown sottostimato (solo a trade exit)

**Severità:** 🟡 MEDIUM  
**File:** `risk/sizing.py::build_equity_curve` (righe 228-268)

### Descrizione

`build_equity_curve` costruisce la curva equity **solo ai punti di exit dei trade**, non barra per barra. Il drawdown viene calcolato su questa curva sparsa, ignorando completamente il drawdown intra-trade.

Esempio: un trade long che perde il 20% mid-trade (low che tocca lo SL) ma viene chiuso a −5%, mostra un drawdown del −5% anziché del −20%.

### Fix proposto

1. **Costruire una equity curve per-bar** che mark-to-market la posizione aperta a ogni barra. Per ogni barra tra `entry_idx+1` e `exit_idx`, calcolare il valore della posizione come `shares * direction * (close - entry_price)`.
2. **Mantenere anche la curva a trade-exit** per retrocompatibilità e per i grafici esistenti
3. **Passare la curva per-bar** a `calculate_all_metrics` per Sharpe/Sortino (risolve anche Bug #1)

---

## Bug #5 — Nessuna curva equity mark-to-market per-bar

**Severità:** 🟡 LOW (enhancement)  
**File:** `risk/sizing.py`

### Descrizione

Al momento non esiste una funzione che costruisce una equity curve mark-to-market a ogni barra. Senza questa:
- Non si può fare risk monitoring intraday
- Non si può calcolare drawdown intra-trade (Bug #4)
- Non si può calcolare Sharpe/Sortino correttamente su ritorni periodici (Bug #1)

### Fix proposto

Aggiungere una funzione `build_mtm_equity_curve(trades, df, initial_equity)` in `risk/sizing.py` che itera su ogni barra del `df` e calcola il P&L non realizzato delle posizioni aperte.

---

## Riepilogo severity e priorità

| # | Bug | Severità | Priorità | Fix stimato |
|---|---|---|---|---|
| 1 | Sharpe/Sortino broken | 🔴 CRITICAL | P0 | 1 riga, 5 min |
| 2 | Regime troppo restrittivo | 🟠 HIGH | P1 | Parametrico, 1h + test |
| 3 | Signal overlap 56% | 🟠 MEDIUM | P2 | Parametrico, 30 min |
| 4 | Drawdown sottostimato | 🟡 MEDIUM | P2 | Nuova funzione, 2h |
| 5 | No MTM equity curve | 🟡 LOW | P3 | Nuova funzione, 3h |

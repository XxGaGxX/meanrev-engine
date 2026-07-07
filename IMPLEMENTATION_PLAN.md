# Piano di Implementazione — Mean Reversion Intraday

**Versione:** 1.0
**Data:** 2026-07-06
**Strategia di riferimento:** Mean Reversion Intraday (documentazione in `documentation.md`)

---

## 1. Analisi della Strategia (sintesi da `documentation.md`)

La strategia è strutturata su **3 livelli indipendenti**:

| Livello | Funzione | Componenti chiave |
|---|---|---|
| **L1 — Filtro di Regime** | Decide **SE** tradare | ADX (<22), Hurst Exponent (<0.45), ATR relativo, esclusione eventi |
| **L2 — Segnale di Ingresso** | Decide **QUANDO** entrare | RSI + Bollinger Bands + Z-score + Volume spike (tripla conferma) |
| **L3 — Gestione Uscita** | Decide **QUANDO** uscire | Take profit (z-score→0), Stop loss (1.5× ATR), Time stop (25 barre), Regime stop (ADX>25) |

Il documento enfatizza correttamente che il **Livello 1 è il più importante** — un buon filtro di regime elimina l'80% dei trade cattivi. La gestione dell'uscita è dove si vince o si perde davvero.

### Punti di forza della documentazione
- Framework a 3 livelli ben strutturato e logicamente corretto
- Ottima enfasi sull'overfitting e sulla walk-forward analysis
- Position sizing basato sul rischio (non size fissa)
- Monte Carlo su sequenza trade per stimare drawdown realistici
- Checklist pre-live completa

### Punti critici / raccomandazioni
- Il codice di esempio usa `talib` che richiede compilazione C — va verificata l'installazione
- L'Hurst Exponent rolling su 252 periodi a 15 min = 63 ore (~9 giorni) — finestra ragionevole
- Il filtro volume a 1.5× media potrebbe essere troppo restrittivo su timeframe alti

---

## 2. Raccomandazioni su Asset e Timeframe

### 2.1 Asset consigliati

Dopo aver incrociato la documentazione con la ricerca sulle best practice per mean reversion intraday, ecco la raccomandazione:

> **Inizia con ETF liquidi sul mercato USA: `SPY`, `QQQ`, `IWM`**

**Perché gli ETF sono la scelta migliore per iniziare:**

| Criterio | ETF (SPY/QQQ/IWM) | Energy Stocks (XOM/CVX) | Forex | Futures |
|---|---|---|---|---|
| Liquidità | ⭐⭐⭐ Eccellente | ⭐⭐ Buona | ⭐⭐⭐ Eccellente | ⭐⭐⭐ Eccellente |
| Spread bid-ask | ⭐⭐⭐ Bassissimo | ⭐⭐ Medio | ⭐⭐⭐ Bassissimo | ⭐⭐⭐ Basso |
| Rischio gap/earnings | ⭐⭐⭐ Nullo (diversificati) | ⭐ Alto (news macro) | ⭐⭐⭐ Basso | ⭐⭐⭐ Basso |
| Mean reversion intraday | ⭐⭐⭐ Forte | ⭐⭐ Medio | ⭐⭐⭐ Forte | ⭐⭐⭐ Forte |
| Compatibilità doc/Alpaca | ⭐⭐⭐ Nativa | ⭐⭐⭐ Nativa | ⭐ Richiede adattamenti | ⭐ Richiede adattamenti |
| Accessibilità retail | ⭐⭐⭐ Alta | ⭐⭐⭐ Alta | ⭐⭐ Alta | ⭐⭐ Media (margini) |

- **SPY** (S&P 500): il più liquido, mean reversion intraday molto forte, pattern apertura/chiusura prevedibili
- **QQQ** (Nasdaq 100): più volatile di SPY, più segnali ma anche più rumore — test secondario
- **IWM** (Russell 2000): volatilità media, buona per diversificare

**Perché NON energy stocks (XOM, CVX, etc.):**
- Fortemente influenzati da news macro (prezzo petrolio, geopolitica, OPEC) che generano trend direzionali improvvisi
- Il filtro di regime (ADX/Hurst) potrebbe non reagire abbastanza velocemente a un repricing su news
- L'esperienza pregressa sul settore è utile per l'analisi fondamentale, ma per mean reversion pura la liquidità e la stabilità del pattern intraday sono più importanti della conoscenza del settore

**Perché NON Forex (per ora):**
- Richiede adattamenti significativi alla documentazione (no volume reale, no earnings, sessioni 24h)
- Meglio implementare dopo aver validato il framework su equities

**Perché NON Futures (per ora):**
- Richiedono account con margini più alti e dati real-time a pagamento
- Ottimi per scalabilità futura, ma sovradimensionati per la fase di validazione

### 2.2 Timeframe consigliato

> **Timeframe primario: 15 minuti**

| Timeframe | Pro | Contro | Verdetto |
|---|---|---|---|
| **5 min** | Più segnali, più frequenza | Troppo rumore, più falsi positivi, filtro volume troppo restrittivo | Test secondario |
| **15 min** | Buon compromesso rumore/segnali, filtri più affidabili, meno costi di transazione | Meno trade, campione statistico più lento da accumulare | **Primario** |
| **1 ora** | Molto robusto, pochi falsi | Troppo pochi segnali intraday (max 6-7 barre/sessione) | Non adatto per intraday |

**Raccomandazione operativa:**
- Sviluppo e validazione su **15 minuti**
- Una volta validato, test parallelo su **5 minuti** con gli stessi parametri (non ottimizzati separatamente) per vedere se aumenta il campione senza degradare le metriche

---

## 3. Piano di Implementazione — Fasi

### FASE 0: Setup Infrastruttura (Week 0)

| Task | Dettaglio | Output |
|---|---|---|
| 0.1 Setup ambiente Python | Python 3.11+, virtualenv, requirements.txt | Ambiente isolato |
| 0.2 Installazione dipendenze | `backtrader`, `pandas`, `numpy`, `TA-Lib`, `alpaca-trade-api`, `vectorbt` (opzionale) | Stack funzionante |
| 0.3 Verifica TA-Lib | `talib` richiede libreria C — test import | Conferma funzionamento |
| 0.4 Account Alpaca | Registrare account paper trading | API key per fetch dati |
| 0.5 Fetch dati storici | SPY, QQQ, IWM a 15 min, 2+ anni di storico (2022-2024) | Dataset pulito e allineato |
| 0.6 Struttura progetto | Creare moduli: `data/`, `indicators/`, `filters/`, `signals/`, `backtest/`, `risk/`, `utils/` | Architettura modulare |

### FASE 1: Livello 1 — Filtro di Regime (Week 1-2)

> **Obiettivo:** Implementare e validare **isolatamente** il filtro di regime. Questa è la fase più importante.

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 1.1 Indicatore ADX | `talib.ADX(high, low, close, 14)` | Plot ADX vs prezzo, verificare ADX < 20 in fasi laterali |
| 1.2 Indicatore Hurst | Implementare Hurst rolling con finestra 252 barre | Verificare H < 0.45 in range-bound, H > 0.5 in trend |
| 1.3 Indicatore ATR relativo | `ATR / close` rolling, flag se > 2σ dalla media | Esclude condizioni di volatilità anomala |
| 1.4 Combinazione filtro | `regime_ok = (ADX < 22) & (Hurst < 0.45) & (ATR_rel < 2σ)` | |
| 1.5 Validazione visiva | Plot prezzo con sfondo verde dove `regime_ok=True` | Deve corrispondere a fasi laterali visivamente |
| 1.6 Validazione statistica | Calcolare % di tempo con `regime_ok=True` (target: 20-50%) | Se <10% troppo restrittivo, se >70% non filtra |

**Output atteso:** Modulo `filters/regime.py` con funzione `apply_regime_filter(df)` testata e validata.

### FASE 2: Livello 2 — Segnale di Ingresso (Week 2-3)

> **Obiettivo:** Implementare il segnale di ingresso con tripla conferma, ma **solo dove `regime_ok=True`**.

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 2.1 Indicatore RSI | `talib.RSI(close, 14)` | Range 0-100, comportamento atteso |
| 2.2 Indicatore Bollinger Bands | `talib.BBANDS(close, 20, 2, 2)` | Bande si allargano in volatilità |
| 2.3 Indicatore Z-score | Rolling 20 periodi | Normalizzazione corretta |
| 2.4 Indicatore Volume | `volume > 1.5 × volume.rolling(20).mean()` | Verificare che filtri barre a basso volume |
| 2.5 Segnale long | `regime_ok & RSI<30 & close<bb_lower & zscore<-2 & vol_confirm` | |
| 2.6 Segnale short | `regime_ok & RSI>70 & close>bb_upper & zscore>2 & vol_confirm` | |
| 2.7 Conteggio segnali | Contare segnali su 2 anni di storico | Minimo 30-50 segnali per asset, altrimenti allentare soglie |

**Output atteso:** Modulo `signals/entry.py` con funzione `generate_entry_signals(df)`.

### FASE 3: Livello 3 — Gestione Uscita (Week 3-4)

> **Obiettivo:** Implementare le 4 regole di uscita in un motore di simulazione.

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 3.1 Take Profit | Uscita quando `zscore` torna ≥ 0 (long) o ≤ 0 (short) | Target dinamico, non arbitrario |
| 3.2 Stop Loss | `1.5 × ATR` dal prezzo di ingresso | Adattivo alla volatilità |
| 3.3 Time Stop | Uscita forzata dopo 25 barre (15 min = ~6.25 ore) | Evita capitale bloccato |
| 3.4 Regime Stop | Uscita immediata se `ADX > 25` durante il trade | Protezione da cambio regime |
| 3.5 Simulazione trade | Loop su ogni segnale, applicare uscite in ordine di priorità | Log completo: entry, exit, P&L, motivazione uscita |

**Output atteso:** Modulo `signals/exit.py` con funzione `simulate_exit(df, entry_idx, direction)`.

### FASE 4: Position Sizing & Risk Management (Week 4)

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 4.1 Sizing adattivo | `size = (equity × risk%) / (ATR × 1.5)` | Backtest con size variabile vs size fissa |
| 4.2 Rischio per trade | 1% del capitale per trade | Mai oltre 2% |
| 4.3 Esposizione aggregata | Limitare posizioni multiple su asset correlati | Max 3 posizioni aperte contemporaneamente |

**Output atteso:** Modulo `risk/sizing.py`.

### FASE 5: Motore di Backtest (Week 4-5)

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 5.1 Integrazione Backtrader | Strategy class con tutti i 3 livelli | Backtest su singolo asset senza errori |
| 5.2 Costi realistici | Commissione 0.1% per lato, slippage 0.05% | Confronto con e senza costi |
| 5.3 Metriche base | Win rate, Profit Factor, Sharpe, Expectancy, Max Drawdown | Tutte calcolabili e positive |

**Output atteso:** Script `backtest/engine.py` con risultati su SPY/QQQ/IWM.

### FASE 6: Walk-Forward Analysis (Week 5-6)

> **Obbligatorio per evitare overfitting.**

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 6.1 Creazione finestre | Train 6 mesi → Test 1 mese, sliding window | Almeno 4 finestre out-of-sample |
| 6.2 Ottimizzazione su train | Grid search parametri chiave (RSI soglia, ATR mult, z_threshold) | Solo su train |
| 6.3 Test su OOS | Applicare parametri ottimi al segmento test | Metriche aggregate solo su test |
| 6.4 Confronto in-sample vs OOS | Verificare che le metriche OOS non degradino >20% | Se degradano, parametri overfittati |

**Output atteso:** Report WFA con tabella finestre e metriche aggregate.

### FASE 7: Monte Carlo Simulation (Week 6)

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 7.1 Trade log WFA | Estrarre lista trade dalla walk-forward analysis | Campione su tutte le finestre test |
| 7.2 Bootstrap | 10,000 simulazioni con resampling dei return | |
| 7.3 Analisi drawdown | Percentili 5°, 50°, 95° di max drawdown | 95° percentile deve essere sostenibile |

**Output atteso:** Report Monte Carlo con distribuzione drawdown.

### FASE 8: Paper Trading (Week 7-10)

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 8.1 Deploy logica | Stessa identica logica su Alpaca paper trading | |
| 8.2 Fetch real-time | WebSocket bars 15 min | Dati allineati con backtest |
| 8.3 Logging trade | Timestamp, prezzo, motivazione uscita per ogni trade | Confrontabile con backtest |
| 8.4 Durata minima | 4-6 settimane O minimo 30-50 trade | Primo dei due che arriva per ultimo |
| 8.5 Confronto metriche | Paper vs WFA — scostamento deve essere <15% | Se maggiore, problema slippage/costi |

**Output atteso:** Log paper trading e report confronto metriche.

### FASE 9: Deployment Live (Week 11+)

| Task | Dettaglio | Criterio di validazione |
|---|---|---|
| 9.1 Size ridotta | 25-50% della size calcolata per prime 2-4 settimane | Riduce rischio esecuzione reale |
| 9.2 Monitoraggio settimanale | Confronto metriche live vs attese | Controllo continuo |
| 9.3 Scaling graduale | Aumentare a size piena dopo 4-6 settimane positive | |

**Output atteso:** Trading live con sizing progressivo.

---

## 4. Timeline Riassuntiva

```
Week 0:  Setup infrastruttura + fetch dati
Week 1-2:  FASE 1 — Filtro di Regime (validazione isolata)
Week 2-3:  FASE 2 — Segnale di Ingresso
Week 3-4:  FASE 3 — Gestione Uscita
Week 4:    FASE 4 — Position Sizing
Week 4-5:  FASE 5 — Motore Backtest (integrazione)
Week 5-6:  FASE 6 — Walk-Forward Analysis
Week 6:    FASE 7 — Monte Carlo
Week 7-10: FASE 8 — Paper Trading (4-6 settimane minimo)
Week 11+:  FASE 9 — Live Trading (size ridotta → piena)
```

---

## 5. Architettura Moduli Consigliata

```
quant_trd/
├── data/
│   ├── fetch.py          # Fetch storico + real-time da Alpaca
│   └── clean.py          # Pulizia, allineamento, validazione
├── indicators/
│   ├── adx.py
│   ├── hurst.py
│   ├── rsi.py
│   ├── bollinger.py
│   ├── zscore.py
│   ├── volume.py
│   └── atr.py
├── filters/
│   └── regime.py         # Filtro ADX + Hurst + ATR relativo
├── signals/
│   ├── entry.py          # Generazione segnali long/short
│   └── exit.py           # Simulazione uscite (TP, SL, time, regime)
├── risk/
│   └── sizing.py         # Position sizing + Kelly frazionato
├── backtest/
│   ├── engine.py         # Classe Backtrader
│   ├── walk_forward.py   # WFA engine
│   └── monte_carlo.py    # MC simulation su trade log
├── live/
│   ├── paper.py          # Paper trading connector
│   └── live.py           # Live trading connector
├── utils/
│   └── metrics.py        # Calcolo Sharpe, Profit Factor, Expectancy, ecc.
├── config.yaml           # Parametri centralizzati (soglie, risk%, ecc.)
├── documentation.md      # Documentazione tecnica originale
└── IMPLEMENTATION_PLAN.md # Questo documento
```

---

## 6. Checklist Decisioni Chiave da Prendere

Prima di iniziare l'implementazione, conferma questi punti:

1. **Asset**: SPY, QQQ, IWM su Alpaca — confermi?
2. **Timeframe**: 15 minuti primario, 5 minuti test secondario — confermi?
3. **Capitale paper/live**: Quanto capitale prevedi? (influenza il position sizing e il minimo numero di share acquistabili — es. SPY a ~$550 richiede capitale minimo diverso da un asset a $50)
4. **Filtro eventi**: Vuoi implementare l'esclusione di orari (prime/ultime 30 min) e eventi macro fin da subito, o nella FASE 1 base senza filtro eventi?

---

## 7. Riferimenti

- `documentation.md` — Documentazione tecnica completa della strategia
- Ricerca web su best practice mean reversion intraday (index futures, ETFs, forex majors)
- Backtrader documentation — https://www.backtrader.com/docu/
- Alpaca API — https://alpaca.markets/docs/

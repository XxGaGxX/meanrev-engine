# Gap Mean Reversion — Design Document

**Data:** 2026-07-09
**Autore:** Diego
**Versione:** 2.0
**Skill applicate:** brainstorming, quant-strategy-blueprint, quant-analyst, backtesting-trading-strategies

---

## 0. ⚠️ Pre-requisito: Alpha Research (EDA)

**Prima di scrivere qualsiasi codice di produzione, va completata una fase di exploratory data analysis per dimostrare l'esistenza dell'edge.**

### 0.1 Expectancy semplice (screening iniziale)

| Domanda | Metodo | Deliverable |
|---|---|---|
| `E[Return \| gap]` è positivo? | Calcolo expectancy condizionata su S&P 500, 2014-2024 | Tabella: gap bucket → mean return, std, N trades |
| Fill rate reale per gap bucket? | % di gap che toccano PrevClose entro fine giornata, per bucket | Tabella: 0.3-0.5%, 0.5-1%, 1-2%, >2% |
| Path dependency: SL colpito prima del TP? | Per ogni gap bucket: % SL hit prima di TP | Istogramma SL vs TP first hit |
| Distribuzione gap su S&P 500? | Istogramma frequenza gap per dimensione | Soglie basate su percentili (es. 25° e 90°), non valori fissi |
| Quanti trade al mese? | Contare segnali validi (dopo filtri) su 10 anni | Media ± std trade/mese |

### 0.2 Expectancy condizionale (analisi di profondità)

**⚠️ L'expectancy semplice `E[Return | gap]` può essere fuorviante.** Un gap dello 0.8% potrebbe funzionare solo nei financial o solo il martedì. L'edge medio nasconde eterogeneità potenzialmente critica.

L'EDA deve calcolare l'expectancy condizionata su TUTTE queste dimensioni:

| Dimensione | Domanda | Deliverable |
|---|---|---|
| **Settore** | `E[Return \| gap, sector]` | Tabella: per ogni settore GICS a 2 cifre → mean return, N trades |
| **VIX** | `E[Return \| gap, VIX_bucket]` | Tabella: VIX < 15, 15-20, 20-25, 25-30 → mean return, std |
| **Giorno settimana** | `E[Return \| gap, day_of_week]` | Lunedì-Venerdì: mean return per giorno, N trades |
| **Market regime** | `E[Return \| gap, regime]` | Bull/Bear/Sideways → mean return (vedi Sezione 2.4 per definizioni) |
| **Market cap** | `E[Return \| gap, market_cap_quintile]` | Large/Mid/Small cap → mean return per quintile |
| **ATR percentile** | `E[Return \| gap, ATR_percentile]` | Volatilità relativa del ticker → mean return per bucket |
| **Direzione gap** | `E[Return \| gap_up]` vs `E[Return \| gap_down]` | LONG vs SHORT: expectancy separata per direzione |
| **Interazioni** | `E[Return \| gap, sector, VIX]` | Almeno le interazioni 2-way più rilevanti |

**Output finale:** una matrice multidimensionale che mostri DOVE l'edge esiste e DOVE no. Esempio: *"gap 0.5-1% funziona nei financial e healthcare con VIX < 20, ma NON nei tech con VIX > 25."*

### 0.3 Gate decision

Dopo l'EDA:
- **Edge confermato (Sharpe atteso > 0.5, robusto attraverso le dimensioni):** procedere con l'implementazione
- **Edge condizionale (Sharpe > 0.5 solo in specifici regimi/settori):** implementare con filtri condizionali
- **Edge debole/marginale:** rivedere parametri o abbandonare la strategia
- **Edge inesistente:** NON procedere — costruire l'infrastruttura prima di provare l'edge è uno spreco di risorse

---

## 1. Overview

Strategia di trading algoritmico intraday/swing su equity USA large-cap che sfrutta il fenomeno statistico del **gap mean reversion**: dopo un'apertura con gap significativo rispetto alla chiusura precedente, il prezzo tende a ritracciare verso la chiusura del giorno prima.

**Obiettivo:** Singola strategia production-ready, backtestata su dati reali con transaction costs e slippage, pronta per esecuzione live via Alpaca.

**Asset class:** Equity USA (S&P 500 large-cap, ETF SPY/QQQ)
**Timeframe:** Intraday/swing (5min bars, hold intraday)
**Broker target:** Alpaca Markets (paper → live)

### ⚠️ Limitazioni note sui dati

- **Survivorship bias:** `yfinance` non include titoli delistati. Il backtest storico su S&P 500 soffre di survivorship bias. Per backtest rigorosi usare dati Alpaca o Polygon che includono ticker delistati.
- **Dati intraday:** `yfinance` limita i dati a 5min agli ultimi 60 giorni. Per backtest multi-anno servono dati giornalieri o fonte alternativa (Alpaca Data API v2, Polygon).
- **Live data:** Per esecuzione live, usare Alpaca Data API o Polygon — `yfinance` ha rate limiting troppo aggressivo per uno scanner su 50+ ticker.
- **Corporate actions:** Dati split-adjusted ma NON dividend-adjusted per il calcolo del gap. Dati dividend-adjusted distorcerebbero la dimensione reale del gap storico.

---

## 2. Fondamento strategico

### 2.1 Cos'è la Mean Reversion

La mean reversion è il principio statistico per cui i prezzi degli asset, dopo essersi allontanati da una media di lungo periodo, tendono a ritornarvi. Si basa sull'assunzione che le deviazioni estreme siano temporanee e che esista una "forza di richiamo" verso il valore medio.

Nel nostro caso, applichiamo la mean reversion ai **gap di apertura**: la chiusura del giorno precedente funge da "media" e il gap rappresenta una deviazione che il mercato tende a correggere nelle prime ore di trading.

### 2.2 Perché i gap revertano

Tre meccanismi principali:
1. **Illiquidità overnight:** durante l'after-hours e il pre-market, pochi ordini muovono il prezzo facilmente. All'apertura, con l'arrivo della liquidità istituzionale, il prezzo "corregge".
2. **Overreaction comportamentale:** i trader retail reagiscono emotivamente alle notizie overnight, spingendo il prezzo oltre il fair value.
3. **Market making istituzionale:** i market maker accumulano posizioni contrarie al gap, fornendo liquidità e spingendo il prezzo verso la chiusura precedente.

### 2.3 Condizionalità dell'edge

Il gap fill NON è garantito. L'edge esiste solo con filtri:
- **Gap size:** gap piccoli (0.3%–2.0%) revertano più spesso; gap >2% sono spesso guidati da news strutturali (earnings) e tendono a NON revertare.
- **Regime di mercato:** la strategia performa peggio in mercati fortemente trendanti. Filtro VIX >30 → no trade.
- **Filtro news/earnings:** escludere ticker con earnings o news ad alto impatto nelle 24h precedenti.
- **Short availability (HTB):** per i segnali SHORT, verificare che il ticker sia shortable su Alpaca (hard-to-borrow = no trade).

### 2.4 Classificazione del Market Regime

Ogni giorno di trading e ogni trade devono essere etichettati con il regime di mercato corrente. Questo permette di calcolare metriche di performance per regime e identificare condizioni avverse.

**Definizione dei regimi:**

| Regime | Condizione | Indicatore |
|---|---|---|
| **Bull Trend** | Prezzo > 200SMA, pendenza 200SMA positiva, ADX(14) > 25 | Trend rialzista strutturale |
| **Bear Trend** | Prezzo < 200SMA, pendenza 200SMA negativa, ADX(14) > 25 | Trend ribassista strutturale |
| **Sideways** | ADX(14) < 20, prezzo oscilla attorno a 200SMA | Mercato laterale/range-bound |
| **High Volatility** | VIX > 25 | Volatilità elevata (indipendentemente dalla direzione) |
| **Low Volatility** | VIX < 15 | Volatilità compressa |
| **Risk On** | SPY > 200SMA, VIX < 20, HYG/IEI spread in contrazione | Appetito per il rischio |
| **Risk Off** | SPY < 200SMA oppure VIX > 25 | Avversione al rischio |

**Utilizzo operativo:**
- Ogni trade nel backtest viene etichettato con il regime corrente
- Il report di backtest include una tabella **Sharpe × Regime**: una riga per ogni regime, con Sharpe, N trades, Win Rate
- La strategia può essere disabilitata selettivamente: es. no SHORT in Bull Trend, no LONG in Bear Trend
- La decisione di attivare/disattivare per regime viene presa DOPO l'EDA (Sezione 0), basandosi sui dati reali

**Output atteso:** tabella come questa:

| Regime | N Trades | Sharpe | Win Rate | Profit Factor |
|---|---|---|---|---|
| Bull Trend | 120 | 1.8 | 62% | 1.5 |
| Bear Trend | 45 | -0.3 | 42% | 0.8 |
| Sideways | 200 | 2.1 | 65% | 1.7 |
| High Vol | 80 | 0.4 | 51% | 1.1 |
| Low Vol | 150 | 1.2 | 58% | 1.3 |
| Risk On | 160 | 2.0 | 64% | 1.6 |
| Risk Off | 90 | 0.2 | 48% | 0.9 |

Se la strategia ha Sharpe negativo in Bear Trend e Risk Off, questi regimi vengono disabilitati in produzione.

*(I valori nella tabella sopra sono illustrativi — verranno popolati con dati reali dall'EDA.)*

---

## 3. Architettura del sistema

```
gap-mean-reversion/
├── docs/
│   ├── specs/
│   │   └── 2026-07-09-gap-mean-reversion-design.md
│   └── strategic-foundation-mean-reversion.md
├── src/
│   ├── __init__.py
│   ├── config.py                 # Parametri globali
│   ├── data/
│   │   ├── __init__.py
│   │   ├── ohlcv.py              # Download + cache OHLCV
│   │   ├── scanner.py            # Scanner pre-market: gap%, VIX, ADX, 200EMA, RVOL
│   │   └── news_filter.py        # Filtro earnings + RVOL pre-market (Finnhub)
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── signals.py            # Generazione segnali LONG/SHORT/EXIT
│   │   └── risk.py               # Position sizing + volatility scaling, SL/TP
│   ├── portfolio/
│   │   ├── __init__.py
│   │   └── manager.py            # Cash, exposure, margin, sector limits, correlation
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py             # Loop backtest event-driven + hold-out split + partial fill
│   │   ├── metrics.py            # Metriche complete + MFE/MAE + rolling + bootstrap
│   │   └── optimize.py           # Grid search + sensitivity heatmaps + plateau detection
│   ├── execution/
│   │   ├── __init__.py
│   │   └── broker.py             # Alpaca + idempotency + reconciliation + recovery
│   ├── logger.py                  # Logging + alerting (Discord/Slack)
│   └── cli.py                    # CLI: backtest, optimize, scan, run, eda
├── config/
│   └── settings.yaml             # Defaults: capitale, commissioni, slippage
├── data/
│   └── cache/                    # Dati OHLCV cachati
├── logs/                         # Log file rotanti
├── reports/                      # Output backtest (trades.csv, equity.csv, chart.png)
├── tests/
│   ├── test_signals.py
│   ├── test_news_filter.py
│   ├── test_risk.py
│   ├── test_metrics.py
│   ├── test_backtest.py
│   ├── test_determinism.py       # Due run identiche → stesso output
│   ├── test_chaos.py             # Simulazione failure (Finnhub, Alpaca, etc.)
│   └── test_replay.py            # Replay giornata registrata
├── requirements.txt
├── .env.example
└── README.md
```

### 3.1 Responsabilità dei moduli

| Modulo | Cosa fa | Dipende da | Input | Output |
|---|---|---|---|---|
| `data/ohlcv.py` | Scarica OHLCV storici (giornalieri + intraday), caching locale | `config.py` | ticker list, date range | `DataFrame` con OHLCV |
| `data/scanner.py` | Calcola gap%, VIX, ADX, 200EMA, RVOL pre-market | `config.py`, `ohlcv.py` | `DataFrame` OHLCV | `List[str]` ticker validi + gap% + regime flags |
| `data/news_filter.py` | Interroga Finnhub per earnings/news, esclude ticker con eventi | `config.py` | `List[str]` ticker | `List[str]` ticker filtrati |
| `strategy/signals.py` | Genera segnali LONG/SHORT/EXIT (usa Close, non wick) | Nessuna (pura logica) | `DataFrame` OHLCV + gap% + opening range | `pd.Series` con -1/0/+1 |
| `strategy/risk.py` | Position sizing con volatility scaling, SL/TP | `config.py` | capitale, entry_price, ATR | `dict` con size, sl, tp |
| `portfolio/manager.py` | Gestisce cash, buying power, margin, exposure, sector limits, correlazione | `config.py`, `signals.py` | segnali, posizioni attuali | allocazioni approvate/rifiutate |
| `backtest/engine.py` | Loop storico giornaliero con hold-out split, T-costs, slippage, partial fill model | `signals.py`, `risk.py`, `ohlcv.py` | ticker, date range, split ratio | equity curve, trades list |
| `backtest/metrics.py` | Calcola tutte le metriche da equity curve | Nessuna (pura funzione) | equity curve, trades list | `dict` metriche |
| `backtest/optimize.py` | Grid search su parametri (gap_min, gap_max, lookback, VIX threshold) | `engine.py`, `metrics.py` | param grid, ticker, date range | migliori parametri + metriche |
| `execution/broker.py` | Invia ordini ad Alpaca (paper/live), gestisce stati, recovery dopo crash | `config.py`, `signals.py`, `risk.py` | segnali, size, sl, tp | order ID, fill status |
| `logger.py` | Logging strutturato + webhook alerts (Discord/Slack) | `config.py` | log level, messaggi | file di log, notifiche |
| `cli.py` | Entry point CLI | Tutti i moduli | argv | output testuale/CSV/PNG |

### 3.2 Data flow giornaliero (live)

```
08:00 EST  → news_filter.py → Finnhub API → esclude ticker con earnings/news
08:30 EST  → scanner.py → calcola VIX (da Alpaca/Polygon, non yfinance) → se VIX > 30: NO TRADE oggi
09:00 EST  → scanner.py → calcola VIX + ADX + 200EMA + RVOL pre-market per ogni ticker
09:00 EST  → scanner.py → filtra: VIX < 30, ADX < 25, price > 200EMA, RVOL < 3x
09:00 EST  → scanner.py → calcola gap% sui ticker rimanenti → applica soglie (da EDA)
09:00 EST  → portfolio/manager.py → RANKING + vincoli settore/correlazione → alloca top N
09:30 EST  → segnali in attesa: raccoglie prime 15 barre (5min) per definire opening range
09:45 EST  → signals.py → conferma: Close 5min > opening_range_high per 2 barre → LONG/SHORT
09:45 EST  → portfolio/manager.py → verifica budget, margin, exposure → approva/rifiuta
09:45 EST  → broker.py → SHORT check: verifica che il ticker sia shortable (HTB = skip)
09:45 EST  → risk.py → calcola size (1% risk, con min stop distance) → broker.py → invia bracket order
Intraday  → signals.py monitora: TP (prev close) o SL (opening range low/high)
15:50 EST  → se trade ancora aperto: EXIT a mercato (15:50, non 16:00 — evita slippage di chiusura)
```

---

## 4. Regole della strategia

### 4.1 Definizioni operative

**Definizioni precise per evitare ambiguità backtest vs live:**

| Termine | Definizione |
|---|---|
| **PrevClose** | Prezzo di chiusura ufficiale della sessione regolare del giorno T-1 |
| **Open** | Primo trade stampato sul SIP (09:30:00 EST), NON l'apertura della prima barra 5min |
| **Opening range high** | Massimo degli `high` delle prime `opening_range_bars` barre da 5min (escluse le wick oltre l'high ufficiale) |
| **Opening range low** | Minimo dei `low` delle prime `opening_range_bars` barre da 5min |
| **Breakout confirmation** | **Close** della barra 5min sopra `opening_range_high` (LONG) o sotto `opening_range_low` (SHORT) per `confirmation_bars` barre consecutive |
| **Gap bucket** | Le soglie gap_min e gap_max vanno derivate empiricamente dall'EDA (Sezione 0) usando percentili, non valori hardcoded |

### 4.2 Parametri (in `config/settings.yaml`)

```yaml
strategy:
  gap_min_pct: 0.003        # 0.3% gap minimo (da calibrare via EDA)
  gap_max_pct: 0.02         # 2.0% gap massimo (da calibrare via EDA)
  opening_range_bars: 3     # 3 barre da 5min = 15 minuti
  confirmation_bars: 2      # 2 Close consecutive oltre opening range
  vix_max: 30.0             # VIX sopra questa soglia → no trade
  adx_max: 25               # ADX(14) > 25 = trend forte → no trade su quel ticker
  ema_period: 200           # price deve essere > 200EMA (solo long in uptrend)
  rvol_max: 3.0             # RVOL pre-market > 3x → news impact, salta ticker
  max_concurrent_trades: 5  # massimo trade simultanei
  max_per_sector: 1         # massimo 1 ticker per settore GICS

risk:
  risk_per_trade: 0.01      # 1% del capitale per trade
  min_stop_distance_pct: 0.001  # SL minimo 0.1%
  max_position_size: 0.95   # massimo 95% del capitale in una posizione
  volatility_scaling: true  # abilita ATR normalization

backtest:
  initial_capital: 25000    # capitale iniziale
  base_slippage: 0.0003     # 3 bps slippage base
  open_slippage_extra: 0.0005  # +5 bps nelle prime barre (open)
  vol_adj_slippage: 0.1     # coefficiente aggiustamento volatilità
  sec_fee_rate: 0.000008    # SEC fee: $8 per $1M
  finra_taf_per_share: 0.000119  # FINRA TAF
  finra_taf_cap: 5.95       # cap FINRA TAF per trade
  hold_out_split: 0.7       # 70% in-sample, 30% out-of-sample

execution:
  broker: alpaca
  paper_trading: true       # paper inizialmente, poi live
```

### 4.3 Trigger logici

**LONG (gap down → buy to fill up):**
```
gap_pct = (Open - PrevClose) / PrevClose
VIX < vix_max
gap_pct between -gap_max_pct and -gap_min_pct
ticker NOT in earnings/news blacklist
opening_range_high = max(high[0:opening_range_bars])
Close of 5min bar > opening_range_high for confirmation_bars consecutive bars
→ ENTRY LONG
→ TP = PrevClose
→ SL = min(low[0:opening_range_bars])
→ EXIT at TP OR SL OR 15:50 EST (15:50 per evitare slippage di chiusura)
```

**SHORT (gap up → sell to fill down):**
```
gap_pct = (Open - PrevClose) / PrevClose
VIX < vix_max
gap_pct between +gap_min_pct and +gap_max_pct
ticker NOT in earnings/news blacklist
opening_range_low = min(low[0:opening_range_bars])
Close of 5min bar < opening_range_low for confirmation_bars consecutive bars
→ ENTRY SHORT
→ TP = PrevClose
→ SL = max(high[0:opening_range_bars])
→ EXIT at TP OR SL OR 15:50 EST (15:50 per evitare slippage di chiusura)
```

### 4.4 Position sizing

```
risk_amount = capital * risk_per_trade                     # es. $25,000 * 1% = $250
stop_distance = max(abs(entry_price - SL), entry_price * min_stop_distance_pct)
position_size = risk_amount / stop_distance                # numero di azioni
position_size = min(position_size, capital * max_position_size / entry_price)

# Volatility scaling (ATR normalization)
# Per rendere i trade confrontabili tra ticker a diversa volatilità:
# position_size = position_size * (ATR_target / ATR_ticker)
# dove ATR_target è un valore di riferimento (es. ATR medio dell'S&P 500)
```

### 4.5 Commissioni e slippage (modello reale Alpaca)

```
# Alpaca NON ha commissioni flat 0.1% — il modello reale è:
# Commissione base: $0
# SEC Fee: ~$8 per $1,000,000 di vendita
# FINRA TAF: $0.000119 per share (capped a $5.95 per trade)

sec_fee_rate = 0.000008      # $8 / $1M
finra_taf_per_share = 0.000119
finra_taf_cap = 5.95

commission_entry = position_size * entry_price * sec_fee_rate + min(position_size * finra_taf_per_share, finra_taf_cap)
commission_exit = position_size * exit_price * sec_fee_rate + min(position_size * finra_taf_per_share, finra_taf_cap)
```

### 4.6 Slippage dinamico

```
# Slippage NON è costante — dipende dalla barra e dalla volatilità
# Prime 3 barre (opening range): slippage più alto
# Barre successive: slippage standard
# Modello: slippage = base_slippage + vol_adj * ATR(14) / price

slippage = base_slippage                          # default: 0.0003 (3 bps)
if bar_index < opening_range_bars:
    slippage += open_slippage_extra                # +5 bps nelle prime barre
slippage += vol_adj_slippage * (ATR_14 / price)   # aggiustamento per volatilità
```

### 4.7 Allocazione multi-ticker e vincoli di portafoglio

Quando più ticker gap simultaneously:
1. **Ranking:** ordina i ticker per `abs(gap%)` decrescente (gap più grandi = priorità)
2. **Vincolo settoriale:** massimo 1 ticker per settore GICS a 2 cifre (es. Info Tech, Financials, Health Care)
3. **Vincolo correlazione rolling:** calcola la correlazione pairwise su finestra mobile di 60 giorni (Pearson, `rolling(60).corr()`). Se due ticker hanno correlazione > 0.7, prendi solo quello con |gap%| maggiore
   - La correlazione NON è statica: viene ricalcolata ogni giorno sui 60 giorni precedenti
   - Per gruppi di ticker altamente correlati (es. semiconduttori), si può usare anche **cluster correlation**: clustering gerarchico sulla matrice di correlazione, con massimo 1 ticker per cluster
4. **Allocazione:** alloca capitale ai primi `max_concurrent_trades` ticker che passano i vincoli
5. **Vincolo budget:** `sum(position_value) ≤ capital * max_position_size`
6. **Segnali non eseguiti:** i ticker oltre il limite vengono loggati ma ignorati

Queste regole evitano che 5 ticker semiconduttori (AMD, NVDA, TSM, INTC, SOXL) vengano tradati simultaneamente come se fossero 5 posizioni indipendenti.

### 4.8 Portfolio State Machine

Il portfolio manager implementa una state machine esplicita per tracciare il ciclo di vita di ogni posizione:

```
  ┌──────┐     segnale      ┌────────────────┐     ordine        ┌──────────────────┐
  │ IDLE │ ───────────────▶ │ PENDING ORDERS │ ───────────────▶ │ ACTIVE POSITIONS │
  └──────┘                   └────────────────┘   accettato      └──────────────────┘
       ▲                            │                                   │
       │                            │ ordine rifiutato/timeout          │ TP/SL/EOD
       │                            ▼                                   ▼
       │                      ┌──────┐                          ┌─────────────┐
       └──────────────────────│ IDLE │◀─────────────────────────│ LIQUIDATION │
          (ritorno a idle)    └──────┘   posizione chiusa       └─────────────┘
                                                                       │
                                                                       │ crash/restart
                                                                       ▼
                                                               ┌──────────┐
                                                               │ RECOVERY │
                                                               └──────────┘
                                                                       │
                                                                       │ riconciliazione completata
                                                                       ▼
                                                               ┌──────────────────┐
                                                               │ ACTIVE POSITIONS │
                                                               └──────────────────┘
```

| Stato | Descrizione | Azioni consentite |
|---|---|---|
| **IDLE** | Nessuna posizione attiva, in attesa di segnali | Ricevere segnali, eseguire scansione pre-market |
| **PENDING ORDERS** | Ordine inviato al broker, in attesa di fill | Monitorare fill status, gestire retry/timeout, cancellare se scade |
| **ACTIVE POSITIONS** | Posizione aperta e monitorata | Aggiornare SL/TP trail, monitorare MFE/MAE, eseguire exit |
| **LIQUIDATION** | Uscita in corso (TP/SL/EOD/forced) | Attendere conferma fill, registrare P&L, loggare trade |
| **RECOVERY** | Riavvio dopo crash/disconnessione | Riconciliare stato con broker, ripristinare monitoraggio |

**Vantaggi della state machine:**
- Ogni transizione di stato è loggata (audit trail completo)
- Stati illegali sono impossibili (es. non puoi inviare un ordine se sei in LIQUIDATION)
- La recovery dopo crash ha un percorso esplicito e testabile
- Facilita il testing: puoi testare ogni transizione separatamente

---

## 5. Backtest engine

### 5.1 Split in-sample / out-of-sample (hold-out validation)

Il backtest usa uno split temporale 70/30 (hold-out validation):
- **In-sample (70%):** usato per calibrare/validare i parametri
- **Out-of-sample (30%):** usato per il test finale, MAI toccato durante la calibrazione

**Nota:** Questo è uno split semplice hold-out, non una rolling validation con finestre multiple. Un rolling hold-out (o Walk-Forward Analysis) sarebbe preferibile per verificare la stabilità dei parametri attraverso diversi regimi di mercato, ma richiede più potenza computazionale. Per la v1 usiamo hold-out semplice; il rolling hold-out è un upgrade futuro.

### 5.2 Loop del backtest

```python
for each trading_day in backtest_period:
    1. news_filter.filter(tickers) → rimuovi ticker con earnings/news
    2. scanner.scan(tickers) → calcola gap%, filtra per VIX e soglie
    3. for each ticker in valid_tickers:
        4. signals.generate(df_intraday) → LONG/SHORT/NO_TRADE
        5. if signal != 0:
            6. risk.calculate(capital, entry_price, sl_price) → size
            7. simulate_execution(size, entry_price, sl, tp) → pnl
            8. update equity curve, trade log
```

### 5.3 Metriche calcolate

| Categoria | Metrica | Descrizione |
|---|---|---|
| **Performance** | Total Return | Rendimento percentuale totale |
| | CAGR | Compound Annual Growth Rate |
| | Annual Returns | Rendimento anno per anno |
| | Monthly Returns | Rendimento mese per mese |
| **Risk-Adjusted** | Sharpe Ratio | Rendimento / volatilità (target: >1.0) |
| | Sortino Ratio | Rendimento / volatilità downside (target: >1.5) |
| | Calmar Ratio | CAGR / max drawdown |
| | MAR Ratio | CAGR / max drawdown (sinonimo Calmar) |
| | SQN (System Quality Number) | (Expectancy / std) * sqrt(N) |
| **Rischio** | Max Drawdown | Massimo picco-valle (%) |
| | VaR 95% | Value at Risk al 95% di confidenza |
| | CVaR 95% | Expected loss oltre il VaR |
| | Volatilità | Deviazione standard annualizzata |
| | Ulcer Index | Misura di drawdown persistente |
| | Skewness | Asimmetria della distribuzione dei rendimenti |
| | Kurtosis | Code spesse nella distribuzione |
| | Probability of Ruin | Probabilità di perdere X% del capitale (Monte Carlo + Bootstrap resampling) |
| **Trade** | Total Trades | Numero di trade round-trip |
| | Win Rate | % trade profittevoli |
| | Profit Factor | Profitto lordo / perdita lorda |
| | Expectancy | Valore atteso medio per trade ($) |
| | Avg Win / Avg Loss | Guadagno/perdita media ($) |
| | Max Consecutive Losses | Massima serie di perdite consecutive |
| | Kelly Criterion | Frazione ottimale di capitale da allocare (**⚠️ SOLO INFORMATIVO**: Kelly su pochi trade è instabile; MAI usato per position sizing diretto) |
| | Recovery Factor | Rendimento totale / max drawdown |
| **Execution** | MFE (Max Favorable Excursion) | Massimo profitto intra-trade prima dell'uscita |
| | MAE (Max Adverse Excursion) | Massima perdita intra-trade prima dell'uscita |
| | Avg Holding Time | Tempo medio di hold (minuti) |
| | Avg Exposure | Percentuale media di capitale investito |
| **Rolling** | Rolling Sharpe (6M) | Sharpe su finestra mobile di 6 mesi |
| | Rolling Sortino (6M) | Sortino su finestra mobile di 6 mesi |
| | Rolling Max DD (6M) | Max drawdown su finestra mobile di 6 mesi |

### 5.4 Sensitivity outputs

Oltre ai file di output standard, generare:
- **Heatmap 2D:** `gap_min_pct` vs `opening_range_bars` colorata per Sharpe → verifica plateau, non cliff edge
- **Response surface:** `gap_min_pct` × `gap_max_pct` → Sharpe 3D
- **Stability plot:** Sharpe al variare di ogni parametro ±20% attorno all'ottimo
- **Plateau Detection:** calcolare la percentuale dello spazio dei parametri con Sharpe entro il 95% del massimo. Se il massimo è un picco isolato (< 5% dello spazio), è probabile overfitting. Un plateau ampio (> 20%) indica un edge robusto.

### 5.5 Output files

| File | Contenuto |
|---|---|
| `reports/backtest_summary.txt` | Riepilogo metriche formattato |
| `reports/backtest_trades.csv` | Log trade-by-trade (data, ticker, entry, exit, pnl, tipo, MFE, MAE) |
| `reports/backtest_equity.csv` | Equity curve giornaliera |
| `reports/backtest_chart.png` | Grafico equity curve + drawdown |
| `reports/sensitivity_heatmap.png` | Heatmap 2D parametri → Sharpe |

---

## 6. Parameter optimization

### 6.1 Grid search (`backtest/optimize.py`)

```yaml
param_grid:
  gap_min_pct: [0.001, 0.002, 0.003, 0.005]     # derivare range dall'EDA
  gap_max_pct: [0.01, 0.015, 0.02, 0.03]
  opening_range_bars: [2, 3, 5, 10]
  confirmation_bars: [1, 2, 3]
  vix_max: [25, 30, 35]
  # SL/TP alternativi da testare:
  sl_type: ["opening_range", "atr_1x", "atr_1.5x", "atr_2x"]
  tp_type: ["prev_close", "atr_1x", "atr_2x"]
```

**Funzione obiettivo:** Sharpe Ratio (in-sample). **Vincolo:** max drawdown < 25%.

L'ottimizzazione gira SOLO sui dati in-sample. I migliori parametri vengono poi validati sull'out-of-sample.

**Nota:** Grid search è accettabile per 5-7 parametri discreti. Per ottimizzazioni future con più parametri, migrare a Bayesian Optimization (Optuna).

### 6.2 Sensitivity analysis

Dopo la grid search, per i parametri ottimali:
1. **Heatmap 2D:** ogni coppia di parametri → Sharpe (es. `gap_min` vs `opening_range_bars`)
2. **Stability check:** variare ogni parametro ±20% e verificare che lo Sharpe non collassi (no "cliff edge")
3. **Response surface:** visualizzazione 3D delle interazioni tra parametri
4. **Plateau Detection:** calcolare la zona dello spazio dei parametri con Sharpe ≥ 95% del massimo. Se questa zona è < 5% dello spazio totale → il massimo è probabilmente overfitting (picco isolato). Se > 20% → l'edge è robusto e stabile.
   - Output: `reports/plateau_analysis.csv` con % plateau, heatmap con contour line al 95%
   - Se plateau < 5%, rivedere i parametri o raccogliere più dati

---

## 7. Data pipeline

### 7.1 Fonti dati

| Dato | Fonte | Frequenza |
|---|---|---|
| OHLCV storico giornaliero | `yfinance` (Yahoo Finance) | Download una tantum + cache |
| OHLCV intraday (5min) | `yfinance` | Download per backtest |
| Earnings calendar | Finnhub API (`/calendar/earnings`) | Ogni giorno pre-market |
| Company news | Finnhub API (`/company-news`) | Ogni giorno pre-market |
| VIX | `yfinance` (^VIX) | Ogni giorno pre-market |

### 7.2 Caching

I dati OHLCV sono cachati in `./data/cache/` in formato Parquet per:
- Evitare rate limiting di Yahoo Finance
- Velocizzare backtest successivi
- Garantire riproducibilità

Struttura cache: `./data/cache/{ticker}_{interval}_{start}_{end}.parquet`

---

## 8. News filter (Finnhub)

### 8.1 Logica

```python
def filter_tickers(tickers: list[str]) -> list[str]:
    clean = []
    for ticker in tickers:
        # 1. Controlla earnings oggi/domani
        earnings = finnhub_client.earnings_calendar(
            _from=today, to=today + timedelta(days=1),
            symbol=ticker
        )
        if earnings: continue  # SALTA

        # 2. Controlla news ultime 24h
        news = finnhub_client.company_news(
            ticker, _from=today - timedelta(days=1), to=today
        )
        high_impact = [n for n in news if impact_score(n) > 0.7]
        if high_impact: continue  # SALTA

        clean.append(ticker)
    return clean
```

### 8.2 Filtro combinato: Earnings Calendar OR RVOL pre-market

⚠️ **RVOL da solo non basta.** Un ticker può avere RVOL basso nel pre-market ma aver pubblicato earnings alle 16:05 del giorno prima (after-market). Il gap del giorno dopo è informativo anche senza volume anomalo.

La logica corretta è **Earnings Calendar OR RVOL**:

```python
def is_high_impact(ticker: str, today: date) -> bool:
    # 1. Controlla earnings calendar (ieri after-market, oggi pre-market, oggi after-market)
    earnings = finnhub_client.earnings_calendar(
        _from=today - timedelta(days=1), to=today + timedelta(days=1),
        symbol=ticker
    )
    if earnings:
        return True  # SALTA: earnings recenti o imminenti

    # 2. Controlla RVOL pre-market come proxy per news non-earnings
    premarket_volume = get_premarket_volume(ticker, today)
    avg_premarket_volume = get_avg_premarket_volume(ticker, today, lookback=20)
    rvol = premarket_volume / avg_premarket_volume if avg_premarket_volume > 0 else 0
    if rvol > 3.0:
        return True  # SALTA: volume anomalo = probabile news ad alto impatto

    # 3. (Opzionale) Finnhub sentiment score
    if finnhub_sentiment_available:
        sentiment = finnhub_client.news_sentiment(ticker)
        if sentiment and sentiment.get("score", 0) > 0.6:
            return True  # SALTA: sentiment elevato

    return False  # OK: nessun evento rilevante
```

**Logica:** se UNO QUALUNQUE dei tre segnali è positivo → il ticker viene saltato. Questo è un OR logico, non un AND.

**Vantaggi dell'approccio combinato:**
- RVOL è oggettivo e misurabile, cattura M&A, regolatorie, crisis events
- Earnings calendar è deterministico, non dipende da dati di volume
- Sentiment (se disponibile) aggiunge un layer NLP per news testuali
- Se Finnhub è down: fallback a RVOL-only + log WARNING
- Se tutto è down: saltare TUTTI i ticker (conservativo)

---

## 9. Execution (Alpaca)

### 9.1 Fasi

1. **Paper trading** (obbligatorio prima del live): tutti gli ordini vanno all'endpoint paper di Alpaca
2. **Validazione:** almeno 30 giorni di paper trading con metriche coerenti col backtest
3. **Live:** switch a endpoint live con capitale reale

### 9.2 Ordini

- **Tipo:** bracket order (entry + TP + SL in unico ordine)
- **Time in force:** DAY (scade a fine giornata se non eseguito)
- **Entry:** stop-limit order. Stop price = opening range breakout level. Limit price = stop + 0.1% (per evitare esecuzioni troppo lontane dal breakout)
- **TP:** limit order a PrevClose
- **SL:** stop market order all'opening range low/high
- **SHORT check:** prima di inviare un ordine short, verificare `alpaca.get_asset(ticker).shortable`

**Nota sull'entry:** Per i breakout serve uno stop-limit order, non un limit order semplice. Se usassimo un limit order, il prezzo si allontanerebbe dal livello di entry prima del fill. Lo stop-limit si attiva al breakout e esegue entro il limite specificato.

### 9.3 Execution Model (ciclo di vita dell'ordine)

Ogni trade segue un modello di esecuzione esplicito, dal segnale fino alla posizione attiva:

```
SIGNAL ──▶ ORDER CREATED ──▶ BROKER ACCEPTED ──▶ EXCHANGE ROUTED
                                                       │
                                                       ▼
                                               PARTIAL FILL (qty < requested)
                                                       │
                                                       ▼
                                               COMPLETE FILL (qty = requested)
                                                       │
                                                       ▼
                                               POSITION ACTIVE
```

| Fase | Descrizione | Fallimento possibile |
|---|---|---|
| **SIGNAL** | La strategia genera un segnale LONG/SHORT | - |
| **ORDER CREATED** | Il modulo `broker.py` costruisce l'ordine (stop-limit bracket) e assegna `client_order_id` | Errore di validazione (es. prezzo fuori range) |
| **BROKER ACCEPTED** | Alpaca accetta l'ordine (HTTP 200) | HTTP 4xx/5xx → retry con backoff esponenziale |
| **EXCHANGE ROUTED** | L'ordine arriva all'exchange (NASDAQ/NYSE/ARCA) | Latenza di rete, exchange down |
| **PARTIAL FILL** | `filled_qty < requested_qty` — solo una parte delle azioni è stata eseguita | Vedi Sezione 9.4: Partial Fill |
| **COMPLETE FILL** | `filled_qty = requested_qty` — esecuzione completa | - |
| **POSITION ACTIVE** | Posizione aperta, SL/TP bracket attivi, monitoring iniziato | - |

### 9.4 Partial Fill Model (backtest)

Nel backtest, il partial fill NON è binario (filled/non-filled). Va simulato con un modello probabilistico:

```python
def simulate_fill(desired_qty: int, bar_volume: int, bar_index: int) -> tuple[int, float]:
    # 1. Probabilità di fill in funzione del rapporto volume
    volume_ratio = min(desired_qty / bar_volume, 1.0) if bar_volume > 0 else 0
    fill_probability = 1.0 - (0.3 * volume_ratio)  # più grande l'ordine, meno probabile il fill completo
    
    # 2. Se fill parziale, quanta quantità viene eseguita?
    if random.random() < fill_probability:
        filled_qty = desired_qty  # fill completo
    else:
        # Fill parziale: tra 30% e 90% della qty desiderata
        fill_pct = random.uniform(0.3, 0.9)
        filled_qty = int(desired_qty * fill_pct)
    
    # 3. Slippage aggiuntivo per fill parziale (esecuzione su più livelli)
    partial_slippage = 0.0
    if filled_qty < desired_qty:
        remaining_qty = desired_qty - filled_qty
        # La parte rimanente viene messa in coda di esecuzione
        # per le barre successive (execution queue)
        partial_slippage = 0.0002 * (remaining_qty / desired_qty)  # +2 bps per fill parziale
    
    return filled_qty, partial_slippage
```

**Regole per il partial fill nel backtest:**
- La quantità rimanente (`remaining_qty`) entra in una **execution queue**
- Alla barra successiva, si tenta di eseguire la quantità rimanente (con probabilità ridotta)
- Dopo 3 barre, la quantità non eseguita viene cancellata (ordine scaduto)
- Il trade viene registrato come "partial fill" nel log
- Le metriche usano solo la quantità effettivamente eseguita

### 9.5 Market Impact

**Dichiarazione per la v1:** Assumiamo market impact trascurabile finché:

```
position_value < 0.5% di ADV (Average Daily Volume)
```

Questo vincolo è realistico per capitali retail ($25k–$250k) su ticker S&P 500 liquidi (ADV > $500M).

Quando il capitale cresce oltre questa soglia (es. $500k, $1M, $2M), il market impact diventa significativo e va modellato esplicitamente:

| Capital | ADV richiesto (per stare sotto 0.5%) | Impatto sul modello |
|---|---|---|
| $25k | > $5M ADV | Trascurabile |
| $250k | > $50M ADV | Trascurabile per large-cap |
| $1M | > $200M ADV | Inizia a essere rilevante per mid-cap |
| $5M | > $1B ADV | Significativo: serve modello Almgren-Chriss o simile |

**Modello di market impact (futuro):**
- Componente temporanea: `η * σ * (Q / V)^β` (Almgren-Chriss)
- Componente permanente: `γ * σ * (Q / V)`
- Dove Q = quantità, V = volume medio, σ = volatilità

Per ora, il backtest include uno **slippage dinamico** (Sezione 4.6) che cattura l'effetto di primo ordine. Il market impact vero e proprio è differito alla v2.

### 9.6 Idempotenza e riconciliazione ordini

**Idempotenza:** Per evitare ordini duplicati in caso di retry/timeout/disconnessione:
- Ogni ordine inviato ad Alpaca usa un `client_order_id` deterministico:
  ```python
  client_order_id = f"{date}_{ticker}_{signal_type}_{attempt}"
  # Esempio: "2026-07-09_AAPL_LONG_1"
  ```
- Se la richiesta va in timeout, il retry con lo stesso `client_order_id` è idempotente (Alpaca lo riconosce e non duplica)

**Clock sync:**
- Usare NTP per sincronizzare l'orologio di sistema entro ±100ms
- Tutti i timestamp sono in EST (NYC), gestendoDST automaticamente
- Verificare `alpaca.get_clock()` all'avvio per confermare che il mercato sia aperto

**Order reconciliation (ogni minuto durante il trading):**
```python
def reconcile():
    local_positions = strategy.get_open_positions()
    broker_positions = alpaca.list_positions()
    local_orders = strategy.get_pending_orders()
    broker_orders = alpaca.list_orders(status='open')
    
    mismatches = compare(local_positions, broker_positions, local_orders, broker_orders)
    if mismatches:
        log_error(mismatches)
        alert_webhook(mismatches)
        # Risolvi: broker è source of truth
        strategy.sync_from_broker(broker_positions, broker_orders)
```

### 9.7 State recovery (crash recovery)

Se il sistema crasha e riparte intraday:
1. **Recupera posizioni aperte:** `alpaca.list_positions()` → recupera ticker, qty, entry price
2. **Recupera ordini aperti:** `alpaca.list_orders(status='open')` → identifica TP/SL bracket attivi
3. **Riconcilia:** confronta stato locale con stato broker → broker è source of truth
4. **Ripristina monitoraggio:** per ogni posizione aperta, riavvia il loop di monitoraggio TP/SL
5. **Logga l'evento:** scrivi crash + recovery su log + webhook alert

L'alternativa (se recovery non è affidabile): chiudere tutte le posizioni al restart e loggare.

---

## 10. Logging e Monitoring

### 10.1 Logging

- **Libreria:** `loguru` (più semplice e potente di `logging` standard)
- **Livelli:** DEBUG (sviluppo), INFO (produzione), WARNING (anomalie), ERROR (fallimenti)
- **Output:** file rotanti in `./logs/` (10 MB per file, retention 30 giorni) + console
- **Formato:** timestamp, livello, modulo, messaggio

### 10.2 Alerting

- **Webhook Discord/Slack:** notifiche per ERROR (es. Finnhub down, Alpaca order rejected, crash recovery)
- **Daily summary:** ogni giorno alle 16:30 EST, invia un riepilogo trade + P&L via webhook

---

## 11. Trading Calendar

Un trading calendar accurato è fondamentale per evitare bug subdoli (es. backtest che esegue trade il 4 luglio o il Black Friday half-day).

### 11.1 Eventi da gestire

| Evento | Impatto | Gestione |
|---|---|---|
| **NYSE Holidays** | Mercato chiuso | `pandas_market_calendars` per generare la lista dei trading day validi |
| **Half Days** (es. Black Friday, 3 luglio) | Mercato chiude alle 13:00 EST | EXIT forzata alle 12:50 EST invece delle 15:50 |
| **DST (Daylight Saving Time)** | L'orario di mercato slitta vs UTC | Tutti i timestamp interni sono in EST (US/Eastern) con `pytz`, gestendo DST automaticamente |
| **Auction Period** (15:50-16:00 EST) | La liquidità cala drasticamente | MAI eseguire trade dopo le 15:50 EST (Sezione 4.3) |
| **Early Close** (es. 13:00 EST) | Giorni particolari annunciati da NYSE | Controllare `pandas_market_calendars` per early close; EXIT forzata 10 minuti prima |
| **Circuit Breakers** | Trading halted su tutto il mercato | `alpaca.get_clock()` restituisce `is_open=False` durante halt → sospendere trading, loggare evento |

### 11.2 Implementazione

```python
import pandas_market_calendars as mcal

nyse = mcal.get_calendar('NYSE')
schedule = nyse.schedule(start_date='2020-01-01', end_date='2030-12-31')

# Genera la lista dei trading day validi
trading_days = schedule.index.date

# Per ogni giorno, controlla se è half-day o early-close
# schedule contiene market_open e market_close in UTC
# Convertire in EST per confrontare con l'orario standard (09:30-16:00)

def is_early_close(date):
    close_est = schedule.loc[date, 'market_close'].tz_convert('US/Eastern')
    return close_est.hour < 16  # chiude prima delle 16:00 EST
```

---

## 12. Performance Stack

Per dataset di milioni di barre (10 anni × 500 ticker × 78 barre/giorno = ~140M barre), Pandas inizia a soffrire. Stack raccomandato:

### 12.1 Stack primario

| Componente | Libreria | Vantaggio |
|---|---|---|
| **DataFrame engine** | **Polars** | 10-100x più veloce di Pandas su operazioni vettorizzate, zero-copy, multi-threaded nativo |
| **Analytical SQL** | **DuckDB** | Query SQL su file Parquet/CSV senza server, colonnare, ottimizzato per analytics |
| **Serialization** | **PyArrow / Parquet** | Formato colonnare compresso, lettura/scrittura veloce, interoperabile con Polars e DuckDB |

### 12.2 Quando usare cosa

| Operazione | Libreria consigliata | Note |
|---|---|---|
| Download + cache OHLCV | Pandas | yfinance restituisce Pandas DataFrames |
| Calcolo indicatori (SMA, ATR, ADX) | **Polars** | Molto più veloce su rolling window |
| Join tra timeframe diversi | **DuckDB** | SQL join sono più leggibili e ottimizzati |
| Grid search / ottimizzazione | **Polars** | Operazioni vettorizzate su griglia di parametri |
| Export report/metriche | Pandas | Compatibilità con matplotlib/seaborn |
| Storage intermedio | **Parquet** | Compresso, tipizzato, queryable via DuckDB |

### 12.3 Migrazione progressiva

- **V1:** Pandas + Parquet (semplice, funziona fino a ~10M barre)
- **V2:** Polars per indicatori e backtest engine (quando Pandas diventa collo di bottiglia)
- **V3:** DuckDB per analytics e query multi-ticker (quando servono join complessi)

---

## 13. Production Acceptance Checklist

Prima di passare in produzione con capitale reale, TUTTI i seguenti checkpoint devono essere verificati:

### 13.1 Edge Validation

- [ ] Edge dimostrato via EDA su S&P 500, 2014-2024
- [ ] Expectancy condizionale calcolata (per settore, VIX, regime, giorno, market cap)
- [ ] Monte Carlo simulation (1000 runs) → distribuzione dei ritorni
- [ ] Bootstrap resampling → intervalli di confidenza per Sharpe e Max DD
- [ ] Rolling hold-out validation (o WFA) → stabilità dei parametri nel tempo
- [ ] Plateau Detection → Sharpe max NON è un picco isolato

### 13.2 Paper Trading

- [ ] Paper trading su Alpaca per almeno 60 giorni di mercato
- [ ] Max drawdown entro il 25% durante il paper
- [ ] Slippage reale misurato e confrontato con il modello di backtest
- [ ] Fill rate reale ≥ 80% (almeno 8 ordini su 10 eseguiti)
- [ ] Nessun ordine duplicato (idempotenza verificata)
- [ ] Riconciliazione ordini testata: discrepanze broker vs locale risolte correttamente

### 13.3 Monitoring & Alerting

- [ ] Webhook Discord/Slack configurato e testato
- [ ] Daily summary funzionante (P&L, N trades, errori)
- [ ] Alert automatici per: Alpaca down, Finnhub down, ordine rifiutato, crash recovery
- [ ] Log audit: tutti i trade hanno un audit trail completo (segnale → ordine → fill → exit)

### 13.4 Resilience

- [ ] Recovery testato: kill del processo e restart → riconciliazione corretta
- [ ] Failover testato: Alpaca down → retry → alert
- [ ] Finnhub down → fallback a RVOL-only, loggato
- [ ] API stress test: 50 ticker scansionati simultaneamente, nessun rate limit colpito
- [ ] Chaos test superati (Sezione 14.3)
- [ ] Replay test: giornata registrata e rigiocata, output identici (Sezione 14.4)

### 13.5 Code Quality

- [ ] Unit test coverage > 90%
- [ ] Integration test coverage > 80%
- [ ] Deterministic backtest verificato (due run → stesso output)
- [ ] Nessun bug Critical o High aperto
- [ ] Type hints su tutte le funzioni pubbliche
- [ ] Performance benchmark: backtest 10 anni × 500 ticker in < 60 minuti

### 13.6 Security

- [ ] API keys in `.env`, MAI committate
- [ ] `.env.example` aggiornato con tutte le variabili necessarie
- [ ] Secrets audit: nessuna key hardcodata nel codice
- [ ] Rate limiting rispettato per tutte le API esterne
- [ ] Paper trading usa endpoint separato dal live (no rischio di esecuzione accidentale)

---

## 14. Testing

### 14.1 Unit test

| File | Cosa testa |
|---|---|
| `test_signals.py` | LONG/SHORT generati correttamente con dati sintetici |
| `test_news_filter.py` | Mock Finnhub API, filtro ticker |
| `test_risk.py` | Position sizing corretto con vari capitali |
| `test_metrics.py` | Calcolo Sharpe, Sortino, VaR su equity curve nota |
| `test_backtest.py` | Integrazione: loop backtest con dati mock |

### 14.2 Integration test

- Backtest su 1 anno di dati SPY reali → verifica output files generati
- Hold-out split: verifica che OOS non venga usato in calibrazione
- **Deterministic backtest:** due esecuzioni identiche (stessi dati, stessi parametri, stesso seed) devono produrre lo STESSO risultato bit-per-bit. Questo richiede:
  - Seed fissato per tutti i random number generator
  - Ordine deterministico di processing dei ticker (ordinamento alfabetico)
  - Nessuna dipendenza da tempo di sistema o risorse esterne nei calcoli
  - Test automatico: `pytest tests/test_determinism.py` che esegue il backtest due volte e confronta equity curve e trade log

### 14.3 Chaos testing

Test di resilienza per l'infrastruttura live. Simulare i seguenti scenari di failure:

| Scenario | Simulazione | Comportamento atteso |
|---|---|---|
| **Finnhub offline** | Mock HTTP 503 da Finnhub | Saltare news filter, loggare WARNING, procedere con RVOL-only |
| **Polygon offline** | Mock HTTP 503 da Polygon | Fallback a yfinance, loggare WARNING |
| **Alpaca offline** | Mock HTTP 503 da Alpaca | Retry con backoff esponenziale (1s, 2s, 4s, 8s, max 30s), poi ALERT |
| **DNS failure** | `socket.gethostbyname()` raise exception | Retry, poi ALERT |
| **Network latency** | Aggiungere 5s di delay artificiale alle chiamate API | Timeout handling, nessun crash |
| **Clock drift** | Alterare orologio di sistema di +5 minuti | Rilevare drift > 1s, loggare ERROR, usare `alpaca.get_clock()` come riferimento |
| **API timeout** | Timeout su 50% delle chiamate Alpaca | Retry idempotente con `client_order_id`, nessun ordine duplicato |
| **Duplicate WebSocket message** | Inviare lo stesso messaggio due volte | Deduplica basata su timestamp + sequence number |
| **Reconnect storm** | Chiudere e riaprire connessione WebSocket 10 volte in 30 secondi | Backoff jitter, rate limiting, non sovraccaricare Alpaca |

**Nota:** Chaos testing e Replay testing sono descritti nella Sezione 14.3 e 14.4.

### 14.4 Replay testing

Tecnica di testing avanzata:
1. **Registrare** un'intera giornata di dati reali da Polygon/Alpaca (tick data, order book snapshot, trade tape)
2. **Salvare** i dati in un file (es. `data/replay/2026-07-09.pqt`)
3. **Rigiocare** la giornata identica nel backtest engine, con lo stesso flusso di dati
4. **Confrontare** i segnali generati in replay con quelli generati live quel giorno

Questo permette di:
- Debuggare discrepanze tra backtest e live senza rischiare capitale reale
- Validare che la logica di segnali sia identica nei due ambienti
- Testare modifiche al codice su dati reali senza eseguire live

---

## 15. Riepilogo metriche attese

| Metrica | Target minimo | Note |
|---|---|---|
| Sharpe Ratio | > 1.0 | Risk-free rate = 4.5% (T-bill attuale) |
| Sortino Ratio | > 1.5 | Penalizza solo downside |
| Max Drawdown | < 25% | Con transaction costs |
| Win Rate | > 55% | Dopo filtri news/VIX |
| Profit Factor | > 1.3 | Profitto lordo / perdita lorda |
| Calmar Ratio | > 1.0 | CAGR / max DD |

*Nota: queste sono attese basate sulla letteratura accademica e su backtest pubblicati online, NON sono state ancora riprodotte in questa sessione. Verranno calcolate realmente durante la fase di implementazione su dati storici reali.*

---

## 16. Rischi e limitazioni

| Rischio | Mitigazione |
|---|---|
| **Regime change**: la strategia smette di funzionare in mercati fortemente trendanti | Filtro VIX, monitoraggio continuo OOS |
| **Overfitting**: parametri ottimizzati sul passato | Hold-out split, sensitivity analysis, plateau detection |
| **Slippage reale peggiore del modello** | Iniziare con paper trading per misurare slippage reale |
| **Finnhub rate limit / downtime** | Fallback: in assenza di dati news, saltare TUTTI i ticker (conservativo) |
| **Gap da earnings non rilevati** (dati mancanti) | Non eseguire trade se news_filter fallisce |
| **Esecuzione parziale** (ordine non filled) | Monitorare `filled_qty` vs `qty`, loggare slippage reale |

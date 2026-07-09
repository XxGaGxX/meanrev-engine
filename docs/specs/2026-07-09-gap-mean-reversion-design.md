# Gap Mean Reversion — Design Document

**Data:** 2026-07-09
**Autore:** Diego
**Versione:** 1.0
**Skill applicate:** brainstorming, quant-strategy-blueprint, quant-analyst, backtesting-trading-strategies

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
│   │   ├── scanner.py            # Scanner pre-market: gap%, filtro VIX
│   │   └── news_filter.py        # Filtro earnings/news (Finnhub)
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── signals.py            # Generazione segnali LONG/SHORT/EXIT
│   │   └── risk.py               # Position sizing, SL/TP
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py             # Loop backtest event-driven + walk-forward
│   │   ├── metrics.py            # Metriche (Sharpe, Sortino, VaR, Calmar, etc.)
│   │   └── optimize.py           # Grid search parametri
│   ├── execution/
│   │   ├── __init__.py
│   │   └── broker.py             # Integrazione Alpaca (paper + live) + state recovery
│   ├── logger.py                  # Logging + alerting (Discord/Slack webhook)
│   └── cli.py                    # CLI: backtest, optimize, scan, run
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
│   └── test_backtest.py
├── requirements.txt
├── .env.example
└── README.md
```

### 3.1 Responsabilità dei moduli

| Modulo | Cosa fa | Dipende da | Input | Output |
|---|---|---|---|---|
| `data/ohlcv.py` | Scarica OHLCV storici (giornalieri + intraday), caching locale | `config.py` | ticker list, date range | `DataFrame` con OHLCV |
| `data/scanner.py` | Calcola gap% pre-market, applica soglie, filtro VIX | `config.py`, `ohlcv.py` | `DataFrame` OHLCV | `List[str]` ticker validi + gap% |
| `data/news_filter.py` | Interroga Finnhub per earnings/news, esclude ticker con eventi | `config.py` | `List[str]` ticker | `List[str]` ticker filtrati |
| `strategy/signals.py` | Genera segnali LONG/SHORT/EXIT da regole booleane | Nessuna (pura logica) | `DataFrame` OHLCV + gap% + opening range | `pd.Series` con -1/0/+1 |
| `strategy/risk.py` | Calcola position size (1% risk), SL/TP in $ | `config.py` | capitale, entry_price, ATR | `dict` con size, sl, tp |
| `backtest/engine.py` | Loop storico giornaliero con walk-forward split, transaction costs, slippage | `signals.py`, `risk.py`, `ohlcv.py` | ticker, date range, split ratio | equity curve, trades list |
| `backtest/metrics.py` | Calcola tutte le metriche da equity curve | Nessuna (pura funzione) | equity curve, trades list | `dict` metriche |
| `backtest/optimize.py` | Grid search su parametri (gap_min, gap_max, lookback, VIX threshold) | `engine.py`, `metrics.py` | param grid, ticker, date range | migliori parametri + metriche |
| `execution/broker.py` | Invia ordini ad Alpaca (paper/live), gestisce stati, recovery dopo crash | `config.py`, `signals.py`, `risk.py` | segnali, size, sl, tp | order ID, fill status |
| `logger.py` | Logging strutturato + webhook alerts (Discord/Slack) | `config.py` | log level, messaggi | file di log, notifiche |
| `cli.py` | Entry point CLI | Tutti i moduli | argv | output testuale/CSV/PNG |

### 3.2 Data flow giornaliero (live)

```
08:00 EST  → news_filter.py → Finnhub API → esclude ticker con earnings/news
08:30 EST  → scanner.py → calcola VIX (da Alpaca/Polygon, non yfinance) → se VIX > 30: NO TRADE oggi
09:00 EST  → scanner.py → calcola gap% sui ticker rimanenti → applica soglie 0.3%–2.0%
09:00 EST  → risk.py → RANKING: ordina ticker per abs(gap%) decrescente, alloca capitale ai top N
09:30 EST  → segnali in attesa: raccoglie prime 15 barre (5min) per definire opening range
09:45 EST  → signals.py → conferma inversione (2 barre consecutive) → genera LONG/SHORT
09:45 EST  → broker.py → SHORT check: verifica che il ticker sia shortable (HTB = skip)
09:45 EST  → risk.py → calcola size (1% risk, con min stop distance) → broker.py → invia bracket order
Intraday  → signals.py monitora: TP (prev close) o SL (opening range low/high)
15:50 EST  → se trade ancora aperto: EXIT a mercato (15:50, non 16:00 — evita slippage di chiusura)
```

---

## 4. Regole della strategia

### 4.1 Parametri (in `config/settings.yaml`)

```yaml
strategy:
  gap_min_pct: 0.003        # 0.3% gap minimo
  gap_max_pct: 0.02         # 2.0% gap massimo
  opening_range_bars: 3     # 3 barre da 5min = 15 minuti
  confirmation_bars: 2      # 2 barre consecutive nella direzione del fill
  vix_max: 30.0             # VIX sopra questa soglia → no trade
  max_concurrent_trades: 5  # massimo trade simultanei (ranking per abs(gap%))

risk:
  risk_per_trade: 0.01      # 1% del capitale per trade
  min_stop_distance_pct: 0.001  # SL minimo 0.1% (evita divisione per zero)
  max_position_size: 0.95   # massimo 95% del capitale in una posizione

backtest:
  initial_capital: 25000    # capitale iniziale
  commission: 0.001         # 0.1% per trade
  slippage: 0.0005          # 0.05% slippage
  walk_forward_split: 0.7   # 70% in-sample, 30% out-of-sample

execution:
  broker: alpaca
  paper_trading: true       # paper inizialmente, poi live
```

### 4.2 Trigger logici

**LONG (gap down → buy to fill up):**
```
gap_pct = (Open - PrevClose) / PrevClose
VIX < vix_max
gap_pct between -gap_max_pct and -gap_min_pct
ticker NOT in earnings/news blacklist
opening_range_high = max(high[0:opening_range_bars])
price breaks above opening_range_high for confirmation_bars consecutive bars
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
price breaks below opening_range_low for confirmation_bars consecutive bars
→ ENTRY SHORT
→ TP = PrevClose
→ SL = max(high[0:opening_range_bars])
→ EXIT at TP OR SL OR 15:50 EST (15:50 per evitare slippage di chiusura)
```

### 4.3 Position sizing

```
risk_amount = capital * risk_per_trade                     # es. $25,000 * 1% = $250
stop_distance = max(abs(entry_price - SL), entry_price * min_stop_distance_pct)  # floor 0.1%
position_size = risk_amount / stop_distance                # numero di azioni
position_size = min(position_size, capital * max_position_size / entry_price)
```

### 4.4 Commissioni e slippage (applicati nel backtest)

```
entry_cost = entry_price * position_size * (1 + slippage + commission)
exit_cost = exit_price * position_size * (1 - slippage - commission)
pnl = (exit_price - entry_price) * position_size - entry_cost_slippage - exit_cost_slippage - commission_entry - commission_exit
```

**Nota sullo slippage:** 0.05% (5 bps) è uno slippage medio. Nelle prime barre dopo l'open lo slippage reale è maggiore. Il paper trading su Alpaca fornirà dati di slippage reale per calibrare questo parametro.

### 4.5 Allocazione multi-ticker

Quando più ticker gap simultaneously:
1. **Ranking:** ordina i ticker per `abs(gap%)` decrescente (gap più grandi = priorità)
2. **Allocazione:** alloca capitale ai primi `max_concurrent_trades` ticker
3. **Vincolo budget:** `sum(position_value) ≤ capital * max_position_size`
4. **Segnali non eseguiti:** i ticker oltre il limite vengono loggati ma ignorati

---

## 5. Backtest engine

### 5.1 Split in-sample / out-of-sample

Il backtest usa uno split temporale 70/30 (hold-out validation):
- **In-sample (70%):** usato per calibrare/validare i parametri
- **Out-of-sample (30%):** usato per il test finale, MAI toccato durante la calibrazione

**Nota:** Questo è uno split semplice, non un vero Walk-Forward Analysis (WFA) con finestre rolling. Un WFA completo con rolling window sarebbe preferibile per verificare la stabilità dei parametri attraverso diversi regimi di mercato, ma richiede più potenza computazionale. Per la v1 usiamo hold-out; la WFA è un upgrade futuro.

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
| **Risk-Adjusted** | Sharpe Ratio | Rendimento / volatilità (target: >1.0) |
| | Sortino Ratio | Rendimento / volatilità downside (target: >1.5) |
| | Calmar Ratio | CAGR / max drawdown |
| **Rischio** | Max Drawdown | Massimo picco-valle (%) |
| | VaR 95% | Value at Risk al 95% di confidenza |
| | CVaR 95% | Expected loss oltre il VaR |
| | Volatilità | Deviazione standard annualizzata |
| | Ulcer Index | Misura di drawdown persistente |
| **Trade** | Total Trades | Numero di trade round-trip |
| | Win Rate | % trade profittevoli |
| | Profit Factor | Profitto lordo / perdita lorda |
| | Expectancy | Valore atteso medio per trade ($) |
| | Avg Win / Avg Loss | Guadagno/perdita media ($) |
| | Max Consecutive Losses | Massima serie di perdite consecutive |

### 5.4 Output files

| File | Contenuto |
|---|---|
| `reports/backtest_summary.txt` | Riepilogo metriche formattato |
| `reports/backtest_trades.csv` | Log trade-by-trade (data, ticker, entry, exit, pnl, tipo) |
| `reports/backtest_equity.csv` | Equity curve giornaliera |
| `reports/backtest_chart.png` | Grafico equity curve + drawdown |

---

## 6. Parameter optimization

### 6.1 Grid search (`backtest/optimize.py`)

```yaml
param_grid:
  gap_min_pct: [0.001, 0.002, 0.003, 0.005]
  gap_max_pct: [0.01, 0.015, 0.02, 0.03]
  opening_range_bars: [2, 3, 5, 10]     # 10, 15, 25, 50 minuti
  confirmation_bars: [1, 2, 3]
  vix_max: [25, 30, 35]
```

**Funzione obiettivo:** Sharpe Ratio (in-sample). **Vincolo:** max drawdown < 25%.

L'ottimizzazione gira SOLO sui dati in-sample. I migliori parametri vengono poi validati sull'out-of-sample.

### 6.2 Sensitivity analysis

Dopo la grid search, per i parametri ottimali si esegue una sensitivity qualche punto percentuale attorno al valore ottimo per verificare la stabilità (no "cliff edge").

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

### 8.2 Impact scoring

L'impact score è calcolato come segue:
```python
CATEGORY_WEIGHTS = {
    "earnings": 1.0,
    "merger-acquisition": 0.9,
    "regulatory": 0.8,
    "product-launch": 0.4,
    "other": 0.2
}

def impact_score(news_item: dict) -> float:
    category_weight = CATEGORY_WEIGHTS.get(news_item.get("category"), 0.2)
    source_count = min(news_item.get("source_count", 1), 10) / 10  # normalizzato 0.1-1.0
    return category_weight * 0.7 + source_count * 0.3  # weighted average
```

Se Finnhub fornisce un sentiment score nativo (es. da `/news-sentiment`), usare quello con soglia `> 0.6`. Altrimenti usare lo scoring categorico sopra.

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

### 9.3 State recovery (crash recovery)

Se il sistema crasha e riparte intraday:
1. **Recupera posizioni aperte:** `alpaca.list_positions()` → recupera ticker, qty, entry price
2. **Recupera ordini aperti:** `alpaca.list_orders(status='open')` → identifica TP/SL bracket attivi
3. **Ripristina monitoraggio:** per ogni posizione aperta, riavvia il loop di monitoraggio TP/SL
4. **Logga l'evento:** scrivi crash + recovery su log + webhook alert

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

## 11. Testing

### 11.1 Unit test

| File | Cosa testa |
|---|---|
| `test_signals.py` | LONG/SHORT generati correttamente con dati sintetici |
| `test_news_filter.py` | Mock Finnhub API, filtro ticker |
| `test_risk.py` | Position sizing corretto con vari capitali |
| `test_metrics.py` | Calcolo Sharpe, Sortino, VaR su equity curve nota |
| `test_backtest.py` | Integrazione: loop backtest con dati mock |

### 11.2 Integration test

- Backtest su 1 anno di dati SPY reali → verifica output files generati
- Walk-forward: verifica che OOS non venga usato in calibrazione

---

## 12. Riepilogo metriche attese

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

## 13. Rischi e limitazioni

| Rischio | Mitigazione |
|---|---|
| **Regime change**: la strategia smette di funzionare in mercati fortemente trendanti | Filtro VIX, monitoraggio continuo OOS |
| **Overfitting**: parametri ottimizzati sul passato | Walk-forward split, sensitivity analysis |
| **Slippage reale peggiore del modello** | Iniziare con paper trading per misurare slippage reale |
| **Finnhub rate limit / downtime** | Fallback: in assenza di dati news, saltare TUTTI i ticker (conservativo) |
| **Gap da earnings non rilevati** (dati mancanti) | Non eseguire trade se news_filter fallisce |
| **Esecuzione parziale** (ordine non filled) | Monitorare `filled_qty` vs `qty`, loggare slippage reale |

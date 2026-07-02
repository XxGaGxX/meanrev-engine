# Roadmap Statistical Arbitrage — da zero a strategia live

Basata sulle 6 strategie dell'articolo Quantt. Ordine pensato per difficoltà crescente e riuso di quello che hai già (Python, C, XGBoost/LightGBM, ZeroMQ, CCXT, Alpaca).

---

## Fase 0 — Infrastruttura base
**Tempo: 3-5 giorni**
**Tech:** Python, `yfinance`/dati broker, `pandas`, `numpy`, Backtrader o Zipline (o il tuo motore C se vuoi riusarlo)

Cosa implementare:
- Data pipeline: scarico OHLCV storico per un universo di 50-100 titoli (stesso settore per iniziare, es. banche regionali USA o oil majors)
- Modulo di costi realistici: 10-30 bps round-trip su liquidi, 50+ bps su illiquidi — da inserire in ogni backtest fin da subito, non dopo
- Framework di backtest riutilizzabile (funzioni comuni: sizing, entry/exit, PnL, drawdown tracking)

Perché prima di tutto: senza questo ogni strategia successiva sarebbe backtestata in modo scorretto (overfitting, look-ahead bias non rilevati).

---

## Fase 1 — Pairs Trading
**Tempo: 1 settimana**
**Tech:** `statsmodels` (test di cointegrazione — Engle-Granger o Johansen), `pandas`

Cosa implementare:
- Screening automatico: per ogni coppia nel tuo universo, test di cointegrazione + correlazione storica
- Calcolo dello spread e rolling z-score (come nello snippet basket, ma su 2 asset)
- Regole di entry/exit su soglie z-score (es. ±2 entry, 0 exit)
- Backtest con costi + gestione del caso "breakout della relazione" (stop se lo spread non torna entro N giorni)

Nota: è la strategia con cui hai già più overlap concettuale con ICT/SMC (mean reversion su relazione tra asset).

---

## Fase 2 — Mean Reversion single-asset
**Tempo: 3-4 giorni**
**Tech:** solo `pandas`/`numpy`, nessuna libreria nuova

Cosa implementare:
- Funzione `mean_reversion_signal()` come da articolo (SMA + rolling std + zscore)
- Test su orizzonti diversi (intraday, 1-5 giorni) per capire dove l'edge è reale
- Filtro di regime: usa ADX o simile per capire se il mercato è trending (skip strategia) o range-bound (attiva strategia)

Questo step è rapido ma serve come baseline per confrontare le strategie più complesse.

---

## Fase 3 — Basket Arbitrage
**Tempo: 1 settimana**
**Tech:** stesso stack di Fase 0, più gestione pesi/ribilanciamento

Cosa implementare:
- Costruzione basket sintetico replicante (ETF top-N holdings pesati)
- Spread ETF vs basket + z-score rolling
- Gestione reweighting: alert quando i pesi dell'ETF cambiano (altrimenti la relazione si rompe silenziosamente)

Aspettativa realistica: come dice l'articolo, a livello retail competi con market maker su latenza — trattalo come esercizio di apprendimento più che come strategia da mandare live con size seria.

---

## Fase 4 — Momentum Reversal (Cross-Sectional)
**Tempo: 1-1.5 settimane**
**Tech:** `pandas` per quantili/decili, universo ampio (small/mid cap)

Cosa implementare:
- Formation period lungo (3-5 anni) + holding period (1 anno) — quindi serve storico dati profondo
- Ranking cross-sectional per decili, long bottom / short top
- Rebalancing periodico (mensile/trimestrale) invece che daily

Questa è più vicina a factor investing che a stat arb pura — utile soprattutto come diversificazione rispetto alle strategie a breve termine che hai già (momentum breakout su Alpaca).

---

## Fase 5 — ML-Based Stat Arb
**Tempo: 2-3 settimane**
**Tech:** `scikit-learn` (KMeans, Ridge), poi XGBoost/LightGBM che già usi, opzionale PyTorch per LSTM/Transformer

Cosa implementare:
- Feature engineering per clustering (volatilità, autocorrelazione, beta) — clusterizzi l'universo in "synthetic peer groups"
- Modello di regressione per predire il rendimento atteso di ogni stock dato il comportamento del cluster
- Trading sul residuo (actual - predicted), long/short sui decili estremi del residuo
- Validazione rigorosamente out-of-sample (walk-forward, non semplice train/test split) — qui riusi la disciplina che hai già da XGBoost/LightGBM nei bot di trading

Rischio principale: overfitting su pattern 2020-2024 che potrebbero non valere nel 2026. Prevedi retraining periodico e monitoraggio del decay dell'edge.

---

## Fase 6 — Integrazione infrastruttura live
**Tempo: 1-2 settimane**
**Tech:** il tuo stack esistente — Python (AI brain) + C (execution engine) via ZeroMQ, Alpaca API, CCXT se estendi a crypto

Cosa implementare:
- Position sizing con inverse-volatility weighting su portfolio di pairs/basket multipli
- Drawdown limits automatici e circuit breaker
- Monitoraggio capacity: volume giornaliero disponibile per ogni gamba della strategia
- Dashboard/log per tracciare decay dell'edge nel tempo (utile anche per Jarvis, se vuoi far confluire i log lì)

---

## Riepilogo tempi

| Fase | Strategia | Tempo |
|---|---|---|
| 0 | Infrastruttura | 3-5 gg |
| 1 | Pairs Trading | 1 sett |
| 2 | Mean Reversion | 3-4 gg |
| 3 | Basket Arbitrage | 1 sett |
| 4 | Momentum Reversal | 1-1.5 sett |
| 5 | ML-Based Stat Arb | 2-3 sett |
| 6 | Live integration | 1-2 sett |

**Totale: ~7-9 settimane** lavorando part-time (compatibile con exam prep di luglio se procedi a bassa intensità nelle fasi 0-2 prima degli esami, e concentri 3-6 dopo il 27 luglio).

Priorità se hai poco tempo ora: Fase 0 + Fase 1 (pairs trading) sono lo standalone più solido e riusano cose che già sai fare.
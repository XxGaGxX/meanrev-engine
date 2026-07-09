# Gap Mean Reversion — Roadmap MVP

**Data:** 2026-07-09
**Scope:** Strategia validata + backtest positivo + test di robustezza + paper trading funzionante
**Totale Fasi:** 11 (0–10)

**Goal MVP:** dimostrare, su dati reali, che l'edge esiste (o non esiste) e portarlo a girare in paper trading. Nient'altro. Niente infrastruttura da "production system".

## Cosa NON è in questo MVP (deferred a v2, dopo aver validato l'edge)

Docker, CI/CD, pre-commit hooks, kill switch automatico, alerting/monitoring hub, health check, secrets audit, data retention, API docs generator, sector/correlation constraints nel portfolio manager, Monte Carlo 10k simulazioni, chaos engineering, data replay test, migrazione Polars/DuckDB. Se una di queste si rivela necessaria *durante* l'MVP (es. le API key finiscono in un commit), la fai al minimo indispensabile, non la pianifichi come fase.

Motivo: costruire tutto questo prima di sapere se l'edge esiste è lavoro buttato se il gate di Fase 2 dice NO.

## Criterio di successo MVP (gate finale)

Il progetto è "MVP completo" solo se **tutti e tre** questi punti sono veri, con numeri reali stampati da codice eseguito — mai stimati:
1. Backtest out-of-sample (dati mai visti in fase di sviluppo) con Sharpe > 0 e profit factor > 1, al netto di commissioni e slippage stimati in modo realistico.
2. Walk-forward su almeno 2 finestre train/test consecutive senza degrado catastrofico tra le finestre (non basta un solo split 70/30).
3. Paper trading live su Alpaca per almeno 15-20 giorni di mercato, con segnali coerenti con quanto atteso dal backtest (stesso numero approssimativo di trade/settimana, stesso segno di edge).

Se il punto 1 fallisce, ti fermi a Fase 2 — non costruisci il resto.

---

## Fase 0 — Setup minimo

**Obiettivo:** struttura progetto essenziale, non enterprise.

**Output:**
- `requirements.txt` (pandas, numpy, yfinance, pyyaml, python-dotenv, matplotlib, pytest, alpaca-py)
- `.env` / `.env.example` con `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`
- `config/settings.yaml` — un solo file, tutti i parametri della strategia lì dentro (no hardcoding)
- `src/data/`, `src/strategy/`, `src/backtest/`, `src/execution/` (4 cartelle, non 15 moduli)
- `.gitignore` (`.env`, `data/cache/`, `__pycache__/`)

**Gate:** `python -c "import src"` non da errori. Basta.

---

## Fase 1 — Dati e Universe

**Obiettivo:** scaricare OHLCV giornalieri per l'universe di test.

**Output:**
- `scripts/download_data.py` — scarica OHLCV via yfinance per ~50-100 ticker large-cap USA liquidi (non serve l'universe storico completo con delisted per l'MVP — nota il survivorship bias nel report finale, ma non bloccarti a ricostruirlo ora)
- Cache in `data/cache/*.parquet`
- Periodo: minimo 5 anni, split già preparato: 70% development / 30% out-of-sample intoccato fino a Fase 6

**Gate:**
- [ ] Dati scaricati per tutti i ticker, nessun buco > 2 giorni consecutivi non giustificato da festività
- [ ] Il 30% out-of-sample è isolato in un file/flag separato e non viene toccato prima della Fase 6

---

## Fase 2 — EDA & Gate Decision (creazione strategia, parte 1)

**Obiettivo:** capire se il gap mean reversion ha un edge misurabile, PRIMA di scrivere strategia/backtest.

**Output:**
- `scripts/eda_gap_expectancy.py` — calcola `E[Return | gap size, direzione]` su dati reali
- Almeno 2 condizionamenti minimi: per settore (macro, non GICS fine) e per size del gap (bucket %)
- `reports/eda_gate_decision.md` con: Sharpe approssimato per bucket, N trade per cella (celle con N<20 = "dati insufficienti", non le usi), decisione: procedere / procedere con filtro / abbandonare

**Gate:**
- [ ] Almeno un bucket di gap ha edge positivo con N ≥ 30 trade sul development set
- [ ] Se nessun bucket regge → STOP, non si passa a Fase 3

---

## Fase 3 — Signal Generator (creazione strategia, parte 2)

**Obiettivo:** tradurre il pattern trovato in Fase 2 in una regola meccanica esatta.

**Output:**
- `src/strategy/signals.py` con funzione pura: input OHLCV → output segnale LONG/SHORT/FLAT, nessuno stato nascosto
- Condizioni LONG/SHORT/EXIT scritte come espressioni booleane esatte (non "quando sembra un buon setup")
- Parametri (soglia gap %, filtro volume, ecc.) in `config/settings.yaml`, presi direttamente dai bucket che hanno passato il gate in Fase 2

**Gate:**
- [ ] Unit test: dato un DataFrame sintetico con un gap noto, il segnale atteso viene generato
- [ ] Nessun parametro hardcoded nel codice

---

## Fase 4 — Risk & Position Sizing (versione base)

**Obiettivo:** SL/TP e sizing, niente di sofisticato.

**Output:**
- `src/strategy/risk.py`: stop loss basato su ATR, take profit basato su ATR o mean-reversion target, position sizing a rischio fisso per trade (es. 1% capitale)
- Niente vol-scaling dinamico, niente sector/correlation constraints — quello è v2

**Gate:**
- [ ] Formula SL/TP esatta documentata e testata su 3-4 casi noti a mano

---

## Fase 5 — Backtest Engine (core)

**Obiettivo:** un loop di backtest onesto, non un vectorized backtest ottimistico.

**Output:**
- `src/backtest/engine.py` — simula trade per trade, entry al prezzo di apertura post-segnale (non al close del giorno del segnale — evita il look-ahead bias più comune), commissioni + slippage stimato (anche solo uno spread fisso realistico in bps, non serve un fill simulator sofisticato)
- Output: equity curve, lista trade, metriche base (winrate, profit factor, Sharpe, max DD) — **calcolate da codice eseguito, mai stimate a mente**

**Gate:**
- [ ] Il backtest gira senza errori sul development set (70%)
- [ ] Nessun trade ha timestamp di entry precedente al timestamp del segnale (check anti look-ahead)

---

## Fase 6 — Backtest positivo su Out-of-Sample (checkpoint critico)

**Obiettivo:** il momento della verità. Qui si scopre se il progetto ha senso.

**Output:**
- Esecuzione del backtest di Fase 5 sul 30% out-of-sample mai toccato prima
- `reports/backtest_oos_results.md` con le metriche reali, confronto in-sample vs out-of-sample

**Gate — vedi Criterio di successo MVP punto 1:**
- [ ] Sharpe out-of-sample > 0 e profit factor > 1, al netto di costi
- [ ] Se il risultato out-of-sample è molto peggiore dell'in-sample (es. Sharpe dimezzato o segno invertito) → segnale di overfitting, si torna a Fase 2/3 a rivedere i filtri, non si va avanti forzando i parametri sull'OOS

---

## Fase 7 — Walk-Forward (test aggiuntivo 1)

**Obiettivo:** un solo split 70/30 non basta a fidarsi. Servono almeno 2 finestre.

**Output:**
- `scripts/walk_forward.py` — almeno 2 finestre train/test consecutive che scorrono nel tempo (es. train 2019-2022/test 2023, train 2020-2023/test 2024)
- `reports/walk_forward_results.md`

**Gate — vedi Criterio di successo MVP punto 2:**
- [ ] Nessuna finestra di test ha risultati radicalmente diversi (stesso segno di edge, ordine di grandezza simile di Sharpe)

---

## Fase 8 — Sensitivity check (test aggiuntivo 2)

**Obiettivo:** capire se la strategia dipende da un parametro magico invece che da un edge reale.

**Output:**
- `scripts/param_sensitivity.py` — variare i 2-3 parametri chiave (soglia gap, ATR multiplier per SL/TP) di ±20-30% e ricalcolare le metriche
- `reports/sensitivity_results.md`

**Gate:**
- [ ] Le metriche restano positive per un intorno ragionevole di parametri, non solo per il singolo valore ottimizzato (se crollano a zero con una variazione del 10%, è overfitting sui parametri, non edge)

---

## Fase 9 — Paper Trading Setup

**Obiettivo:** collegare la strategia validata ad Alpaca paper trading.

**Output:**
- `src/execution/alpaca_paper.py` — piazza ordini su Alpaca paper account seguendo esattamente la logica di Fase 3/4 (stessa funzione di signal generation usata nel backtest, non una riscritta — per evitare disallineamento backtest/live)
- Log dei trade in `logs/paper_trades.csv`
- CLI minima per avviare/fermare (`python -m src.execution.run_paper`)

**Gate:**
- [ ] Il primo trade piazzato in paper trading matcha esattamente cosa avrebbe fatto il backtest sugli stessi dati
- [ ] Nessuna API key nel codice o nei log committati

---

## Fase 10 — Paper Trading Run & Verifica finale

**Obiettivo:** far girare il sistema e confrontare comportamento live vs atteso.

**Output:**
- Run continuativo per 15-20 giorni di mercato
- `reports/paper_trading_review.md` — frequenza trade osservata vs attesa dal backtest, eventuali crash/bug operativi, confronto qualitativo P&L (troppo pochi trade in 20gg per un giudizio statistico, ma serve per beccare bug di esecuzione)

**Gate — vedi Criterio di successo MVP punto 3:**
- [ ] Sistema gira senza crash per tutto il periodo (o i crash sono stati loggati e capiti, non ignorati)
- [ ] Frequenza e direzione dei segnali coerenti con le attese del backtest

**A questo punto l'MVP è chiuso.** Solo se tutti e tre i criteri di successo sono soddisfatti, ha senso valutare le fasi "enterprise" della roadmap completa (kill switch, CI/CD, ecc.) prima di passare a capitale reale.

---

## Nota sui tempi

Con esami il 21 e 27 luglio, non pianificare l'esecuzione di questa roadmap prima di allora. Le Fasi 0-2 (setup + EDA gate) sono le uniche che vale la pena eventualmente incastrare in mezzo allo studio, perché è lì che scopri se vale la pena continuare — tutto il resto (Fasi 3-10) richiede tempo continuativo che ora non hai.
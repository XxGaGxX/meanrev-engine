# Gap Mean Reversion — Roadmap Audit v4.0

**Data:** 2026-07-09
**Versione roadmap analizzata:** v4.0 (48 fasi, 0–47)
**Scopo:** Identificare criticità quantitative, software e di produzione prima dell'upgrade a v5.0

---

## 1. Quantitative Audit

### 1.1 Survivorship Bias

**Severità:** 🔴 CRITICA

**Problema:** La roadmap attuale usa `yfinance` per scaricare i costituenti S&P 500 correnti e i loro dati storici. Questo introduce survivorship bias: i ticker che sono usciti dall'S&P 500 (fallimenti, acquisizioni, declassamenti) non sono inclusi nel dataset storico. La strategia viene backtestata solo su aziende che sono SOPRAVVISSUTE fino ad oggi.

**Impatto:** Sharpe Ratio e expectancy sono artificialmente gonfiati. La strategia sembra più profittevole di quanto sarebbe nella realtà, dove i ticker problematici sarebbero stati tradati prima del delisting.

**Risoluzione v5.0:** Nuova Fase "Historical Universe Reconstruction" che ricostruisce i componenti storici dell'S&P 500 (ticker entrati, usciti, delisted) e include TUTTI i ticker nel backtest, non solo i sopravvissuti.

### 1.2 Look-Ahead Bias

**Severità:** 🟡 MEDIA

**Problema:** Il backtest engine attuale potrebbe introdurre look-ahead bias in punti sottili:
- Calcolo indicatori (SMA, ADX) su dati che includono il giorno corrente
- Classificazione regime basata su dati non ancora disponibili al momento del trade
- Filtro news/earnings: le notizie del giorno vengono verificate PRIMA che il mercato apra, ma alcuni dati Finnhub potrebbero includere informazioni intraday

**Impatto:** Performance del backtest leggermente sovrastimate.

**Risoluzione v5.0:** Linee guida esplicite nel backtest engine per garantire che ogni decisione usi solo dati disponibili fino al timestamp della decisione. Shift temporale forzato per tutti gli indicatori (T-1 per dati giornalieri, barra corrente per intraday).

### 1.3 Overfitting Risk

**Severità:** 🔴 CRITICA

**Problema:** La grid search attuale (Fase 25) esplora 4×4×4×3×3×4×3 = 6,912 combinazioni su ~7 parametri. Con ~200 trade nella finestra in-sample, il rapporto trade/parametri è ~28:1, sotto la soglia minima raccomandata di 50:1.

**Impatto:** Alta probabilità di overfitting. I parametri "ottimali" performano bene sull'in-sample ma degradano significativamente sull'out-of-sample.

**Risoluzione v5.0:**
- Walk Forward Analysis con split Train/Validation/Test (mai ottimizzare sul test)
- Feature Selection & Robustness: ogni filtro deve dimostrare miglioramento statisticamente significativo
- Plateau detection: se il massimo Sharpe è un picco isolato (<5% dello spazio parametri), è overfitting
- Monte Carlo simulation per stress-test della robustness

### 1.4 Qualità Dataset

**Severità:** 🟡 MEDIA

**Problema:** `yfinance` fornisce dati gratuiti ma con limitazioni note:
- Dati intraday limitati a ~60 giorni
- Possibili dati mancanti o errati per ticker poco liquidi
- Nessuna garanzia di qualità per OHLCV storici
- Split/dividendi non sempre corretti

**Impatto:** Backtest potenzialmente inaccurato per periodi lunghi.

**Risoluzione v5.0:**
- Data Provider Abstraction Layer: possibilità di switchare a Alpaca Data API o Polygon per backtest production-grade
- Data Quality Validation già presente (Fase 8), ma rafforzata con cross-validation tra provider

### 1.5 Affidabilità Metriche

**Severità:** 🟡 MEDIA

**Problema:** Le metriche attuali (Fase 24) coprono la maggior parte degli indicatori standard, ma mancano:
- Deflated Sharpe Ratio (tiene conto del numero di trial nell'ottimizzazione)
- Probabilistic Sharpe Ratio
- Benchmark-relative metrics (vs SPY buy-and-hold)
- Turnover e market impact aggregati

**Impatto:** Le metriche potrebbero sovrastimare la significatività statistica della strategia.

**Risoluzione v5.0:** Metriche aggiuntive nella Fase 24 enhanced, con focus su statistical significance testing.

### 1.6 Validità Backtest

**Severità:** 🟡 MEDIA

**Problema:** Il backtest engine attuale è un loop giornaliero che simula barre 5min. Non è un vero event-driven backtester con order book simulato.

**Impatto:** Fill rate, slippage, e market impact sono approssimati. In produzione, l'esecuzione reale può differire significativamente.

**Risoluzione v5.0:** Backtest engine event-driven con Market Event → Signal → Order → Fill → Position → Portfolio flow esplicito.

---

## 2. Software Audit

### 2.1 Modularità

**Severità:** 🟢 BASSA

**Valutazione:** La struttura modulare (`src/data`, `src/strategy`, `src/portfolio`, `src/backtest`, `src/execution`) è ben progettata. Ogni modulo ha una responsabilità chiara.

**Raccomandazioni v5.0:**
- Data Provider Abstraction Layer per disaccoppiare la fonte dati dal resto del sistema
- Strategy Versioning per tracciare esperimenti e parametri

### 2.2 Dependency Management

**Severità:** 🟡 MEDIA

**Problema:** Il file `requirements.txt` corrente pinnare le versioni con `==`, ma non c'è un `requirements.lock` o `poetry.lock` per garantire riproducibilità esatta. Inoltre, dipendenze come `yfinance` possono rompersi con aggiornamenti lato server.

**Risoluzione v5.0:** Già presente Fase 1 (Dependency Lock). Aggiungere verifica periodica delle dipendenze nel CI/CD.

### 2.3 Testing

**Severità:** 🟢 BASSA

**Valutazione:** La roadmap include test suite completa (Fase 40), test di determinismo (Fase 41), chaos engineering (Fase 42), e data replay (Fase 43). Copertura eccellente per un progetto retail.

**Raccomandazioni v5.0:** Aggiungere property-based testing con `hypothesis` per funzioni critiche (signal generator, risk manager).

### 2.4 CI/CD

**Severità:** 🟢 BASSA

**Valutazione:** Pre-commit hooks (Fase 36), GitHub Actions (Fase 37), Docker (Fase 38) già presenti. Copertura completa.

### 2.5 Gestione Configurazioni

**Severità:** 🟡 MEDIA

**Problema:** `config/settings.yaml` contiene tutti i parametri, ma non c'è versioning delle configurazioni. Se si modifica un parametro e si esegue un backtest, non c'è traccia di QUALE configurazione ha prodotto QUALE risultato.

**Risoluzione v5.0:** Strategy Versioning con `config/strategies/gap_mean_reversion_v1.yaml`, v2.yaml, ecc. Ogni esperimento tracciato con experiment_id, strategy_version, dataset_version, parameters, results.

### 2.6 Scalabilità

**Severità:** 🟢 BASSA

**Valutazione:** La fase di Performance Migration (Fase 47, post-production) copre la scalabilità con Polars/DuckDB. Per la v1, Pandas è sufficiente.

---

## 3. Production Audit

### 3.1 Execution Risk

**Severità:** 🟡 MEDIA

**Problema:** L'esecuzione su Alpaca (Fase 29) è ben progettata, ma mancano:
- Gestione esplicita di partial fill in produzione (non solo simulazione)
- Gestione di order rejection con retry intelligente
- Circuit breaker per simboli specifici (es. trading halt su un ticker)

**Risoluzione v5.0:** Bracket order construction (Fase 30) e idempotency (Fase 31) coprono già questi aspetti. Aggiungere gestione trading halt nel kill switch.

### 3.2 Broker Integration

**Severità:** 🟢 BASSA

**Valutazione:** Broker Base API (Fase 29), Bracket Orders (Fase 30), Idempotency (Fase 31), e State Recovery (Fase 32) forniscono una copertura completa dell'integrazione broker.

### 3.3 Failure Recovery

**Severità:** 🟢 BASSA

**Valutazione:** State Recovery (Fase 32) con riconciliazione posizioni e audit trail copre il recovery dopo crash. Kill Switch (Fase 44) copre lo shutdown di emergenza.

### 3.4 Monitoring

**Severità:** 🟢 BASSA

**Valutazione:** Alerting (Fase 34), Health Check (Fase 35), e logging coprono il monitoring in produzione.

### 3.5 Kill Switch

**Severità:** 🟢 BASSA

**Valutazione:** Kill Switch (Fase 44) con max drawdown, ordini rifiutati, clock drift, e override manuale è completo.

---

## 4. Raccomandazioni Prioritarie per v5.0

| Priorità | Area | Azione | Nuova Fase |
|---|---|---|---|
| 🔴 P0 | Survivorship Bias | Historical Universe Reconstruction | NEW |
| 🔴 P0 | Overfitting | Walk Forward Analysis + Feature Selection + Monte Carlo | NEW ×3 |
| 🟡 P1 | Data Quality | Data Provider Abstraction Layer | NEW |
| 🟡 P1 | Riproducibilità | Strategy Versioning | NEW |
| 🟡 P1 | Backtest Accuracy | Event-Driven Backtest Engine upgrade | UPGRADE Fase 21 |
| 🟡 P1 | Metriche | Enhanced Metrics (Deflated Sharpe, PSR) | UPGRADE Fase 24 |

---

## 5. Conclusione

La roadmap v4.0 è un solido punto di partenza per un sistema di trading algoritmico retail. Le criticità principali sono nell'area quantitativa (survivorship bias, overfitting) e nella qualità dei dati (dipendenza da yfinance). La v5.0 affronta queste criticità con 6 nuove fasi e 2 upgrade, portando il sistema a un livello professionale di validazione statistica e robustezza.

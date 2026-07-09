# Gap Mean Reversion — Development Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan phase-by-phase. Each phase is an atomic, independently verifiable unit.

**Data:** 2026-07-09
**Autore:** Diego (Senior Architect)
**Versione Roadmap:** 5.1
**Documento di Riferimento:** `docs/specs/2026-07-09-gap-mean-reversion-design.md` v2.0
**Totale Fasi:** 54 (0–53)

**Goal:** Costruire un sistema di trading algoritmico production-ready che sfrutta la mean reversion dei gap di apertura su equity USA large-cap, con backtest rigoroso, esecuzione via Alpaca, CI/CD pipeline, kill switch, monitoring completo, e validazione quantitativa professionale.

**Architecture:** Sistema modulare Python con pipeline pre-market (scanner + filtro news), engine di segnali (gap mean reversion con conferma opening range), motore di backtest con hold-out split, modulo di esecuzione Alpaca con idempotenza e state recovery, kill switch automatico, e CLI unificata. Stack dati: Pandas → Polars/DuckDB per scalabilità. DevOps: pre-commit hooks, GitHub Actions CI/CD, Docker.

**Tech Stack:** Python 3.11+, Pandas/Polars, DuckDB, PyArrow/Parquet, yfinance, Finnhub API, Alpaca Markets API, pytest, loguru, matplotlib/seaborn, pandas_market_calendars, pytz, PyYAML, black, ruff, mypy, Docker, GitHub Actions.

## Global Constraints

- **Linguaggio:** Python 3.11+ (type hints su tutte le funzioni pubbliche)
- **API keys:** MAI committate; sempre in `.env`; `.env.example` aggiornato
- **No codice hardcodato:** tutti i parametri in `config/settings.yaml`
- **Nessuna modifica all'architettura** definita nel Design Document Sezione 3
- **Nessuna nuova funzionalità** oltre a quanto specificato nel Design Document
- **Nessuna modifica alla strategia quantitativa** definita nella Sezione 4
- **Nessun dato di performance inventato:** tutte le metriche vanno calcolate su dati reali
- **Prima di scrivere codice di produzione:** completare EDA (Fasi 3–5)
- **Prima del live:** completare paper trading (Fase 40) e Production Acceptance Checklist (Sezione 13 del Design Document)
- **DRY, YAGNI, TDD:** test scritti prima dell'implementazione dove applicabile
- **Coverage target:** unit test > 90%, integration test > 80%
- **Tutti i file seguono la struttura del progetto definita nella Sezione 3 del Design Document**

---

---

# MACRO FASE 0: FONDAMENTA

---

## Fase 0: Project Setup & Skeleton

### Titolo
Project Setup & Skeleton

### Obiettivo
Creare la struttura completa del progetto, inizializzare l'ambiente Python, creare i file di configurazione base e inizializzare Git.

### Motivazione
Senza una struttura di progetto solida, tutte le fasi successive sarebbero caotiche. Il Design Document (Sezione 3) definisce una struttura precisa che va rispettata. Questa fase crea lo scheletro su cui tutto il resto si appoggia.

### Prerequisiti
Nessuno.

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 3: Architettura del sistema)
- `docs/strategic-foundation-mean-reversion.md`

### Output (file creati)
- `requirements.txt` — dipendenze Python con versioni pinned
- `pyproject.toml` o `setup.cfg` — configurazione progetto
- `.env.example` — template variabili d'ambiente
- `.gitignore` — esclude `.env`, `data/cache/`, `logs/`, `reports/`, `__pycache__/`, `*.pyc`
- `src/__init__.py`
- `src/data/__init__.py`
- `src/strategy/__init__.py`
- `src/portfolio/__init__.py`
- `src/backtest/__init__.py`
- `src/execution/__init__.py`
- `tests/__init__.py`
- `config/` (directory vuota — `settings.yaml` creato nella Fase 1)
- `data/cache/` (directory vuota)
- `logs/` (directory vuota)
- `reports/` (directory vuota)
- `docs/` (già esistente)
- `README.md` — descrizione progetto, setup, usage

### Componenti coinvolti
- Root del progetto
- Directory `src/` e tutti i suoi sottopackage
- Directory `tests/`
- Directory `config/`
- Directory `data/cache/`
- Directory `logs/`
- Directory `reports/`

### Responsabilità
**Cosa FA:**
- Creare la struttura di directory come da Sezione 3 del Design Document
- Inizializzare `requirements.txt` con: `pandas`, `numpy`, `yfinance`, `pyyaml`, `python-dotenv`, `loguru`, `pytest`, `matplotlib`, `seaborn`, `pandas-market-calendars`, `pytz`, `requests`, `pyarrow`, `polars`, `duckdb`, `finnhub-python`, `alpaca-py` (o `alpaca-trade-api`)
- Creare `.env.example` con chiavi placeholder: `FINNHUB_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`, `DISCORD_WEBHOOK_URL`, `SLACK_WEBHOOK_URL`
- Creare `.gitignore` completo
- Inizializzare Git (`git init`) se non già fatto
- Scrivere `README.md` con: titolo, descrizione, prerequisiti, setup iniziale, struttura progetto

**Cosa NON FA:**
- NON scrive codice applicativo
- NON crea `config/settings.yaml` (Fase 1)
- NON installa pacchetti (l'agente lo fa manualmente dopo)
- NON configura virtual environment

### Criteri di completamento
- [ ] Tutte le directory create come da Sezione 3 del Design Document
- [ ] Tutti i file `__init__.py` creati e validi (possono essere vuoti)
- [ ] `requirements.txt` contiene tutte le dipendenze necessarie
- [ ] `.env.example` contiene tutte le variabili d'ambiente richieste
- [ ] `.gitignore` esclude file sensibili e generati
- [ ] `README.md` descrive il progetto in modo sufficiente per un nuovo sviluppatore
- [ ] `git init` eseguito (se non già presente)
- [ ] `python -c "import src"` non dà errori

### Test richiesti
- Nessun test automatico in questa fase (solo verifica manuale della struttura)

### Dipendenze
Da questa fase dipendono: **TUTTE le fasi successive** (0 → 1, 2, 3, …)

### Rischi
- **Rischio:** Struttura diversa da quella del Design Document → le fasi successive falliscono perché i path non corrispondono
  - **Mitigazione:** Verificare ogni directory contro la Sezione 3 del Design Document prima di completare
- **Rischio:** `.gitignore` incompleto → API keys committate accidentalmente
  - **Mitigazione:** Includere `.env`, `*.key`, `*.pem`, `data/cache/`

### Note implementative
- Usare `pathlib.Path.mkdir(parents=True, exist_ok=True)` per creare le directory
- I file `__init__.py` possono essere vuoti
- Non pinnare versioni eccessivamente restrittive in `requirements.txt`; usare `>=` con major version
- Il file `pyproject.toml` è opzionale per la v1; se creato, minimale

### Requisito Design Document
- Sezione 3 (Architettura del sistema)

---

## Fase 1: Dependency Lock & Virtual Environment

### Titolo
Dependency Lock & Virtual Environment

### Obiettivo
Generare `requirements-dev.txt`, configurare `pyproject.toml` con `[project.optional-dependencies] test`, documentare il setup dell'ambiente virtuale, e installare tutte le dipendenze.

### Motivazione
Un ambiente di sviluppo riproducibile è essenziale per evitare problemi di dipendenze tra ambienti diversi. Separare dipendenze runtime da dipendenze sviluppo permette deployment più snelli.

### Prerequisiti
- Fase 0 completata (struttura progetto esistente)

### Input
- `requirements.txt` (creato in Fase 0)
- `pyproject.toml` (creato in Fase 0)
- Struttura directory

### Output (file creati/modificati)
- **Modify:** `requirements.txt` — pinnare versioni esatte (`==`) dopo installazione
- **Create:** `requirements-dev.txt` — dipendenze sviluppo (pytest, pytest-cov, pytest-mock, black, ruff, mypy, freezegun)
- **Modify:** `pyproject.toml` — aggiungere sezioni `[tool.black]`, `[tool.ruff]`, `[tool.mypy]`
- **Create:** `docs/SETUP.md` — istruzioni setup ambiente
- Test: nessun test in questa fase

### Componenti coinvolti
- Root del progetto — `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`

### Responsabilità
**Cosa FA:**
- Installare dipendenze runtime e dev
- Pinnare versioni in `requirements.txt` dopo installazione (`pip freeze`)
- Configurare `pyproject.toml` con sezioni per black, ruff, mypy
- Scrivere `docs/SETUP.md` con istruzioni per venv, install, verify

**Cosa NON FA:**
- NON scrive codice applicativo
- NON configura CI/CD (Fase 49)

### Criteri di completamento
- [ ] `pip install -r requirements.txt` e `-r requirements-dev.txt` completano senza errori
- [ ] `python -c "import pandas, numpy, yfinance, yaml, loguru, pytest"` nessun errore
- [ ] `requirements-dev.txt` contiene black, ruff, mypy, pytest-cov, pytest-mock
- [ ] `pyproject.toml` configurato per black, ruff, mypy
- [ ] `docs/SETUP.md` descrive setup completo per nuovo sviluppatore

### Test richiesti
- Nessun test automatico

### Dipendenze
Da questa fase dipendono: **TUTTE le fasi successive** (ambiente pronto per sviluppo)

### Rischi
- **Rischio:** Conflitti di versione → installazione fallisce
  - **Mitigazione:** Risolvere conflitti prima di pinnare; testare `pip check`

### Note implementative
- Ambiente virtuale: `python -m venv .venv`, `source .venv/bin/activate` (o `.venv\Scripts\activate` su Windows)
- `pip freeze > requirements.txt` per pinnare
- Non committare `.venv/`

### Requisito Design Document
- Sezione 3 (Architettura), Sezione 12 (Performance Stack — dipendenze)

---

## Fase 2: Configuration & Environment

### Titolo
Configuration & Environment

### Obiettivo
Creare `config/settings.yaml` con tutti i parametri del sistema secondo la Sezione 4.2 del Design Document, e `src/config.py` per caricarlo.

### Motivazione
Tutti i parametri del sistema (strategia, risk, backtest, esecuzione) devono essere centralizzati e configurabili senza modificare il codice. Questo è il primo mattone su cui ogni altro modulo si appoggia.

### Prerequisiti
- Fase 0 completata (struttura progetto esistente)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 4.2: Parametri)
- Struttura directory creata nella Fase 0

### Output (file creati/modificati)
- **Create:** `config/settings.yaml` — YAML con TUTTI i parametri (strategy, risk, backtest, execution)
- **Create:** `src/config.py` — modulo che carica `settings.yaml`, gestisce override via env vars, fornisce accesso typed ai parametri

- Test: `tests/test_config.py` (fase 1)
### Componenti coinvolti
- `config/settings.yaml`
- `src/config.py`

### Responsabilità
**Cosa FA:**
- Creare `config/settings.yaml` con le sezioni `strategy`, `risk`, `backtest`, `execution` esattamente come da Sezione 4.2 del Design Document
- Includere TUTTI i parametri: `gap_min_pct`, `gap_max_pct`, `opening_range_bars`, `confirmation_bars`, `vix_max`, `adx_max`, `ema_period`, `rvol_max`, `max_concurrent_trades`, `max_per_sector`, `risk_per_trade`, `min_stop_distance_pct`, `max_position_size`, `volatility_scaling`, `initial_capital`, `base_slippage`, `open_slippage_extra`, `vol_adj_slippage`, `sec_fee_rate`, `finra_taf_per_share`, `finra_taf_cap`, `hold_out_split`, `broker`, `paper_trading`
- Creare `src/config.py` con:
  - Funzione `load_config(config_path: str = "config/settings.yaml") -> dict` che carica YAML e applica override da variabili d'ambiente (es. `STRATEGY_VIX_MAX` sovrascrive `strategy.vix_max`)
  - Supporto per notazione dot-separated nelle env vars (`STRATEGY_GAP_MIN_PCT` → `config["strategy"]["gap_min_pct"]`)
  - Type casting automatico (le env vars sono stringhe, i parametri possono essere float/int/bool)
  - Oggetto/singleton `Config` con accesso typed ai parametri
- Gestire variabili d'ambiente per API keys: `FINNHUB_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`

**Cosa NON FA:**
- NON modifica parametri oltre quanto specificato nella Sezione 4.2
- NON aggiunge nuovi parametri non presenti nel Design Document
- NON implementa validazione avanzata dei parametri (verrà in fase di hardening)

### Criteri di completamento
- [ ] `config/settings.yaml` contiene TUTTI i parametri della Sezione 4.2 con i valori di default specificati
- [ ] `src/config.py` importabile senza errori
- [ ] `load_config()` restituisce un dict con tutte le chiavi
- [ ] Override via env var funzionante (testato manualmente: `export STRATEGY_VIX_MAX=25 && python -c "from src.config import load_config; c = load_config(); assert c['strategy']['vix_max'] == 25"`)
- [ ] `Config` object accessibile: `Config.strategy.vix_max`, `Config.risk.risk_per_trade`, ecc.
- [ ] I commenti in `settings.yaml` spiegano il significato di ogni parametro
- [ ] Le variabili d'ambiente per API keys vengono lette da `.env` via `python-dotenv`

### Test richiesti
- **Unit test:** `tests/test_config.py`
  - Test caricamento YAML base
  - Test override env var per tipi: float, int, bool, string
  - Test env var inesistente non causa errori
  - Test `Config` object access

### Dipendenze
Da questa fase dipendono: **TUTTE le fasi che usano parametri** (3, 4, 6, 7, 8, 9, 10, 11, 13, 16, 17, 19, 21, 23)

### Rischi
- **Rischio:** Typo nei nomi dei parametri → moduli successivi non trovano i valori attesi
  - **Mitigazione:** Usare esattamente i nomi della Sezione 4.2; scrivere test che verificano la presenza di ogni chiave
- **Rischio:** Override env var non funziona per tipi non-string → `vix_max` rimane stringa "25" invece di float 25.0
  - **Mitigazione:** Implementare type casting basato sul tipo del valore di default in YAML

### Note implementative
- Usare `PyYAML` per il parsing; `python-dotenv` per `.env`
- L'oggetto `Config` può essere implementato come `types.SimpleNamespace` annidato o come dataclass
- Per l'override env var, convertire i nomi dei parametri in UPPER_SNAKE_CASE (es. `strategy.gap_min_pct` → `STRATEGY_GAP_MIN_PCT`)

### Requisito Design Document
- Sezione 4.2 (Parametri), Sezione 3 (Architettura)

---

# MACRO FASE 1: ALPHA RESEARCH (EDA GATE)

---

## Fase 3: Strategy Versioning & Experiment Tracking

### Titolo
Strategy Versioning & Experiment Tracking

### Obiettivo
Creare `config/strategies/` con file YAML versionati per ogni configurazione di strategia, e un sistema di experiment tracking per riproducibilita completa.

### Motivazione
Modificare un parametro in `settings.yaml` e rieseguire il backtest senza tracciare COSA e cambiato rende impossibile riprodurre risultati passati. Il strategy versioning garantisce che ogni backtest, paper trading, e produzione siano legati a una configurazione immutabile e versionata.

### Prerequisiti
- Fase 2 completata (Config)

### Input
- `config/settings.yaml`
- `src/config.py`

### Output (file creati/modificati)
- **Create:** `config/strategies/gap_mean_reversion_v1.yaml` -- configurazione base
- **Create:** `config/strategies/` -- directory per versioni future
- **Create:** `src/experiment.py` -- modulo experiment tracking
- **Modify:** `src/config.py` -- supporto `strategy_version` parameter
- **Create:** `reports/experiments/` -- directory per risultati esperimenti
- Test: `tests/test_experiment.py` (fase 3)

### Componenti coinvolti
- `config/strategies/`
- `src/experiment.py`
- `src/config.py`

### Responsabilita
**Cosa FA:**
- Creare `config/strategies/gap_mean_reversion_v1.yaml` con TUTTI i parametri attuali
- Struttura del file strategia con name, version, created, parameters
- `src/experiment.py` con classe `Experiment`: experiment_id UUID, strategy_version, dataset_version (hash), parameters (snapshot), start_time, end_time, results (dict metriche)
- `ExperimentTracker`: registra esperimenti in `reports/experiments/index.csv`, log_experiment(), get_latest(), compare()
- Il file v1.yaml e IMMUTABILE dopo la creazione; modifiche creano v2.yaml

**Cosa NON FA:**
- NON modifica i parametri esistenti (solo versioning)
- NON esegue backtest o ottimizzazione

### Criteri di completamento
- [ ] `config/strategies/gap_mean_reversion_v1.yaml` creato con tutti i parametri
- [ ] `src/experiment.py` importabile
- [ ] `Experiment` creato, serializzato, deserializzato con round-trip integro
- [ ] `ExperimentTracker` registra e recupera esperimenti
- [ ] `reports/experiments/index.csv` popolato dopo ogni esperimento
- [ ] `src/config.py` carica strategia da file versionato

### Test richiesti
- **Unit test:** `tests/test_experiment.py`
  - Test Experiment creation/serialization round-trip
  - Test ExperimentTracker.log_experiment() scrive nel index
  - Test ExperimentTracker.compare() calcola delta corretto
  - Test caricamento strategia da file YAML versionato

### Dipendenze
Da questa fase dipendono: TUTTE le fasi che usano parametri (versioning applicato ovunque)

### Rischi
- **Rischio:** Desincronizzazione tra `settings.yaml` e `strategies/v1.yaml`
  - **Mitigazione:** `settings.yaml` diventa un template; i valori reali sono sempre in `strategies/`
- **Rischio:** Experiment index corrotto da scritture concorrenti
  - **Mitigazione:** Append-only CSV con lock; single-process per v1

### Note implementative
- UUID: `import uuid; str(uuid.uuid4())`
- Dataset hash: `hashlib.sha256(pd.util.hash_pandas_object(df).values).hexdigest()[:16]`
- Experiment index CSV: `experiment_id, strategy_version, dataset_hash, start_time, sharpe, max_dd, win_rate`

### Requisito Design Document
- Global Constraints (riproducibilita), Sezione 6 (Optimization)


## Fase 4: Logger Base

### Titolo
Logger Base

### Obiettivo
Implementare `src/logger.py` con `loguru` per logging strutturato su file rotanti e console.

### Motivazione
Il logging è necessario per l'EDA, il backtest e l'esecuzione. Implementarlo subito permette a tutte le fasi successive di usarlo. La Sezione 10 del Design Document specifica `loguru` come libreria.

### Prerequisiti
- Fase 0 completata (struttura progetto)
- Fase 1 completata (config disponibile per log level e path)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 10.1: Logging)
- `src/config.py` (per `log_level` e `log_dir` path)

### Output (file creati/modificati)
- **Create:** `src/logger.py` — modulo logging con `loguru`
- **Modify:** `config/settings.yaml` — aggiungere sezione `logging` con `log_level`, `log_dir`, `log_retention`

- Test: `tests/test_logger.py` (fase 2)
### Componenti coinvolti
- `src/logger.py`
- `config/settings.yaml` (nuova sezione `logging`)

### Responsabilità
**Cosa FA:**
- Configurare `loguru` con:
  - Output su console (con colori) per livello DEBUG e superiori
  - Output su file rotanti in `logs/` (10 MB per file, retention configurabile)
  - Formato: `{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function}:{line} | {message}`
- Fornire helper: `get_logger(name: str) -> logger` che restituisce un logger con contesto
- Aggiungere sezione `logging` in `settings.yaml`: `log_level: "INFO"`, `log_dir: "logs"`, `log_retention: "30 days"`
- Rimuovere l'handler di default di `loguru` all'inizio

**Cosa NON FA:**
- NON implementa webhook/alerting (Fase 34)
- NON implementa daily summary (Fase 34)
- NON si occupa di log specifici di trading (quelli verranno nei moduli consumer)

### Criteri di completamento
- [ ] `src/logger.py` importabile senza errori
- [ ] `setup_logging()` configura loguru correttamente
- [ ] `get_logger("test").info("test message")` scrive su console e file
- [ ] I file di log vengono creati in `logs/`
- [ ] La rotazione funziona (verificabile con test che scrive >10MB)
- [ ] `config/settings.yaml` ha la sezione `logging`

### Test richiesti
- **Unit test:** `tests/test_logger.py`
  - Test che il logger scrive su file
  - Test che get_logger restituisce un logger funzionante
  - Test che il formato include timestamp, livello, modulo
  - Test che la directory `logs/` viene creata se non esiste

### Dipendenze
Da questa fase dipendono: **TUTTE le fasi che usano logging** (3, 4, 5, 6, 7, 8, 9, 11, 12, 15, 17, 20, 23, 28)

### Rischi
- **Rischio:** `loguru` non installato → ImportError
  - **Mitigazione:** Verificare che `loguru` sia in `requirements.txt` (Fase 0)
- **Rischio:** Permessi di scrittura su `logs/` insufficienti
  - **Mitigazione:** Gestire `PermissionError` con fallback a console-only + WARNING

### Note implementative
- `loguru` usa `logger.add()` per aggiungere sink; `logger.remove()` per rimuovere il default
- Per la rotazione: `rotation="10 MB"`, `retention="30 days"`
- Non serve una classe wrapper complessa; `loguru` è già sufficientemente potente

---

## Fase 5: EDA Data Downloader

### Titolo
EDA Data Downloader

### Obiettivo
Creare uno script di download dati per l'Exploratory Data Analysis: OHLCV giornalieri e intraday (5min) per i costituenti S&P 500, 2014–2024, con caching Parquet.

### Motivazione
La Sezione 0 del Design Document richiede EDA su 10 anni di dati S&P 500. Senza dati non si può calcolare expectancy, fill rate, o path dependency. Questa fase crea il dataset su cui girano le Fasi 4 e 5.

### Prerequisiti
- Fase 0 completata (struttura + requirements)
- Fase 2 completata (logger)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 0.1, 0.2, 7.1, 7.2)
- `config/settings.yaml` (opzionale — path cache)

### Output (file creati)
- **Create:** `scripts/eda_download.py` — script standalone per scaricare dati S&P 500
- **Create:** `data/cache/` popolata con file `.parquet` nel formato `{ticker}_daily_{start}_{end}.parquet` e `{ticker}_5min_{start}_{end}.parquet`
- **Create:** `data/sp500_tickers.csv` — lista ticker S&P 500 correnti (scaricata da Wikipedia o fonte alternativa)

### Componenti coinvolti
- `scripts/eda_download.py`
- `data/cache/`
- `data/sp500_tickers.csv`

### Responsabilità
**Cosa FA:**
- Scaricare la lista dei costituenti S&P 500 attuali (da Wikipedia o simile)
- Per ogni ticker, scaricare OHLCV giornaliero 2014-01-01 → 2024-12-31 via `yfinance`
- Per ogni ticker, scaricare OHLCV intraday 5min per il periodo disponibile (yfinance limita a ~60 giorni)
- Salvare ogni ticker in formato Parquet in `data/cache/`
- Gestire rate limiting di yfinance (delay tra richieste, retry con backoff)
- Loggare progresso (ticker X/500 completato)
- Verificare integrità dati dopo il download (nessun DataFrame vuoto, date continue)
- Salvare la lista ticker in `data/sp500_tickers.csv`

**Cosa NON FA:**
- NON calcola metriche di expectancy (Fase 5)
- NON fa analisi condizionale (Fase 7)
- NON implementa il caching generico di OHLCV (Fase 8) — questo è specifico per EDA
- NON scarica dati VIX o settoriali (aggiunti nella Fase 5 se necessario)

### Criteri di completamento
- [ ] `data/sp500_tickers.csv` contiene ~500 ticker
- [ ] Almeno 400 ticker hanno dati giornalieri 2014–2024 in `data/cache/`
- [ ] I file Parquet sono leggibili con `pd.read_parquet()`
- [ ] I DataFrame hanno le colonne: `Open`, `High`, `Low`, `Close`, `Volume` (daily) o `open`, `high`, `low`, `close`, `volume` (intraday)
- [ ] Nessun DataFrame è vuoto (0 righe)
- [ ] Lo script gestisce ticker delistati (yfinance restituisce `KeyError` o DataFrame vuoto → skip + log WARNING)
- [ ] Rate limiting rispettato: nessun HTTP 429 da yfinance

### Test richiesti
- **Integration test (manuale):** Eseguire lo script e verificare che completi senza errori
- **Unit test:** `tests/test_eda_download.py`
  - Test che la funzione `download_ticker` restituisce un DataFrame valido per un ticker noto (es. AAPL)
  - Test che `download_ticker` gestisce ticker inesistente (restituisce None o DataFrame vuoto)
  - Test che il salvataggio Parquet è leggibile

### Dipendenze
Da questa fase dipendono: **Fase 5, Fase 7** (EDA expectancy)

### Rischi
- **Rischio:** Rate limiting yfinance → script bloccato per ore
  - **Mitigazione:** Delay di 0.5–1s tra richieste; retry con backoff esponenziale (2s, 4s, 8s)
- **Rischio:** yfinance non ha dati intraday oltre 60 giorni → EDA su timeframe intraday limitato
  - **Mitigazione:** Per EDA iniziale, usare dati giornalieri (sufficienti per expectancy screening); Nota nel Design Document Sezione 1: i dati intraday lunghi richiedono Alpaca Data API o Polygon
- **Rischio:** Survivorship bias (yfinance non include ticker delistati)
  - **Mitigazione:** Documentato nel Design Document Sezione 1; per v1 è accettabile; per backtest rigorosi usare dati Alpaca/Polygon

### Note implementative
- Usare `yfinance.download()` con `progress=False` e `threads=False` per evitare output rumoroso
- Per la lista S&P 500: Wikipedia `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies` o `yfinance` ticker `^GSPC`
- I ticker con `.` (es. `BRK.B`) vanno normalizzati a `-` per yfinance (`BRK-B`)
- Salvare anche un file `data/sp500_tickers.csv` per riferimento

---

## Fase 6: Historical Universe Reconstruction

### Titolo
Historical Universe Reconstruction (Survivorship Bias Elimination)

### Obiettivo
Ricostruire i componenti storici dell'S&P 500 dal 2014 al 2024, includendo ticker entrati, usciti, delisted, e falliti. Produrre `data/universe/sp500_history.csv`.

### Motivazione
Usare solo i costituenti S&P 500 attuali per un backtest 2014-2024 introduce survivorship bias: le aziende che sono fallite o sono uscite dall'indice vengono escluse, gonfiando artificialmente le performance del backtest. Questa e la criticita quantitativa piu grave della v4.0 (vedi audit).

### Prerequisiti
- Fase 7 completata (EDA Download -- dati S&P 500 correnti)
- Fase 2 completata (Config)

### Input
- `data/sp500_tickers.csv` -- ticker correnti
- Dati storici da fonti pubbliche (Wikipedia)
- `docs/specs/2026-07-09-gap-mean-reversion-design.md`

### Output (file creati)
- **Create:** `data/universe/sp500_history.csv` -- storico componenti S&P 500
- **Create:** `src/data/universe.py` -- modulo universe reconstruction
- **Create:** `data/universe/delisted_tickers.csv` -- ticker rimossi con data e motivo
- Test: `tests/test_universe.py` (fase 6)

### Componenti coinvolti
- `data/universe/`
- `src/data/universe.py`

### Responsabilita
**Cosa FA:**
- `scrape_sp500_history(start_year=2014, end_year=2024) -> pd.DataFrame`: scarica cambiamenti S&P 500 da Wikipedia
- `build_historical_universe(date) -> list[str]`: ticker che erano nell'S&P 500 a quella data
- Formato `sp500_history.csv`: date, ticker, sector, market_cap, active (1=attivo, 0=rimosso)
- Includere data e motivo della rimozione (delisting, acquisizione, fallimento)
- Gestire ticker con `.` (BRK.B -> BRK-B per yfinance)
- `get_survivorship_free_universe(date) -> list[str]`: include TUTTI i ticker attivi a quella data

**Cosa NON FA:**
- NON scarica dati OHLCV per i ticker storici (lo fa EDA Download/OHLCV Cache)
- NON modifica lo scanner o il backtest (usano l'universe come input)

### Criteri di completamento
- [ ] `sp500_history.csv` contiene almeno 600 ticker unici (~20-30 cambi/anno x 10 anni)
- [ ] Per ogni anno 2014-2024, `build_historical_universe()` restituisce ~500 ticker
- [ ] Ticker noti rimossi (GE 2018, KSS, Macy's) marcati come `active=0`
- [ ] `delisted_tickers.csv` documenta motivo rimozione per ogni ticker
- [ ] Universe 2014 != universe 2024 (conferma cambiamento componenti)
- [ ] Nessun survivorship bias: il backtest usa l'universe storico, non quello corrente

### Test richiesti
- **Unit test:** `tests/test_universe.py`
  - Test `build_historical_universe(date(2014,1,2))` != `build_historical_universe(date(2024,1,2))`
  - Test `get_survivorship_free_universe()` include ticker non piu nell'indice
  - Test `sp500_history.csv` ha colonne corrette e date ordinate

### Dipendenze
Da questa fase dipendono: Fase 11 (EDA Simple usa universe storico), Fase 15 (OHLCV Cache)

### Rischi
- **Rischio:** Dati incompleti: Wikipedia potrebbe non avere TUTTI i cambiamenti
  - **Mitigazione:** Documentare la fonte; per production, usare CRSP o WRDS (a pagamento)
- **Rischio:** Ticker cambiano simbolo (FB -> META) -> universe contiene entrambi
  - **Mitigazione:** Mappare rinominazioni con `old_symbol -> new_symbol` mapping

### Note implementative
- Wikipedia URL: `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies`
- Tabella "Selected changes" nella sezione "Recent and upcoming changes"
- Per v1, accettare il 95% di accuratezza (Wikipedia); per production, migrare a fonte premium

### Requisito Design Document
- Sezione 0 (Pre-requisito: Alpha Research), Sezione 7 (Data Pipeline)
### Nota sui Dati Premium (Limitazione Wikipedia)

**Limitazione:** La ricostruzione dell'universe storico da Wikipedia ha ~95% di accuratezza. Per backtest rigorosi su 10 anni, errori nel 5% possono introdurre bias marginali.

**Piano di migrazione a fonti premium:**
1. **CRSP/WRDS (gold standard):** Dati istituzionali con Survivorship Bias-Free Database. Costo: ~$10K/anno per accesso accademico. Migrazione target: post paper trading.
2. **Polygon.io (retail premium):** Dati storici con delisting info. Costo: ~$50-200/mese. Migrazione target: prima del live trading.
3. **Validazione incrociata:** Confrontare universe Wikipedia vs Polygon per identificare discrepanze prima del go-live.

**Per v1 (paper trading):** Wikipedia e accettabile con documentazione esplicita della limitazione.
**Per v2 (live trading):** MIGRAZIONE OBBLIGATORIA a Polygon o fonte premium equivalente.



## Fase 7: EDA — Simple Expectancy

### Titolo
EDA — Simple Expectancy Screening

### Obiettivo
Calcolare l'expectancy semplice `E[Return | gap]` su dati S&P 500 2014–2024, producendo le tabelle della Sezione 0.1 del Design Document.

### Motivazione
Prima di investire tempo nell'implementazione, bisogna dimostrare che l'edge esiste. La Sezione 0.1 richiede: expectancy per gap bucket, fill rate reale, path dependency (SL vs TP), distribuzione gap, e frequenza trade.

### Prerequisiti
- Fase 4 completata (dati scaricati in `data/cache/`)

### Input
- `data/cache/*.parquet` — dati OHLCV giornalieri
- `data/sp500_tickers.csv` — lista ticker
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 0.1)

### Output (file creati)
- **Create:** `scripts/eda_simple_expectancy.py` — script di analisi
- **Create:** `reports/eda_simple_expectancy.csv` — tabella gap bucket → mean return, std, N trades
- **Create:** `reports/eda_fill_rate.csv` — tabella gap bucket → % fill entro fine giornata
- **Create:** `reports/eda_sl_vs_tp.png` — istogramma SL vs TP first hit per bucket
- **Create:** `reports/eda_gap_distribution.png` — istogramma distribuzione gap
- **Create:** `reports/eda_trade_frequency.csv` — media ± std trade/mese

### Componenti coinvolti
- `scripts/eda_simple_expectancy.py`

### Responsabilità
**Cosa FA:**
- Per ogni ticker e ogni giorno, calcolare `gap_pct = (Open - PrevClose) / PrevClose`
- Bucketizzare i gap: 0.3-0.5%, 0.5-1%, 1-2%, >2% (e speculari negativi)
- Per ogni bucket, calcolare: mean return intraday (`(Close - Open) / Open`), deviazione standard, N trades
- Per ogni bucket, calcolare fill rate: % di gap che toccano PrevClose durante la giornata
- Per ogni bucket, calcolare path dependency: % SL hit prima di TP (dove SL = opening range low/high simulato, TP = PrevClose)
- Generare istogramma della distribuzione dei gap (frequenza per dimensione)
- Calcolare soglie basate su percentili (es. 25° e 90° percentile della distribuzione gap)
- Contare trade validi al mese: media ± deviazione standard
- Salvare tutti gli output in `reports/`

**Cosa NON FA:**
- NON calcola expectancy condizionale per settore/VIX/giorno (Fase 7)
- NON implementa il backtest completo (Fase 22)
- NON applica filtri news/VIX (solo gap bucket semplici)
- NON calcola Sharpe o metriche avanzate

### Criteri di completamento
- [ ] Tabella `eda_simple_expectancy.csv` generata e popolata
- [ ] Tabella `eda_fill_rate.csv` generata e popolata
- [ ] Istogramma `eda_sl_vs_tp.png` generato
- [ ] Istogramma `eda_gap_distribution.png` generato con linee ai percentili 25°, 50°, 75°, 90°
- [ ] `eda_trade_frequency.csv` mostra media ± std trade/mese
- [ ] I risultati sono consistenti con le attese teoriche (fill rate decrescente per gap crescenti)
- [ ] Tutti gli output sono riproducibili (seed fissato dove necessario)

### Test richiesti
- **Unit test:** `tests/test_eda_simple.py`
  - Test `calculate_gap_pct(open_price, prev_close)` → valore corretto
  - Test `bucket_gap(-0.008)` → bucket "-1% to -0.5%"
  - Test `calculate_fill_rate` su dati sintetici con risultato noto
  - Test `calculate_path_dependency` su scenario dove SL viene sempre colpito prima di TP

### Dipendenze
Da questa fase dipende: **Fase 7** (EDA condizionale usa i risultati come baseline)

### Rischi
- **Rischio:** I dati mostrano edge debole o inesistente → la Fase 7 (gate) blocca il progetto
  - **Mitigazione:** Questo è il comportamento atteso; l'EDA serve proprio a validare o scartare l'ipotesi
- **Rischio:** Calcolo errato di PrevClose (usare `Close` shiftato invece della chiusura ufficiale)
  - **Mitigazione:** Verificare con dati noti (es. SPY su un giorno specifico); scrivere test con dati sintetici
- **Rischio:** Look-ahead bias (usare dati del giorno T per calcolare il segnale del giorno T)
  - **Mitigazione:** Per ogni giorno T, `PrevClose = Close[T-1]`, `Open = Open[T]`, `gap_pct = (Open[T] - Close[T-1]) / Close[T-1]`

### Note implementative
- Usare `pandas` per operazioni vettorizzate (evitare loop Python)
- L'opening range simulato per la path dependency: al posto delle barre 5min (che non abbiamo nei dati giornalieri), usare `(High - Low)` delle prime ore come proxy, oppure usare `Low` del giorno come SL per LONG e `High` come SL per SHORT (semplificazione per EDA)
- Documentare sempre la semplificazione nei commenti

---

## Fase 8: EDA — Conditional Expectancy & Gate Decision

### Titolo
EDA — Conditional Expectancy & Gate Decision

### Obiettivo
Calcolare l'expectancy condizionale su tutte le dimensioni della Sezione 0.2, produrre la matrice multidimensionale, e prendere la decisione di gate (procedere/bloccare/condizionale).

### Motivazione
L'expectancy semplice può essere fuorviante. Un edge che sembra solido nella media potrebbe essere inesistente in specifici settori o regimi. La Sezione 0.2 richiede analisi su 8 dimensioni + interazioni. La Sezione 0.3 definisce i criteri di gate.

### Prerequisiti
- Fase 4 completata (dati)
- Fase 5 completata (expectancy semplice come baseline)

### Input
- `data/cache/*.parquet` — dati OHLCV giornalieri
- `reports/eda_simple_expectancy.csv` — baseline
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 0.2, 0.3, 2.4)

### Output (file creati)
- **Create:** `scripts/eda_conditional_expectancy.py`
- **Create:** `reports/eda_conditional_matrix.csv` — tabella multidimensionale: gap bucket × settore × VIX bucket × giorno × regime × market cap × direzione → mean return, N trades
- **Create:** `reports/eda_sector_heatmap.png` — heatmap settore × gap bucket
- **Create:** `reports/eda_vix_impact.png` — line chart: mean return per VIX bucket
- **Create:** `reports/eda_interactions.csv` — interazioni 2-way più rilevanti
- **Create:** `reports/eda_gate_decision.md` — documento con la decisione di gate e la motivazione

### Componenti coinvolti
- `scripts/eda_conditional_expectancy.py`

### Responsabilità
**Cosa FA:**
- Per ogni dimensione (settore, VIX, giorno settimana, regime, market cap, ATR percentile, direzione gap), calcolare `E[Return | gap, dimensione]`
- Settore: mappare ogni ticker al suo settore GICS a 2 cifre (via yfinance `.info` o CSV statico)
- VIX: scaricare dati VIX da yfinance (`^VIX`); bucketizzare: <15, 15-20, 20-25, 25-30
- Giorno settimana: `df.index.dayofweek` (0=Lunedì, 4=Venerdì)
- Market regime: classificare ogni giorno secondo la Sezione 2.4 (Bull/Bear/Sideways/High Vol/Low Vol/Risk On/Risk Off)
- Market cap: quintili basati sulla capitalizzazione di mercato
- ATR percentile: ATR(14) relativo al prezzo, bucketizzato in quintili
- Direzione gap: LONG (gap down) vs SHORT (gap up)
- Interazioni: calcolare almeno le interazioni gap × settore × VIX
- Produrre heatmap e visualizzazioni
- Scrivere `eda_gate_decision.md` con:
  - Sharpe atteso (approssimato da mean return / std)
  - Classificazione: Edge confermato / Condizionale / Debole / Inesistente
  - Raccomandazione: procedere / procedere con filtri / rivedere / abbandonare
  - Evidenza a supporto (tabelle, grafici)

**Cosa NON FA:**
- NON implementa la strategia (è solo analisi)
- NON calcola metriche di backtest complete (Fase 24)
- NON modifica parametri di configurazione

### Criteri di completamento
- [ ] `eda_conditional_matrix.csv` contiene almeno 1000 righe (combinazioni di dimensioni)
- [ ] Tutti i grafici generati e salvati in `reports/`
- [ ] `eda_gate_decision.md` contiene una decisione chiara con motivazione
- [ ] Se edge confermato: Sharpe atteso > 0.5 su almeno il 60% delle dimensioni
- [ ] Se edge condizionale: identificati chiaramente i regimi/settori dove funziona e dove no
- [ ] Se edge debole/inesistente: documento spiega perché e cosa cambierebbe

### Test richiesti
- **Unit test:** `tests/test_eda_conditional.py`
  - Test classificazione regime: date note → regime atteso
  - Test bucket VIX: valore VIX → bucket corretto
  - Test mappatura settore: ticker noto → settore GICS corretto
  - Test interazione 2-way su dati sintetici

### Dipendenze
Da questa fase dipende: **TUTTA l'implementazione** (se gate = NO, il progetto si ferma qui)

### Rischi
- **Rischio:** Dati settoriali mancanti o errati per ticker delistati
  - **Mitigazione:** Per ticker senza settore, escludere dall'analisi settoriale ma includere nelle altre dimensioni
- **Rischio:** Classificazione regime instabile (un giorno può essere sia Bull che Risk On)
  - **Mitigazione:** I regimi NON sono mutuamente esclusivi; un giorno può appartenere a più regimi. Ogni trade viene etichettato con tutti i regimi applicabili.
- **Rischio:** Overfitting nell'analisi condizionale (troppe dimensioni, pochi trade per cella)
  - **Mitigazione:** Riportare N trades per ogni cella; celle con N < 20 vanno marcate come "dati insufficienti"

### Note implementative
- Per la classificazione del regime, servono: 200SMA (da OHLCV giornalieri), ADX(14) (calcolato), VIX (da `^VIX`)
- ADX può essere calcolato con `pandas-ta` o manualmente
- Per market cap: usare `yfinance.Ticker(ticker).info['marketCap']` al momento dell'analisi (non storico perfetto, ma accettabile per EDA)
- Documentare esplicitamente che la classificazione regime è semplificata per l'EDA (non usa dati intraday)

---

# MACRO FASE 2: DATA LAYER

---

## Fase 9: Feature Selection & Robustness

### Titolo
Feature Selection & Robustness Analysis

### Obiettivo
Validare statisticamente ogni filtro della strategia (VIX, ADX, 200EMA, RVOL, settore, giorno settimana) dimostrando che migliora il risk-adjusted return rispetto alla baseline senza filtro.

### Motivazione
Aggiungere filtri senza validazione statistica e la causa principale di overfitting nel trading quantitativo. Ogni filtro riduce il numero di trade e deve dimostrare che il trade-off tra meno trade e migliore qualita e positivo. Un filtro viene mantenuto SOLO se migliora lo Sharpe ratio della baseline in modo statisticamente significativo.

### Prerequisiti
- Fase 12 completata (EDA Conditional)
- Fase 11 completata (EDA Simple)
- Fase 7 completata (EDA Download)

### Input
- `reports/eda_simple_expectancy.csv`
- `reports/eda_conditional_matrix.csv`
- `data/universe/sp500_history.csv`
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 2.1, 2.2, 2.3)

### Output (file creati)
- **Create:** `scripts/feature_selection.py`
- **Create:** `reports/filter_analysis.csv` -- analisi comparativa filtri
- **Create:** `reports/filter_heatmap.png`
- **Create:** `reports/feature_selection_report.md`
- Test: `tests/test_feature_selection.py` (fase 9)

### Componenti coinvolti
- `scripts/feature_selection.py`

### Responsabilita
**Cosa FA:**
- Per OGNI filtro (VIX, ADX, 200EMA, RVOL, settore, giorno settimana):
  - Calcolare metriche della strategia CON e SENZA il filtro
  - Calcolare delta: `Sharpe_con_filtro - Sharpe_senza_filtro`
  - Calcolare impatto sul numero di trade: `N_trades_con / N_trades_senza`
  - Bootstrap del delta Sharpe con 1000 campioni, intervallo di confidenza 95%
- Criterio KEEP: Delta Sharpe > 0, IC 95% NON include zero, N_trades ridotto non piu del 50%
- Criterio REMOVE: Delta Sharpe <= 0 O IC include zero O N_trades ridotto > 50%
- `filter_analysis.csv`: filter, baseline_sharpe, filtered_sharpe, delta_sharpe, ci_lower, ci_upper, pct_trades_remaining, decision
- `feature_selection_report.md`: raccomandazioni finali con motivazione statistica

**Cosa NON FA:**
- NON modifica la strategia (solo analisi)
- NON implementa nuovi filtri (solo validazione di quelli esistenti)
- NON sostituisce la grid search

### Criteri di completamento
- [ ] `filter_analysis.csv` generato con TUTTI i filtri analizzati
- [ ] Per ogni filtro: baseline, filtered, delta, CI, decision
- [ ] Filtri con delta negativo o non significativo marcati REMOVE
- [ ] Filtri con delta positivo e significativo marcati KEEP
- [ ] `feature_selection_report.md` spiega il razionale di ogni decisione
- [ ] Bootstrap CI calcolato con 1000 iterazioni

### Test richiesti
- **Unit test:** `tests/test_feature_selection.py`
  - Test bootstrap CI su dati sintetici
  - Test decision logic: delta positivo + CI non include zero -> KEEP
  - Test decision logic: delta positivo ma CI include zero -> REMOVE
  - Test decision logic: N_trades ridotto > 50% -> REMOVE

### Dipendenze
Da questa fase dipende: Fase 14 (Data Provider), Fase 21 (Scanner -- parametri finali decisi qui)

### Rischi
- **Rischio:** Bootstrap su pochi trade produce CI troppo ampi -> tutti i filtri non significativi
  - **Mitigazione:** Usare dati 2014-2024 (10 anni); se N_trades < 100, il test perde potenza
- **Rischio:** Rimuovere troppi filtri -> overfitting ridotto ma performance peggiori in production
  - **Mitigazione:** Trade-off documentato; la robustezza e prioritaria sul fit storico

### Note implementative
- Bootstrap: `sklearn.utils.resample` o implementazione manuale con `np.random.choice`
- Heatmap: `seaborn.heatmap` con filtro sulle righe, metriche sulle colonne
- Per la baseline senza filtro: disabilitare TUTTI i filtri tranne gap_min/gap_max

### Requisito Design Document
- Sezione 0.3 (Gate Decision), Sezione 2 (Filtri), Sezione 6 (Optimization)



## Fase 10: Data Provider Abstraction Layer

### Titolo
Data Provider Abstraction Layer

### Obiettivo
Implementare `src/data/providers/` con un'interfaccia comune `MarketDataProvider` e implementazioni per Yahoo Finance, Alpaca Data API, e Polygon.io.

### Motivazione
La roadmap v4.0 dipende esclusivamente da `yfinance`, che e adeguato per EDA e prototipazione ma insufficiente per backtest intraday (dati limitati a 60 giorni) e produzione (nessuna garanzia di qualita). Il Data Provider Abstraction Layer permette di switchare provider senza modificare scanner, strategy, o backtester.

### Prerequisiti
- Fase 2 completata (Config)
- Fase 5 completata (Logger)

### Input
- `src/config.py`
- `src/logger.py`
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 7)

### Output (file creati)
- **Create:** `src/data/providers/__init__.py`
- **Create:** `src/data/providers/base.py` -- classe astratta MarketDataProvider
- **Create:** `src/data/providers/yahoo.py` -- implementazione Yahoo Finance
- **Create:** `src/data/providers/alpaca.py` -- implementazione Alpaca Data API
- **Create:** `src/data/providers/polygon.py` -- implementazione Polygon.io
- **Modify:** `config/settings.yaml` -- aggiungere data_provider parameter
- Test: `tests/test_providers.py` (fase 10)

### Componenti coinvolti
- `src/data/providers/`
- `config/settings.yaml`

### Responsabilita
**Cosa FA:**
- `base.py` -- Classe astratta MarketDataProvider con metodi: get_daily_data, get_intraday_data, get_pre_market_data, get_historical_universe, get_vix
- `yahoo.py` -- YahooProvider: wrapper yfinance esistente, rate limiting, retry
- `alpaca.py` -- AlpacaProvider: Alpaca Data API v2, dati intraday illimitati
- `polygon.py` -- PolygonProvider: Polygon.io API, dati intraday storici completi
- `ProviderFactory.get_provider(name) -> MarketDataProvider`: default Yahoo
- Tutti i DataFrame con colonne standardizzate (lowercase, timezone-aware)
- `data_provider: "yahoo"` in `config/settings.yaml`

**Cosa NON FA:**
- NON riscrive il codice yfinance esistente (lo wrappa)
- NON implementa streaming/websocket (solo REST storico)

### Criteri di completamento
- [ ] YahooProvider.get_daily_data funzionante
- [ ] ProviderFactory.get_provider("yahoo") restituisce YahooProvider
- [ ] DataFrame hanno colonne standardizzate: open, high, low, close, volume
- [ ] Timezone-aware: tutti i timestamp in US/Eastern
- [ ] config/settings.yaml ha data_provider parameter

### Test richiesti
- **Unit test:** `tests/test_providers.py`
  - Test YahooProvider con mock
  - Test ProviderFactory con nome valido e invalido
  - Test tutti i provider implementano l'interfaccia completa
  - Test DataFrame hanno colonne corrette e timezone

### Dipendenze
Da questa fase dipendono: Fase 15 (OHLCV Cache usa provider), Fase 21 (Scanner), Fase 31 (Backtest)

### Rischi
- **Rischio:** Provider diversi restituiscono dati leggermente diversi
  - **Mitigazione:** Per backtest production, usare UN solo provider; Yahoo per EDA
- **Rischio:** Costi API: Alpaca Data e Polygon sono a pagamento
  - **Mitigazione:** Yahoo per EDA/prototipazione; Alpaca/Polygon per backtest finale e produzione

### Note implementative
- ABC da `abc` module: `from abc import ABC, abstractmethod`
- AlpacaProvider usa `alpaca-py` (gia in requirements)
- Per v1, Yahoo e il default; Alpaca e Polygon sono opzionali

### Requisito Design Document
- Sezione 7 (Data Pipeline), Sezione 12 (Performance & Scalability)

## Fase 11: OHLCV Cache Pipeline

### Titolo
OHLCV Cache Pipeline

### Obiettivo
Implementare `src/data/ohlcv.py`: download OHLCV giornalieri e intraday con caching Parquet, come da Sezioni 7.1 e 7.2 del Design Document.

### Motivazione
Il modulo OHLCV è la fondamenta di tutti i dati. Scanner, backtest, e EDA dipendono da esso. Il caching Parquet evita rate limiting e accelera le esecuzioni successive.

### Prerequisiti
- Fase 1 completata (config)
- Fase 2 completata (logger)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 7.1, 7.2)
- `src/config.py`
- `src/logger.py`

### Output (file creati/modificati)
- **Create:** `src/data/ohlcv.py`
- **Create:** `tests/test_ohlcv.py`

### Componenti coinvolti
- `src/data/ohlcv.py`
- `data/cache/`

### Responsabilità
**Cosa FA:**
- Funzione `download_daily(ticker: str, start: str, end: str) -> pd.DataFrame`: scarica OHLCV giornalieri da yfinance, salva in `data/cache/{ticker}_daily_{start}_{end}.parquet`
- Funzione `download_intraday(ticker: str, start: str, end: str, interval: str = "5m") -> pd.DataFrame`: scarica OHLCV intraday
- Funzione `load_daily(ticker: str, start: str, end: str) -> pd.DataFrame`: carica da cache se esiste, altrimenti scarica
- Funzione `load_intraday(ticker: str, start: str, end: str, interval: str = "5m") -> pd.DataFrame`: idem per intraday
- Funzione `load_multiple(tickers: list[str], start: str, end: str, interval: str = "1d") -> dict[str, pd.DataFrame]`: carica/scarica in batch
- Funzione `clear_cache(ticker: str | None = None)`: pulisce la cache
- Funzione `get_cache_path(ticker: str, interval: str, start: str, end: str) -> Path`: path deterministico
- Gestione rate limiting: delay configurabile tra richieste, retry con backoff esponenziale
- Gestione errori: ticker delistato (log WARNING, skip), rete down (retry, poi log ERROR)
- Normalizzazione colonne: tutte lowercase (`open`, `high`, `low`, `close`, `volume`)
- Verifica integrità dopo download: nessun NaN nelle colonne OHLC, date ordinate

**Cosa NON FA:**
- NON calcola indicatori tecnici (SMA, ATR, ADX) — quelli vengono calcolati nei moduli consumer (scanner, signals)
- NON gestisce dati in tempo reale/streaming (solo storico)
- NON implementa fonti dati alternative a yfinance (Polygon, Alpaca Data) — upgrade futuro

### Criteri di completamento
- [ ] `download_daily("AAPL", "2024-01-01", "2024-12-31")` restituisce DataFrame con ~252 righe
- [ ] Seconda chiamata con stessi parametri carica da cache (nessuna richiesta HTTP)
- [ ] `load_multiple(["AAPL", "MSFT", "GOOGL"], "2024-01-01", "2024-12-31")` restituisce dict con 3 DataFrame
- [ ] Ticker inesistente: log WARNING, restituisce DataFrame vuoto, non crasha
- [ ] Rate limiting: se yfinance restituisce 429, retry dopo delay
- [ ] Cache file segue il formato: `data/cache/{ticker}_{interval}_{start}_{end}.parquet`
- [ ] Type hints su tutte le funzioni pubbliche

### Test richiesti
- **Unit test:** `tests/test_ohlcv.py`
  - Test `download_daily` con mock di yfinance
  - Test `load_daily` carica da cache quando il file esiste
  - Test `load_daily` scarica quando il file NON esiste
  - Test `get_cache_path` restituisce path corretto
  - Test ticker invalido → DataFrame vuoto + log WARNING
  - Test rate limiting → retry chiamato
  - Test `clear_cache` rimuove i file

### Dipendenze
Da questa fase dipendono: **Fase 15 (Scanner), Fase 23 (Backtest Engine)**

### Rischi
- **Rischio:** Parquet non installato → ImportError
  - **Mitigazione:** `pyarrow` o `fastparquet` in `requirements.txt` (Fase 0)
- **Rischio:** Cache corrotto (file Parquet illeggibile)
  - **Mitigazione:** `try/except` su `pd.read_parquet()`; se fallisce, rimuovi file corrotto e riscarica
- **Rischio:** Due processi scrivono lo stesso file contemporaneamente
  - **Mitigazione:** Per v1, non gestire concorrenza (single-process); documentare come limitazione

### Note implementative
- yfinance restituisce colonne con nomi che variano; normalizzare sempre a lowercase
- Per la cache key: `f"{ticker}_{interval}_{start}_{end}.parquet"`
- Gestire `yfinance` errori: `yfinance.YFinanceError`, `KeyError` per ticker delistati
- Delay default: 0.5s tra richieste; backoff: 2s, 4s, 8s, max 30s

---

## Fase 12: Data Quality Validation

### Titolo
Data Quality Validation

### Obiettivo
Verificare la qualità dei dati scaricati: completezza (no gap > 3 giorni lavorativi), qualità (no outlier OHLCV, no volume = 0 su giorni di trading), e allineamento timestamp (timezone EST). Produrre `reports/data_quality_report.csv`.

### Motivazione
Dati di scarsa qualità producono backtest inaffidabili. Gap di 5 giorni o volume=0 indicano dati corrotti. Senza validazione, bug nei dati si propagano silenziosamente.

### Prerequisiti
- Fase 8 completata (OHLCV cache popolata)
- Fase 11 completata (Trading Calendar — per verificare giorni di trading)

### Input
- `data/cache/*.parquet` — dati OHLCV
- `src/data/calendar.py` — giorni di trading attesi

### Output (file creati)
- **Create:** `src/data/quality.py`
- **Create:** `reports/data_quality_report.csv`
- Test: `tests/test_data_quality.py`

### Componenti coinvolti
- `src/data/quality.py`

### Responsabilità
**Cosa FA:**
- `check_completeness(df, calendar, ticker) -> dict`: verifica no gap > 3 giorni lavorativi
- `check_quality(df, ticker) -> dict`: verifica no outlier (z-score > 5), no volume=0 su giorni trading, no prezzi negativi
- `check_timezone(df, ticker) -> dict`: verifica timestamp US/Eastern, no duplicati, date ordinate
- `validate_dataset(tickers, cache_dir, calendar) -> pd.DataFrame`: report completo per tutti i ticker
- `flag_ticker(ticker, issue_type, severity)`: marca ticker con WARNING o ERROR

**Cosa NON FA:**
- NON corregge automaticamente i dati (solo segnalazione)
- NON riscarica dati difettosi (decisione manuale)

### Criteri di completamento
- [ ] `reports/data_quality_report.csv` generato per tutti i ticker in cache
- [ ] Almeno 90% ticker passano tutti i check
- [ ] Ticker con ERROR bloccanti identificati

### Test richiesti
- **Unit test:** `tests/test_data_quality.py` — gap 5gg → FAIL, dati continui → PASS, volume=0 → FAIL, timestamp UTC → FAIL

### Dipendenze
Da questa fase dipende: **Fase 15 (Scanner usa dati validati)**

### Rischi
- Falsi positivi → meno ticker disponibili; falsi negativi → backtest falsato
  - **Mitigazione:** Soglie configurabili; check multipli ridondanti

### Note implementative
- Outlier detection: IQR o z-score con soglia 5
- Gap detection: confronto con `calendar.get_trading_days()`
- Timezone: verificare `df.index.tz`

### Requisito Design Document
- Sezioni 7.1, 7.2 (Data Pipeline), Sezione 11 (Trading Calendar)

---

## Fase 13: Trading Calendar

### Titolo
Trading Calendar

### Obiettivo
Implementare il trading calendar come da Sezione 11 del Design Document, usando `pandas_market_calendars`.

### Motivazione
Senza un trading calendar accurato, il backtest esegue trade nei giorni di festa, non gestisce half-day, e produce risultati falsati. Questo modulo è usato da backtest engine, scanner, e execution.

### Prerequisiti
- Fase 1 completata (config)
- Fase 2 completata (logger)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 11)
- `src/config.py`

### Output (file creati)
- **Create:** `src/data/calendar.py`
- **Create:** `tests/test_calendar.py`

### Componenti coinvolti
- `src/data/calendar.py`

### Responsabilità
**Cosa FA:**
- Funzione `get_trading_days(start: str, end: str) -> list[date]`: restituisce tutti i giorni di trading NYSE nel range
- Funzione `is_trading_day(d: date) -> bool`: verifica se una data è un giorno di trading
- Funzione `is_early_close(d: date) -> bool`: verifica se è un half-day (es. Black Friday)
- Funzione `get_market_close_time(d: date) -> datetime.time`: restituisce l'orario di chiusura (16:00 EST o 13:00 EST per early close)
- Funzione `get_forced_exit_time(d: date) -> datetime.time`: restituisce l'orario di exit forzata (15:50 EST o 12:50 EST per early close)
- Funzione `get_next_trading_day(d: date) -> date`: prossimo giorno di trading
- Funzione `get_previous_trading_day(d: date) -> date`: giorno di trading precedente
- Gestione DST: tutti gli orari in US/Eastern, conversione automatica tramite `pytz`
- Gestione circuit breakers: funzione `is_market_open_now() -> bool` che controlla `pandas_market_calendars` schedule

**Cosa NON FA:**
- NON gestisce eventi in tempo reale (circuit breaker detection richiede Alpaca; Fase 36)
- NON implementa calendari per exchange non-US

### Criteri di completamento
- [ ] `get_trading_days("2024-01-01", "2024-12-31")` restituisce ~252 giorni
- [ ] 4 Luglio 2024 NON è nella lista
- [ ] Black Friday 2024 (29 Novembre) è marcato come early close
- [ ] `get_forced_exit_time(date(2024, 11, 29))` restituisce 12:50 EST
- [ ] `get_forced_exit_time(date(2024, 7, 15))` restituisce 15:50 EST
- [ ] `is_trading_day(date(2024, 12, 25))` restituisce False (Natale)

### Test richiesti
- **Unit test:** `tests/test_calendar.py`
  - Test `get_trading_days` restituisce date ordinate e senza weekend
  - Test `is_early_close` per Black Friday e 3 Luglio (se half-day)
  - Test `get_forced_exit_time` per giorno normale e half-day
  - Test `get_next_trading_day` per Venerdì → Lunedì
  - Test `is_trading_day` per festività note (Natale, Thanksgiving, 4 Luglio, Memorial Day, Labor Day)

### Dipendenze
Da questa fase dipendono: **Fase 15 (Scanner), Fase 23 (Backtest Engine), Fase 27 (Broker)**

### Rischi
- **Rischio:** `pandas_market_calendars` non include early close per alcuni anni
  - **Mitigazione:** Verificare con il calendario NYSE ufficiale per l'anno corrente
- **Rischio:** DST non gestito correttamente → orari sfalsati di 1 ora
  - **Mitigazione:** Usare `pytz.timezone('US/Eastern')` per TUTTE le conversioni; testare date a cavallo del cambio DST (Marzo e Novembre)

### Note implementative
- `pandas_market_calendars` restituisce orari in UTC; convertire sempre in US/Eastern
- Cache del calendario in memoria (non cambia durante l'esecuzione)
- Pre-calcolare il calendario all'import del modulo per evitare chiamate ripetute

---

# MACRO FASE 3: PRE-MARKET PIPELINE

---

## Fase 14: Market Regime Classifier

### Titolo
Market Regime Classifier

### Obiettivo
Implementare la classificazione del market regime come da Sezione 2.4 del Design Document.

### Motivazione
Il regime di mercato è usato da scanner (filtro VIX/ADX), EDA (expectancy condizionale), e backtest (etichettatura trade). Va implementato come modulo separato e riutilizzabile.

### Prerequisiti
- Fase 1 completata (config)
- Fase 2 completata (logger)
- Fase 8 completata (OHLCV — per scaricare dati SPY e VIX)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 2.4)
- `src/config.py`
- `src/data/ohlcv.py`

### Output (file creati)
- **Create:** `src/data/regime.py`
- **Create:** `tests/test_regime.py`

### Componenti coinvolti
- `src/data/regime.py`

### Responsabilità
**Cosa FA:**
- Funzione `classify_regime(df: pd.DataFrame, vix_value: float | None = None) -> dict[str, bool]`: dato un DataFrame OHLCV giornaliero (tipicamente SPY) e un valore VIX, restituisce un dict con i flag di regime
- Calcola 200SMA e sua pendenza (differenza su 20 giorni)
- Calcola ADX(14) (implementazione manuale o via `pandas-ta`)
- Classifica in 7 regimi come da Sezione 2.4: Bull Trend, Bear Trend, Sideways, High Volatility, Low Volatility, Risk On, Risk Off
- Funzione `get_regime_label(regime_flags: dict[str, bool]) -> str`: restituisce un'etichetta human-readable (es. "Bull Trend + Low Vol + Risk On")
- Funzione `is_tradeable(regime_flags: dict[str, bool], signal_type: str) -> bool`: verifica se il regime corrente permette il trading (es. no SHORT in Bull Trend, no LONG in Bear Trend — configurabile via config)

**Cosa NON FA:**
- NON decide automaticamente quali regimi disabilitare (la decisione viene dall'EDA, Fase 7)
- NON scarica dati (usa DataFrame passati dal chiamante)
- NON implementa logica di trading

### Criteri di completamento
- [ ] `classify_regime(spy_df, vix=18)` restituisce dict con tutte e 7 le chiavi
- [ ] Mercato in uptrend con VIX=18 → `Bull Trend=True`, `Low Volatility=True`, `Risk On=True`, `Sideways=False`
- [ ] Mercato laterale con VIX=18 → `Sideways=True`
- [ ] VIX=28 → `High Volatility=True`, `Risk Off=True` indipendentemente dal trend
- [ ] ADX(14) calcolato correttamente (verificato contro valori noti di SPY)
- [ ] 200SMA e pendenza calcolati correttamente

### Test richiesti
- **Unit test:** `tests/test_regime.py`
  - Test `classify_regime` con dati sintetici in trend rialzista → Bull Trend
  - Test `classify_regime` con dati sintetici laterali → Sideways
  - Test `classify_regime` con VIX alto → High Volatility + Risk Off
  - Test `classify_regime` con VIX basso → Low Volatility
  - Test `is_tradeable` con segnale SHORT in Bull Trend → False
  - Test `is_tradeable` con segnale LONG in Bear Trend → False
  - Test `get_regime_label` formatta correttamente

### Dipendenze
Da questa fase dipendono: **Fase 15 (Scanner), Fase 23 (Backtest Engine)**

### Rischi
- **Rischio:** Calcolo ADX manuale errato → classificazione trend sbagliata
  - **Mitigazione:** Verificare contro `pandas-ta` o fonte attendibile; testare su dati SPY con valori noti
- **Rischio:** Regimi non mutuamente esclusivi → confusione nell'interpretazione
  - **Mitigazione:** Documentare chiaramente che i regimi NON sono esclusivi; un giorno può essere sia "Bull Trend" che "Low Volatility" che "Risk On"
- **Rischio:** 200SMA richiede 200 giorni di dati → inizio serie ha valori NaN
  - **Mitigazione:** Gestire NaN nei calcoli; `classify_regime` restituisce `None` o flag `False` se dati insufficienti

### Note implementative
- ADX formula: `ADX = 100 * MA( abs( +DI - -DI ) / ( +DI + -DI ), 14 )` dove +DI e -DI sono i Directional Indicators
- 200SMA pendenza: `(SMA_200[-1] - SMA_200[-20]) / SMA_200[-20]` → positiva se > 0.001 (0.1%)
- Per Risk On/Off, l'HYG/IEI spread richiede dati aggiuntivi; per v1, usare solo SPY e VIX

---

## Fase 15: Finnhub News & Earnings

### Titolo
Finnhub News & Earnings Filter

### Obiettivo
Implementare `src/data/news_filter.py` con l'integrazione Finnhub per earnings calendar e company news, come da Sezione 8 del Design Document.

### Motivazione
Il filtro news/earnings è essenziale per escludere ticker con gap informativi (non rumorosi). Senza questo filtro, la strategia entra su gap da earnings e perde sistematicamente.

### Prerequisiti
- Fase 1 completata (config con `FINNHUB_API_KEY`)
- Fase 2 completata (logger)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 8)
- `src/config.py`
- `src/logger.py`

### Output (file creati)
- **Create:** `src/data/news_filter.py`
- **Create:** `tests/test_news_filter.py`

### Componenti coinvolti
- `src/data/news_filter.py`
- Finnhub API (esterna)

### Responsabilità
**Cosa FA:**
- Inizializzare il client Finnhub con API key da config/env
- Funzione `get_upcoming_earnings(tickers: list[str], from_date: date, to_date: date) -> set[str]`: restituisce ticker con earnings nel periodo
- Funzione `get_high_impact_news(ticker: str, from_date: date, to_date: date) -> list[dict]`: restituisce news ad alto impatto
- Funzione `filter_tickers(tickers: list[str], today: date) -> list[str]`: filtra i ticker rimuovendo quelli con earnings o news ad alto impatto
- Implementare `is_high_impact(news_item: dict) -> bool`: score basato su categoria/news impact
- Implementare la logica combinata Earnings OR RVOL come da Sezione 8.2:
  - Step 1: Controlla earnings calendar (ieri after-market, oggi pre-market, oggi after-market, domani pre-market)
  - Step 2: Se Finnhub non disponibile → fallback a RVOL-only + log WARNING
  - Step 3: Se tutto down → restituisci lista vuota (conservativo)
- Gestione rate limiting Finnhub (60 chiamate/minuto per piano free)
- Gestione errori API: timeout, 403, 429, 503 → retry o fallback

**Cosa NON FA:**
- NON implementa RVOL pre-market (Fase 14)
- NON implementa Finnhub sentiment (opzionale, v2)
- NON decide quali ticker tradare (solo filtro)

### Criteri di completamento
- [ ] `filter_tickers(["AAPL", "MSFT", "TSLA"], today)` restituisce lista filtrata
- [ ] Ticker con earnings oggi → escluso dalla lista
- [ ] Ticker con news "high impact" → escluso
- [ ] Finnhub API key mancante → log ERROR, restituisce lista vuota (conservativo)
- [ ] Finnhub down (HTTP 503) → log WARNING, tenta fallback
- [ ] Rate limiting: non più di 50 chiamate/minuto
- [ ] Type hints su tutte le funzioni pubbliche

### Test richiesti
- **Unit test:** `tests/test_news_filter.py`
  - Test `filter_tickers` con mock Finnhub che restituisce earnings per AAPL → AAPL escluso
  - Test `filter_tickers` con mock Finnhub che restituisce news high-impact per MSFT → MSFT escluso
  - Test `filter_tickers` con mock Finnhub che restituisce 503 → fallback a RVOL (o lista vuota)
  - Test `filter_tickers` con lista vuota in input → lista vuota in output
  - Test `is_high_impact` con varie categorie di news
  - Test rate limiting: 100 chiamate consecutive non superano il limite

### Dipendenze
Da questa fase dipende: **Fase 15 (Scanner integra il filtro news)**

### Rischi
- **Rischio:** Finnhub API key non configurata → modulo inutilizzabile
  - **Mitigazione:** Messaggio di errore chiaro; fallback conservativo (lista vuota = nessun trade)
- **Rischio:** Finnhub piano free ha limiti stringenti (60 call/min, dati ritardati)
  - **Mitigazione:** Documentare; per uso production passare a piano premium
- **Rischio:** Earnings non rilevati (dati mancanti su Finnhub)
  - **Mitigazione:** Questo è il rischio principale; il fallback RVOL (Fase 14) mitiga parzialmente

### Note implementative
- Usare `finnhub-python` package: `import finnhub`
- Earnings calendar: `client.earnings_calendar(_from=..., to=..., symbol=...)`
- Company news: `client.company_news(symbol, _from=..., to=...)`
- L'impact score può essere basato sulla categoria (es. "earnings", "mergers-acquisitions" → high impact)
- Salvare l'ultimo stato delle API in un file di cache per evitare chiamate ridondanti nella stessa giornata

---

## Fase 16: RVOL Calculator

### Titolo
RVOL Calculator (Relative Volume Pre-Market)

### Obiettivo
Implementare il calcolo del Relative Volume pre-market come filtro aggiuntivo per news/eventi non rilevati da Finnhub.

### Motivazione
La Sezione 8.2 del Design Document specifica che RVOL pre-market > 3x è un segnale di news ad alto impatto. RVOL cattura eventi che Finnhub potrebbe non rilevare (es. rumor, social media, movimenti tecnici).

### Prerequisiti
- Fase 1 completata (config con `rvol_max`)
- Fase 8 completata (OHLCV per dati di volume)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 8.2)
- `src/config.py`
- `src/data/ohlcv.py`

### Output (file creati)
- **Create:** `src/data/rvol.py`
- **Create:** `tests/test_rvol.py`

### Componenti coinvolti
- `src/data/rvol.py`

### Responsabilità
**Cosa FA:**
- Funzione `get_premarket_volume(ticker: str, date: date) -> float`: restituisce il volume pre-market per un ticker in una data
- Funzione `get_avg_premarket_volume(ticker: str, date: date, lookback: int = 20) -> float`: media del volume pre-market negli ultimi N giorni
- Funzione `calculate_rvol(ticker: str, date: date, lookback: int = 20) -> float`: `premarket_volume / avg_premarket_volume`
- Funzione `is_high_rvol(ticker: str, date: date, threshold: float = 3.0) -> bool`: True se RVOL > soglia
- Gestione edge case: avg_premarket_volume = 0 → restituisce 0 (nessun dato storico)
- Per backtest (dati giornalieri senza pre-market): usare il volume dei primi 30 minuti come proxy del pre-market

**Cosa NON FA:**
- NON implementa lo scanner completo (Fase 15)
- NON si integra con Finnhub (lo farà lo scanner, Fase 15)

### Criteri di completamento
- [ ] `calculate_rvol("AAPL", date(2024, 7, 1))` restituisce un float
- [ ] RVOL > 3.0 per giorni con earnings (se il volume pre-market è disponibile)
- [ ] `get_avg_premarket_volume` con lookback=20 restituisce media corretta
- [ ] Se nessun dato pre-market disponibile → RVOL = 1.0 (nessuna anomalia)
- [ ] `is_high_rvol` rispetta la soglia configurata

### Test richiesti
- **Unit test:** `tests/test_rvol.py`
  - Test `calculate_rvol` con dati sintetici: volume doppio della media → RVOL = 2.0
  - Test `calculate_rvol` con volume = 0 → RVOL = 0
  - Test `get_avg_premarket_volume` con meno di `lookback` giorni → media sui giorni disponibili
  - Test `is_high_rvol` con soglia personalizzata

### Dipendenze
Da questa fase dipende: **Fase 15 (Scanner integra RVOL)**

### Rischi
- **Rischio:** Dati pre-market non disponibili da yfinance → RVOL sempre 1.0
  - **Mitigazione:** Per v1 e backtest, usare proxy (volume prima ora); per live, Alpaca/Polygon forniscono dati pre-market
- **Rischio:** RVOL fuorviante per ticker poco liquidi (basso volume = alta varianza)
  - **Mitigazione:** Applicare RVOL solo a ticker con avg_premarket_volume > soglia minima

### Note implementative
- yfinance non fornisce dati pre-market separati. Per backtest, usare `volume` delle prime barre 5min come proxy.
- La logica RVOL sarà più accurata in live con dati Alpaca/Polygon.
- Documentare chiaramente la limitazione dei dati pre-market nel backtest.

---

## Fase 17: Pre-Market Scanner

### Titolo
Pre-Market Scanner

### Obiettivo
Implementare `src/data/scanner.py`: lo scanner pre-market che calcola gap%, VIX, ADX, 200EMA, RVOL e produce la lista di ticker validi per il trading.

### Motivazione
Lo scanner è il cuore della pipeline pre-market: integra tutti i filtri (VIX, ADX, 200EMA, RVOL, gap size, news) e produce la watchlist giornaliera. È il modulo che orchestra Fase 12 (regime), Fase 13 (news), e Fase 14 (RVOL).

### Prerequisiti
- Fase 8 completata (OHLCV)
- Fase 12 completata (Market Regime)
- Fase 13 completata (News Filter)
- Fase 14 completata (RVOL)
- Fase 11 completata (Trading Calendar)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 3.2, 4.1, 4.2, 4.3)
- `src/config.py`
- `src/data/ohlcv.py`
- `src/data/regime.py`
- `src/data/news_filter.py`
- `src/data/rvol.py`
- `src/data/calendar.py`

### Output (file creati)
- **Create:** `src/data/scanner.py`
- **Create:** `tests/test_scanner.py`

### Componenti coinvolti
- `src/data/scanner.py`

### Responsabilità
**Cosa FA:**
- Funzione `scan_premarket(tickers: list[str], date: date) -> pd.DataFrame`: esegue lo scan completo e restituisce DataFrame con colonne: `ticker`, `gap_pct`, `abs_gap_pct`, `vix`, `regime_flags`, `passed_filters`, `rank`
- Step dello scan (in ordine):
  1. Controlla se `date` è un trading day (via calendar)
  2. Scarica VIX corrente
  3. Se VIX > `vix_max` → nessun trade oggi (restituisce DataFrame vuoto con log INFO)
  4. Per ogni ticker: scarica OHLCV giornaliero recente (per PrevClose) e intraday (per Open)
  5. Calcola gap%: `(Open - PrevClose) / PrevClose`
  6. Applica filtro gap size: `gap_min_pct <= abs(gap_pct) <= gap_max_pct`
  7. Applica filtro ADX: `ADX(14) <= adx_max` per quel ticker
  8. Applica filtro 200EMA: `price > 200EMA` (per LONG); `price < 200EMA` (per SHORT)
  9. Applica filtro RVOL: `RVOL <= rvol_max`
  10. Applica filtro news/earnings: esclude ticker con eventi
  11. Classifica regime corrente (Bull/Bear/Sideways/High Vol/Low Vol/Risk On/Risk Off)
  12. Ranking: ordina per `abs(gap_pct)` decrescente
- Funzione `get_watchlist(date: date) -> list[str]`: restituisce solo i ticker passati
- Funzione `get_gap_pct(ticker: str, date: date) -> float`: calcola il gap% per un singolo ticker
- Gestione dati mancanti: ticker senza PrevClose o Open → escluso con log DEBUG
- Logging a ogni step: quanti ticker passano ogni filtro

**Cosa NON FA:**
- NON genera segnali LONG/SHORT (Fase 16)
- NON alloca capitale (Fase 19)
- NON gestisce l'esecuzione (Fase 27)

### Criteri di completamento
- [ ] `scan_premarket(["AAPL", "MSFT", "TSLA"], date(2024, 7, 15))` restituisce DataFrame con colonne specificate
- [ ] VIX > 30 → DataFrame vuoto
- [ ] Ticker con gap 0.1% → escluso (sotto gap_min_pct)
- [ ] Ticker con gap 3% → escluso (sopra gap_max_pct)
- [ ] Ticker con ADX > 25 → escluso
- [ ] Ticker con RVOL > 3.0 → escluso
- [ ] Ranking per abs(gap_pct) decrescente funzionante
- [ ] Data non-trading day → DataFrame vuoto
- [ ] Log a ogni step: "500 ticker → 450 dopo filter X → 300 dopo filter Y → ..."

### Test richiesti
- **Unit test:** `tests/test_scanner.py`
  - Test `scan_premarket` con dati mock: 5 ticker, 2 passano i filtri
  - Test `scan_premarket` con VIX > 30 → DataFrame vuoto
  - Test `scan_premarket` con giorno festivo → DataFrame vuoto
  - Test `get_watchlist` restituisce solo ticker con `passed_filters=True`
  - Test `get_gap_pct` calcolo corretto
  - Test ranking: abs(gap) più grande in cima
  - Test integrazione con news_filter mock: ticker con earnings escluso

### Dipendenze
Da questa fase dipendono: **Fase 16 (Signals), Fase 19 (Portfolio Manager), Fase 23 (Backtest Engine)**

### Rischi
- **Rischio:** Performance: scaricare dati intraday per 50+ ticker in live è lento
  - **Mitigazione:** Parallelizzare i download (ThreadPoolExecutor); usare cache OHLCV; in live, limitare lo scan ai top 50 S&P 500 per market cap
- **Rischio:** Dati mancanti per troppi ticker → watchlist vuota
  - **Mitigazione:** Loggare WARNING con conteggio; non crashare

### Note implementative
- Per la v1, lo scanner usa dati pre-market limitati (yfinance). In produzione (Fase 36+), migrare a Polygon o Alpaca Data API per dati pre-market reali.
- Il filtraggio VIX a 30 è un cutoff hardcoded dal Design Document.
- L'ADX e la 200EMA per ogni ticker vanno calcolati sui dati giornalieri, non intraday.

---

# MACRO FASE 4: STRATEGY CORE

---

## Fase 18: Signal Generator

### Titolo
Signal Generator

### Obiettivo
Implementare `src/strategy/signals.py`: il generatore di segnali LONG/SHORT/EXIT basato sulle regole della Sezione 4.3 del Design Document.

### Motivazione
Il signal generator è il cuore della strategia: traduce i dati di mercato in decisioni di trading. Deve implementare ESATTAMENTE le regole della Sezione 4, senza variazioni.

### Prerequisiti
- Fase 1 completata (config)
- Fase 2 completata (logger)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 4.1, 4.3)
- `src/config.py`

### Output (file creati)
- **Create:** `src/strategy/signals.py`
- **Create:** `tests/test_signals.py`

### Componenti coinvolti
- `src/strategy/signals.py`

### Responsabilità
**Cosa FA:**
- Funzione `generate_signals(df_intraday: pd.DataFrame, gap_pct: float, opening_range_bars: int, confirmation_bars: int) -> pd.Series`: restituisce una Series con -1 (SHORT), 0 (NO TRADE), +1 (LONG) per ogni barra
- Calcola `opening_range_high = max(df_intraday['high'][:opening_range_bars])`
- Calcola `opening_range_low = min(df_intraday['low'][:opening_range_bars])`
- Per LONG (gap negativo, acquisto per fill up):
  - Verifica: `gap_pct < 0` e `abs(gap_pct)` nel range
  - Verifica: `Close` della barra 5min > `opening_range_high` per `confirmation_bars` barre consecutive
  - Segnale: +1 alla barra di conferma
- Per SHORT (gap positivo, vendita per fill down):
  - Verifica: `gap_pct > 0` e `abs(gap_pct)` nel range
  - Verifica: `Close` della barra 5min < `opening_range_low` per `confirmation_bars` barre consecutive
  - Segnale: -1 alla barra di conferma
- Funzione `get_entry_price(df_intraday: pd.DataFrame, signal_bar: int, signal_type: int) -> float`: prezzo di entry al close della barra di segnale
- Funzione `get_stop_loss(df_intraday: pd.DataFrame, opening_range_bars: int, signal_type: int) -> float`:
  - LONG: `SL = min(df_intraday['low'][:opening_range_bars])`
  - SHORT: `SL = max(df_intraday['high'][:opening_range_bars])`
- Funzione `get_take_profit(prev_close: float) -> float`: `TP = prev_close`
- Funzione `should_exit(df_intraday: pd.DataFrame, entry_bar: int, tp: float, sl: float, signal_type: int) -> tuple[bool, str]`: verifica se TP, SL, o EOD sono stati raggiunti
- **USA Close, NON high/low:** la conferma breakout si basa sul Close della barra, non sul high/low (evita falsi breakout da wick)
- **Nessuna dipendenza esterna:** `signals.py` è pura logica, non chiama API né accede a file

**Cosa NON FA:**
- NON calcola position size (Fase 17)
- NON gestisce portfolio o allocazione (Fase 19)
- NON si occupa di esecuzione ordini (Fase 27)

### Criteri di completamento
- [ ] `generate_signals(df_gap_down, gap_pct=-0.01, ...)` restituisce +1 dopo conferma
- [ ] `generate_signals(df_gap_up, gap_pct=+0.01, ...)` restituisce -1 dopo conferma
- [ ] Gap nel range ma nessuna conferma → tutti 0
- [ ] Gap fuori range → tutti 0 (indipendentemente dal breakout)
- [ ] `get_entry_price` restituisce Close della barra di segnale
- [ ] `get_stop_loss(LONG)` restituisce il minimo dell'opening range
- [ ] `get_stop_loss(SHORT)` restituisce il massimo dell'opening range
- [ ] `get_take_profit` restituisce PrevClose
- [ ] `should_exit` rileva TP, SL, e li distingue correttamente
- [ ] Conferma basata su CLOSE, non su high/low (verificato con test specifico)

### Test richiesti
- **Unit test:** `tests/test_signals.py`
  - Test LONG: gap down, Close rompe opening_range_high per 2 barre → +1
  - Test SHORT: gap up, Close rompe opening_range_low per 2 barre → -1
  - Test NO TRADE: gap nel range ma nessun breakout → 0
  - Test NO TRADE: gap fuori range → 0
  - Test conferma con 1 barra insufficiente (se confirmation_bars=2) → 0
  - Test conferma basata su Close, non high/low: high rompe ma Close no → 0
  - Test `should_exit`: TP raggiunto
  - Test `should_exit`: SL raggiunto
  - Test `should_exit`: nessuno dei due raggiunto
  - Test con DataFrame vuoto → Series vuota

### Dipendenze
Da questa fase dipendono: **Fase 17 (Risk), Fase 19 (Portfolio), Fase 23 (Backtest)**

### Rischi
- **Rischio:** Look-ahead bias: usare dati di barre future per decidere il segnale alla barra corrente
  - **Mitigazione:** Per la barra `i`, usare solo dati fino alla barra `i`; la conferma richiede barre `i` e `i+1` (se `confirmation_bars=2`)
- **Rischio:** Wick vs Close: usare high/low invece di Close per la conferma → falsi segnali
  - **Mitigazione:** Il Design Document (Sezione 4.1) specifica esplicitamente "Close della barra 5min"; test specifico per verificare

### Note implementative
- `signals.py` è il modulo più critico: ogni bug qui si propaga a backtest, ottimizzazione, e live trading
- Usare `pd.Series` con indice temporale; -1/0/+1 per ogni barra
- La logica deve essere idempotente: stesso input → stesso output
- NON usare random o tempo di sistema nei calcoli
- Documentare ogni funzione con docstring che spiega la logica esatta (riferimenti alle sezioni del Design Document)

---

## Fase 19: Risk Manager — Base

### Titolo
Risk Manager — Position Sizing Base

### Obiettivo
Implementare `src/strategy/risk.py`: calcolo della position size e dei livelli SL/TP come da Sezioni 4.4, 4.5 del Design Document.

### Motivazione
Il money management è ciò che separa una strategia profittevole da una che perde tutto. Il risk manager implementa la regola dell'1% risk per trade e il dimensionamento basato sulla distanza dello stop loss.

### Prerequisiti
- Fase 1 completata (config)
- Fase 16 completata (signals — per entry price e SL/TP)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 4.4, 4.5, 4.6)
- `src/config.py`

### Output (file creati)
- **Create:** `src/strategy/risk.py`
- **Create:** `tests/test_risk.py`

### Componenti coinvolti
- `src/strategy/risk.py`

### Responsabilità
**Cosa FA:**
- Funzione `calculate_position_size(capital: float, entry_price: float, stop_loss: float, risk_per_trade: float, min_stop_distance_pct: float, max_position_size: float) -> int`: restituisce il numero di azioni
  - `risk_amount = capital * risk_per_trade`
  - `stop_distance = max(abs(entry_price - stop_loss), entry_price * min_stop_distance_pct)`
  - `position_size = int(risk_amount / stop_distance)`
  - `max_shares = int(capital * max_position_size / entry_price)`
  - `return min(position_size, max_shares)`
- Funzione `calculate_stop_loss(entry_price: float, sl_price: float, signal_type: int) -> float`: calcola la distanza dello stop in $
- Funzione `calculate_commission(position_size: int, price: float, sec_fee_rate: float, finra_taf_per_share: float, finra_taf_cap: float) -> float`: calcola commissioni SEC + FINRA TAF come da Sezione 4.5
  - `commission = position_size * price * sec_fee_rate + min(position_size * finra_taf_per_share, finra_taf_cap)`
- Funzione `calculate_slippage(price: float, bar_index: int, opening_range_bars: int, atr: float, base_slippage: float, open_slippage_extra: float, vol_adj_slippage: float) -> float`: slippage dinamico come da Sezione 4.6
  - `slippage = base_slippage`
  - `if bar_index < opening_range_bars: slippage += open_slippage_extra`
  - `slippage += vol_adj_slippage * (atr / price)`
- Funzione `calculate_trade_cost(entry_price: float, exit_price: float, position_size: int, bar_index: int, atr: float, ...) -> dict`: costo totale del trade (commissioni + slippage)
- Funzione `calculate_pnl(entry_price: float, exit_price: float, position_size: int, signal_type: int, costs: dict) -> float`: P&L netto del trade

**Cosa NON FA:**
- NON implementa volatility scaling (Fase 18)
- NON gestisce margini o buying power (Fase 19)
- NON implementa trailing stop (upgrade futuro)

### Criteri di completamento
- [ ] `calculate_position_size(25000, 100.0, 99.0, 0.01, 0.001, 0.95)` restituisce ~250 azioni (risk_amount=250, stop_distance=1.0 → 250 shares)
- [ ] Stop distance sotto il minimo → floor a `entry_price * min_stop_distance_pct`
- [ ] Position size eccede max → capped a `capital * max_position_size / entry_price`
- [ ] `calculate_commission(100, 100.0, ...)` restituisce commissioni corrette (SEC + FINRA TAF)
- [ ] FINRA TAF capped a $5.95
- [ ] `calculate_slippage` con bar_index=0 → slippage aumentato
- [ ] `calculate_slippage` con bar_index=10 → slippage base
- [ ] `calculate_trade_cost` include entry + exit commissioni e slippage
- [ ] `calculate_pnl` LONG: prezzo sale → P&L positivo (netto costi)
- [ ] `calculate_pnl` SHORT: prezzo scende → P&L positivo (netto costi)

### Test richiesti
- **Unit test:** `tests/test_risk.py`
  - Test position size base: capital=25000, risk=1%, entry=100, sl=99 → 250 shares
  - Test position size con stop distance troppo piccolo → floor applicato
  - Test position size con capitale insufficiente → 0 shares
  - Test position size capped da max_position_size
  - Test commissioni SEC+TAF su 100 shares a $100
  - Test FINRA TAF cap: 10000 shares → TAF capped a $5.95
  - Test slippage dinamico in opening range (bar_index < 3)
  - Test slippage dinamico fuori opening range (bar_index >= 3)
  - Test P&L LONG: entry=100, exit=101, 100 shares, costi=0 → +$100
  - Test P&L SHORT: entry=100, exit=98, 100 shares, costi=0 → +$200
  - Test P&L netto con commissioni e slippage

### Dipendenze
Da questa fase dipendono: **Fase 18 (Volatility Scaling), Fase 19 (Portfolio), Fase 23 (Backtest)**

### Rischi
- **Rischio:** Divisione per zero: `risk_amount / stop_distance` con stop_distance = 0
  - **Mitigazione:** `min_stop_distance_pct` garantisce `stop_distance > 0`
- **Rischio:** Position size = 0 per capitali piccoli → nessun trade eseguibile
  - **Mitigazione:** Loggare WARNING; è un comportamento atteso per capitali sotto ~$1000

### Note implementative
- Tutti i calcoli monetari in USD, arrotondati a 2 decimali
- Position size in azioni intere (`int()`)
- `calculate_commission` va chiamato due volte per trade (entry e exit)
- Documentare che le commissioni Alpaca reali possono variare (verificare con Alpaca docs)

---

## Fase 20: Risk Manager — Volatility Scaling

### Titolo
Risk Manager — Volatility Scaling (ATR Normalization)

### Obiettivo
Aggiungere al risk manager il volatility scaling basato su ATR, come descritto nella Sezione 4.4 del Design Document.

### Motivazione
Senza volatility scaling, un trade su un ticker ad alta volatilità (es. NVDA, ATR=3%) ha lo stesso rischio in dollari di un trade su un ticker a bassa volatilità (es. KO, ATR=0.5%), ma il rischio reale è molto diverso. L'ATR normalization rende i trade confrontabili.

### Prerequisiti
- Fase 17 completata (Risk Manager base)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 4.4)
- `src/strategy/risk.py` (da modificare)
- `src/config.py`

### Output (file modificati)
- **Modify:** `src/strategy/risk.py` — aggiungere `calculate_atr()` e modificare `calculate_position_size()`
- **Modify:** `tests/test_risk.py` — aggiungere test per volatility scaling

### Componenti coinvolti
- `src/strategy/risk.py`

### Responsabilità
**Cosa FA:**
- Funzione `calculate_atr(df: pd.DataFrame, period: int = 14) -> float`: calcola l'Average True Range (ATR) su un periodo
- Modificare `calculate_position_size()` per supportare volatility scaling:
  - Se `volatility_scaling` è abilitato in config:
  - `atr_ticker = calculate_atr(df)`
  - `atr_target = config.atr_target` (es. ATR medio S&P 500, ~1.5%)
  - `scaling_factor = atr_target / atr_ticker`
  - `position_size = int(position_size * scaling_factor)`
- Aggiungere parametro `atr_target` in `config/settings.yaml` sotto `risk` (default: 0.015 = 1.5%)
- Funzione `calculate_atr_pct(df: pd.DataFrame, period: int = 14) -> float`: ATR come percentuale del prezzo

**Cosa NON FA:**
- NON modifica la logica base di position sizing (solo scaling moltiplicativo)
- NON implementa ATR trailing stop (upgrade futuro)
- NON cambia SL/TP in base all'ATR (solo position size)

### Criteri di completamento
- [ ] `calculate_atr(df_volatile)` > `calculate_atr(df_stable)`
- [ ] Ticker volatile: scaling_factor < 1 → position_size ridotto
- [ ] Ticker stabile: scaling_factor > 1 → position_size aumentato (ma capped da max_position_size)
- [ ] Volatility scaling disabilitato: position_size invariato
- [ ] `calculate_atr_pct` restituisce valore tra 0 e 1 (es. 0.02 = 2%)
- [ ] `config/settings.yaml` ha `atr_target` sotto `risk`

### Test richiesti
- **Unit test:** `tests/test_risk.py` (aggiunte)
  - Test `calculate_atr` su dati con range noto
  - Test `calculate_position_size` con volatility_scaling=True: ticker volatile → meno azioni
  - Test `calculate_position_size` con volatility_scaling=False: comportamento invariato
  - Test `calculate_position_size` con ATR=0 → scaling_factor infinito → capped
  - Test `calculate_atr_pct` su dati noti

### Dipendenze
Da questa fase dipendono: **Fase 19 (Portfolio Manager usa position sizing completo)**

### Rischi
- **Rischio:** ATR target non calibrato → scaling eccessivo o insufficiente
  - **Mitigazione:** Usare 1.5% come default (ATR medio S&P 500); calibrare durante EDA o backtest
- **Rischio:** ATR calcolato su pochi dati → valore instabile
  - **Mitigazione:** Richiedere almeno `period` giorni di dati; se insufficienti, restituire 1.0 (nessuno scaling)

### Note implementative
- ATR formula standard: `TR = max(high - low, abs(high - prev_close), abs(low - prev_close))`, poi `ATR = MA(TR, period)`
- Usare `pandas` per calcolo vettorizzato (evitare loop)
- `scaling_factor` clamp: `min(2.0, max(0.2, scaling_factor))` per evitare estremi
- Aggiungere `atr_target: 0.015` in `config/settings.yaml` sotto `risk`

---

## Fase 21: Portfolio Manager — State Machine

### Titolo
Portfolio Manager — State Machine

### Obiettivo
Implementare `src/portfolio/manager.py` con la state machine esplicita della Sezione 4.8 del Design Document, gestendo il ciclo di vita delle posizioni (IDLE → PENDING → ACTIVE → LIQUIDATION → RECOVERY).

### Motivazione
Senza una state machine, il portfolio manager è soggetto a bug di stato (es. inviare ordini mentre si è in liquidazione, perdere posizioni dopo un crash). La Sezione 4.8 definisce una macchina a stati esplicita che previene questi errori.

### Prerequisiti
- Fase 1 completata (config)
- Fase 2 completata (logger)
- Fase 17 completata (Risk Manager)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 4.8)
- `src/config.py`
- `src/strategy/risk.py`

### Output (file creati)
- **Create:** `src/portfolio/manager.py`
- **Create:** `tests/test_portfolio.py`

### Componenti coinvolti
- `src/portfolio/manager.py`

### Responsabilità
**Cosa FA:**
- Definire enum `PositionState`: IDLE, PENDING, ACTIVE, LIQUIDATION, RECOVERY
- Classe `PortfolioManager`:
  - `__init__(capital, config)`: inizializza con capitale, config, dizionario posizioni vuoto
  - `request_signal(signal: dict) -> str`: riceve un segnale, valida contro stato corrente, restituisce "approved" o "rejected" con motivazione
  - `transition_to(state: PositionState, position_id: str)`: cambia stato di una posizione
  - `get_state(position_id: str) -> PositionState`: restituisce stato corrente
  - `get_active_positions() -> list[dict]`: posizioni in stato ACTIVE
  - `get_pending_orders() -> list[dict]`: ordini in stato PENDING
  - `get_total_exposure() -> float`: valore totale delle posizioni attive
  - `get_available_capital() -> float`: capitale disponibile per nuovi trade
  - `get_buying_power() -> float`: buying power considerando margine
  - `close_position(position_id: str, exit_price: float) -> dict`: chiude una posizione, registra P&L, transizione a IDLE
  - `log_transition(position_id: str, from_state: PositionState, to_state: PositionState, reason: str)`: logga ogni transizione
- Validazione transizioni illegali: es. non si può passare da LIQUIDATION a PENDING
- Ogni transizione loggata con `loguru` (audit trail)
- Metodo `reconcile(broker_positions: list[dict], broker_orders: list[dict])`: riconcilia stato locale con broker

**Cosa NON FA:**
- NON implementa vincoli di settore/correlazione (Fase 20)
- NON comunica con Alpaca (Fase 27)
- NON esegue ordini (solo gestione stato)

### Criteri di completamento
- [ ] State machine: IDLE → PENDING → ACTIVE → LIQUIDATION → IDLE funzionante
- [ ] Transizione illegale (es. LIQUIDATION → PENDING) → eccezione o log ERROR
- [ ] `request_signal` in stato IDLE → approved
- [ ] `request_signal` in stato PENDING (max raggiunto) → rejected
- [ ] `get_available_capital` calcolato correttamente (capitale - esposizione)
- [ ] `get_total_exposure` somma corretta delle posizioni attive
- [ ] `close_position` registra P&L e transiziona a IDLE
- [ ] Ogni transizione loggata con timestamp, posizione, stato precedente, stato nuovo
- [ ] `reconcile` confronta locale vs broker e aggiorna stato

### Test richiesti
- **Unit test:** `tests/test_portfolio.py`
  - Test ciclo di vita completo: IDLE → PENDING → ACTIVE → LIQUIDATION → IDLE
  - Test transizione illegale: LIQUIDATION → PENDING solleva eccezione
  - Test `request_signal` con max_concurrent_trades raggiunto → rejected
  - Test `get_available_capital` dopo apertura posizione
  - Test `get_total_exposure` con 3 posizioni attive
  - Test `close_position` calcola P&L LONG
  - Test `close_position` calcola P&L SHORT
  - Test `reconcile`: posizioni locali = broker → nessun cambiamento
  - Test `reconcile`: broker ha posizione in più → aggiunta a stato locale
  - Test `reconcile`: broker ha posizione in meno → rimossa da stato locale
  - Test audit trail: tutte le transizioni loggate

### Dipendenze
Da questa fase dipendono: **Fase 20 (Sector/Correlation Constraints), Fase 23 (Backtest), Fase 27 (Broker), Fase 32 (Recovery)**

### Rischi
- **Rischio:** Stato inconsistente dopo eccezione a metà transizione
  - **Mitigazione:** Usare pattern try/finally; se la transizione fallisce, rollback allo stato precedente
- **Rischio:** Memory leak: posizioni mai rimosse dal dizionario
  - **Mitigazione:** `close_position` rimuove sempre la posizione dal dizionario attivo; test di memoria dopo 10000 cicli

### Note implementative
- Usare `enum.Enum` per `PositionState`
- Il dizionario delle posizioni usa `position_id` come chiave (formato: `{date}_{ticker}_{signal_type}`)
- `capital` è il capitale iniziale; l'equity corrente = capitale + P&L realizzato + P&L non realizzato
- La state machine è single-threaded per v1 (nessuna concorrenza)
- Aggiungere metodo `to_dict()` e `from_dict()` per serializzazione/deserializzazione (utile per recovery, Fase 32)

---

## Fase 22: Portfolio Manager — Sector & Correlation Constraints

### Titolo
Portfolio Manager — Sector & Correlation Constraints

### Obiettivo
Aggiungere al Portfolio Manager i vincoli di settore e correlazione rolling come da Sezione 4.7 del Design Document.

### Motivazione
Senza vincoli di settore e correlazione, la strategia potrebbe allocare 5 posizioni in ticker semiconduttori altamente correlati (NVDA, AMD, INTC, TSM, SOXL), violando il principio di diversificazione e aumentando il rischio di drawdown correlati.

### Prerequisiti
- Fase 19 completata (Portfolio Manager base)
- Fase 8 completata (OHLCV — per dati storici necessari alla correlazione)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 4.7)
- `src/portfolio/manager.py` (da modificare)
- `src/config.py`
- `src/data/ohlcv.py`

### Output (file modificati)
- **Modify:** `src/portfolio/manager.py` — aggiungere metodi `apply_sector_constraint()`, `apply_correlation_filter()`, `rank_and_allocate()`
- **Modify:** `tests/test_portfolio.py` — aggiungere test per vincoli

### Componenti coinvolti
- `src/portfolio/manager.py`

### Responsabilità
**Cosa FA:**
- Funzione `get_sector(ticker: str) -> str`: mappa ticker → settore GICS a 2 cifre (da file CSV statico o yfinance)
- Funzione `apply_sector_constraint(candidates: list[dict], active_positions: list[dict], max_per_sector: int = 1) -> list[dict]`: filtra candidati rimuovendo quelli il cui settore è già rappresentato nelle posizioni attive
- Funzione `calculate_rolling_correlation(ticker_a: str, ticker_b: str, lookback: int = 60) -> float`: correlazione di Pearson su finestra mobile di 60 giorni
- Funzione `apply_correlation_filter(candidates: list[dict], active_positions: list[dict], corr_threshold: float = 0.7) -> list[dict]`: per ogni candidato, verifica correlazione con posizioni attive; se `corr > 0.7`, prendi solo quello con `|gap%|` maggiore
- Funzione `apply_cluster_correlation(candidates: list[dict], corr_threshold: float = 0.7) -> list[dict]`: clustering gerarchico sulla matrice di correlazione, max 1 ticker per cluster (opzionale per v1)
- Funzione `rank_and_allocate(candidates: list[dict], max_trades: int) -> list[dict]`: ranking per `abs(gap%)` decrescente, poi applica vincoli settore e correlazione, alloca top N
- Modificare `request_signal` per usare `rank_and_allocate`

**Cosa NON FA:**
- NON modifica la state machine (Fase 19)
- NON calcola la matrice di correlazione per più di 50 ticker alla volta (performance)

### Criteri di completamento
- [ ] Due candidati stesso settore → solo il primo (per ranking) viene allocato
- [ ] Candidato con correlazione > 0.7 vs posizione attiva → scartato (o sostituito se |gap%| maggiore)
- [ ] `rank_and_allocate` restituisce max `max_concurrent_trades` allocazioni
- [ ] `rank_and_allocate` con 10 candidati e max_trades=5 → restituisce max 5
- [ ] Vincolo budget: `sum(position_value) <= capital * max_position_size`
- [ ] Settore non disponibile per un ticker → log WARNING, non escludere (fail-open)
- [ ] Correlazione non calcolabile (dati insufficienti) → assumere 0 (nessuna restrizione)

### Test richiesti
- **Unit test:** `tests/test_portfolio.py` (aggiunte)
  - Test `apply_sector_constraint`: 3 candidati, 2 stesso settore, 1 posizione attiva in quel settore → max 1 allocato
  - Test `apply_sector_constraint`: settori tutti diversi → tutti passano
  - Test `apply_correlation_filter`: candidato con corr=0.8 vs posizione attiva → scartato
  - Test `apply_correlation_filter`: candidato con corr=0.8 ma |gap%| maggiore → sostituisce posizione attiva
  - Test `rank_and_allocate`: verifica ranking per abs(gap%)
  - Test `rank_and_allocate`: verifica max_concurrent_trades
  - Test budget constraint: 6° trade eccede max exposure → scartato

### Dipendenze
Da questa fase dipendono: **Fase 23 (Backtest Engine usa portfolio manager completo)**

### Rischi
- **Rischio:** Calcolo correlazione su 60 giorni richiede 60 giorni di dati → fallisce per ticker con storico breve
  - **Mitigazione:** Se dati < 60 giorni, usare tutti i dati disponibili (min 20); se < 20, correlazione = 0
- **Rischio:** Performance: calcolare matrice di correlazione per 50 ticker × 50 ticker = 1225 coppie
  - **Mitigazione:** Calcolare solo per i top 20 candidati (dopo ranking preliminare)

### Note implementative
- Per la mappatura settore: creare `data/sector_mapping.csv` statico con ticker → settore GICS
- La correlazione rolling usa `df['close'].pct_change().rolling(60).corr()`
- Per il clustering gerarchico (opzionale): `scipy.cluster.hierarchy` con `method='average'`
- Documentare che la correlazione è calcolata sui rendimenti giornalieri, non sui prezzi

---

# MACRO FASE 5: BACKTESTING SUITE

---

## Fase 23: Commission & Slippage Simulator

### Titolo
Commission & Slippage Simulator

### Obiettivo
Implementare il simulatore di costi di transazione come da Sezioni 4.5 e 4.6 del Design Document, come modulo standalone riutilizzabile dal backtest engine.

### Motivazione
Transaction costs realistici sono ciò che separa un backtest "da paper trading" da uno realistico. Le commissioni Alpaca (SEC fee + FINRA TAF) e lo slippage dinamico sono già parzialmente implementati in `risk.py` (Fase 17), ma vanno estratti in un modulo dedicato per chiarezza.

### Prerequisiti
- Fase 17 completata (Risk Manager — ha già `calculate_commission` e `calculate_slippage`)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 4.5, 4.6, 9.4, 9.5)
- `src/strategy/risk.py` (codice esistente da rifattorizzare)
- `src/config.py`

### Output (file creati/modificati)
- **Create:** `src/backtest/costs.py` — modulo costi standalone
- **Modify:** `src/strategy/risk.py` — delegare calcolo costi a `backtest/costs.py`
- **Create:** `tests/test_costs.py`

### Componenti coinvolti
- `src/backtest/costs.py`
- `src/strategy/risk.py`

### Responsabilità
**Cosa FA:**
- Funzione `calculate_commission(position_size: int, price: float, config: dict) -> float`: SEC fee + FINRA TAF (da `risk.py`)
- Funzione `calculate_slippage(price: float, bar_index: int, opening_range_bars: int, atr: float, config: dict) -> float`: slippage dinamico (da `risk.py`)
- Funzione `calculate_partial_fill(desired_qty: int, bar_volume: int) -> tuple[int, float]`: probabilità e quantità di fill parziale come da Sezione 9.4
  - `volume_ratio = min(desired_qty / bar_volume, 1.0)`
  - `fill_probability = 1.0 - (0.3 * volume_ratio)`
  - Se fill: `filled_qty = desired_qty`
  - Se partial: `filled_qty = int(desired_qty * random.uniform(0.3, 0.9))`
  - `partial_slippage = 0.0002 * (remaining_qty / desired_qty)`
- Funzione `calculate_total_costs(entry_price, exit_price, position_size, bar_index, atr, config) -> dict`: costo totale round-trip
- Funzione `apply_market_impact_check(position_value: float, avg_daily_volume: float, threshold: float = 0.005) -> bool`: verifica `position_value < 0.5% ADV`
- Supporto per seed deterministico (per riproducibilità backtest)

**Cosa NON FA:**
- NON esegue il backtest loop (Fase 23)
- NON calcola metriche (Fase 24)
- NON implementa market impact avanzato (Almgren-Chriss) — v2

### Criteri di completamento
- [ ] `calculate_commission` identico alla versione in `risk.py` (stessi risultati)
- [ ] `calculate_slippage` identico alla versione in `risk.py` (stessi risultati)
- [ ] `calculate_partial_fill` con `desired_qty=1000, bar_volume=100000` → alta probabilità di fill completo
- [ ] `calculate_partial_fill` con `desired_qty=1000, bar_volume=2000` → probabile fill parziale
- [ ] `calculate_total_costs` include entry slippage + exit slippage + commissioni entry + commissioni exit
- [ ] `apply_market_impact_check` con position_value=1000, ADV=1000000 → True (0.1% < 0.5%)
- [ ] `apply_market_impact_check` con position_value=50000, ADV=1000000 → False (5% > 0.5%)
- [ ] Seed fissato → `calculate_partial_fill` produce sempre lo stesso risultato

### Test richiesti
- **Unit test:** `tests/test_costs.py`
  - Test commissioni: valori noti → risultato atteso
  - Test FINRA TAF cap
  - Test slippage in opening range
  - Test slippage fuori opening range
  - Test partial fill: volume alto → fill completo
  - Test partial fill: volume basso → fill parziale
  - Test partial fill con seed fisso → output deterministico
  - Test market impact check: sotto soglia → True, sopra → False
  - Test costi totali: somma corretta di tutti i componenti

### Dipendenze
Da questa fase dipendono: **Fase 22, Fase 23 (Backtest Engine usa costi)**

### Rischi
- **Rischio:** `risk.py` e `costs.py` divergono → risultati diversi tra backtest e live
  - **Mitigazione:** `risk.py` DEVE delegare a `costs.py`; non duplicare la logica
- **Rischio:** Random non deterministico → backtest non riproducibile
  - **Mitigazione:** Usare `random.Random(seed)` o `numpy.random.RandomState(seed)`; seed passato esplicitamente

### Note implementative
- Estrarre le funzioni da `risk.py` in `costs.py`, poi far sì che `risk.py` importi da `costs.py`
- Per il partial fill, la execution queue (barre successive) è implementata nel backtest engine (Fase 23), non qui
- Aggiungere `random_seed` in `config/settings.yaml` sotto `backtest`

---

## Fase 24: Partial Fill Engine

### Titolo
Partial Fill Engine

### Obiettivo
Implementare la logica di execution queue per il partial fill model come da Sezione 9.4 del Design Document.

### Motivazione
Il partial fill model non è solo una probabilità: la quantità non eseguita va messa in coda e ritentata nelle barre successive. Questa logica è abbastanza complessa da meritare un modulo dedicato.

### Prerequisiti
- Fase 21 completata (Costs — `calculate_partial_fill`)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 9.4)
- `src/backtest/costs.py`

### Output (file creati)
- **Create:** `src/backtest/fill_simulator.py`
- **Create:** `tests/test_fill_simulator.py`

### Componenti coinvolti
- `src/backtest/fill_simulator.py`

### Responsabilità
**Cosa FA:**
- Classe `ExecutionQueue`:
  - `__init__(max_attempts=3)`: inizializza coda vuota e contatore tentativi
  - `enqueue(ticker, desired_qty, entry_price, signal_type, bar_index)`: aggiunge un ordine alla coda
  - `process_bar(bar_index, bar_volume, bar_price) -> list[dict]`: processa la coda per la barra corrente, restituisce i fill
  - Per ogni ordine in coda:
    - Tenta `calculate_partial_fill(remaining_qty, bar_volume)`
    - Se fill completo: rimuovi dalla coda, restituisci fill
    - Se fill parziale: riduci `remaining_qty`, incrementa `attempts`
    - Se `attempts >= max_attempts`: cancella ordine, logga "order expired"
  - `get_remaining() -> list[dict]`: ordini ancora in coda
  - `clear()`: svuota la coda
- Funzione `simulate_execution(ticker, desired_qty, entry_price, signal_type, df_intraday, bar_index) -> tuple[int, float, float]`: helper che simula l'intera esecuzione (coda + fill) e restituisce `(filled_qty, avg_fill_price, total_slippage)`

**Cosa NON FA:**
- NON modifica il backtest engine (Fase 23 integra questo modulo)
- NON gestisce ordini reali (solo simulazione)

### Criteri di completamento
- [ ] Ordine eseguito alla prima barra (fill completo) → rimosso dalla coda
- [ ] Ordine parzialmente eseguito → `remaining_qty` ridotto, rimane in coda
- [ ] Dopo 3 tentativi falliti → ordine cancellato, log "expired"
- [ ] `process_bar` con coda vuota → lista fill vuota
- [ ] `get_remaining` restituisce solo ordini non completati
- [ ] `clear()` svuota completamente la coda
- [ ] `simulate_execution` restituisce `filled_qty`, `avg_fill_price` (media pesata), `total_slippage`

### Test richiesti
- **Unit test:** `tests/test_fill_simulator.py`
  - Test enqueue + process_bar con fill completo
  - Test enqueue + process_bar × 2 con fill parziale poi completo
  - Test enqueue + process_bar × 3 → expire
  - Test coda vuota → process_bar restituisce []
  - Test `clear()` svuota coda
  - Test `simulate_execution` con fill completo alla prima barra
  - Test `simulate_execution` con fill parziale su 2 barre
  - Test `simulate_execution` con expire dopo 3 barre
  - Test con seed fisso → output deterministico

### Dipendenze
Da questa fase dipende: **Fase 23 (Backtest Engine integra ExecutionQueue)**

### Rischi
- **Rischio:** Performance: `process_bar` chiamato per ogni barra × ogni ordine in coda
  - **Mitigazione:** La coda ha al massimo `max_concurrent_trades` elementi; è O(N) con N piccolo
- **Rischio:** Ordine eseguito a prezzo peggiore dopo partial fill → P&L distorto
  - **Mitigazione:** `avg_fill_price` è la media pesata dei prezzi di esecuzione parziali

### Note implementative
- `ExecutionQueue` è una classe semplice (non servono dipendenze esterne)
- Usare `random.Random(seed)` per la componente stocastica
- Documentare che il modello di partial fill è una semplificazione; in produzione, i fill reali dipendono dal book di ordini

---

## Fase 25: Backtest Engine — Core Loop

> **Nota:** La Fase 23 originale è stata decomposta in 3 sotto-fasi: 19a (Core Loop), 19b (Integration), 19c (Validation).
### Titolo
Backtest Engine — Core Loop

### Obiettivo
Implementare il loop di backtest event-driven base: iterazione giornaliera, equity curve, e trade log. **SOLO il loop principale** senza integrazione costi, fill simulator, e portfolio (questi vanno in 19b).


### Prerequisiti
- Fase 8 completata (OHLCV)
- Fase 11 completata (Calendar)
- Fase 15 completata (Scanner)
- Fase 16 completata (Signals)
- Fase 17 completata (Risk)
- Fase 19 completata (Portfolio Manager)
- Fase 21 completata (Costs)
- Fase 22 completata (Fill Simulator)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 5.1, 5.2)
- Tutti i moduli sopra elencati
- `src/config.py`

### Output (file creati)
- **Create:** `src/backtest/engine.py`
- **Create:** `tests/test_backtest.py`

### Componenti coinvolti
- `src/backtest/engine.py`

### Responsabilità
**Cosa FA:**
- Classe `BacktestEngine`:
  - `__init__(config, tickers, start_date, end_date)`: inizializza con config, lista ticker, date range
  - `run() -> BacktestResult`: esegue il backtest completo
  - `_split_data(tickers, start, end) -> tuple[pd.Timestamp, pd.Timestamp]`: calcola il punto di split 70/30
  - Loop principale (giornaliero):
    1. Verifica che `date` sia un trading day (via calendar)
    2. `scanner.scan_premarket(tickers, date)` → watchlist
    3. Per ogni ticker nella watchlist:
       a. Carica dati intraday 5min per quel giorno
       b. `signals.generate_signals(df_intraday, gap_pct)` → Series segnali
       c. Per ogni barra con segnale ≠ 0:
          - `risk.calculate_position_size(capital, entry_price, sl_price)` → size
          - `portfolio.request_signal(...)` → approved/rejected
          - Se approved: simula esecuzione via `fill_simulator`
          - Applica costi (commissioni, slippage)
          - Monitora TP/SL/EOD
          - Registra trade (entry/exit/pnl/MFE/MAE)
    4. Aggiorna equity curve giornaliera
  - `_calculate_mfe_mae(df_intraday, entry_bar, exit_bar, position_type) -> tuple[float, float]`: MFE e MAE intra-trade
  - `_build_equity_curve(trades, initial_capital) -> pd.Series`: equity curve giornaliera dal log trade
  - `_build_trade_log() -> pd.DataFrame`: DataFrame con tutti i trade
- Classe `BacktestResult`:
  - `equity_curve: pd.Series`
  - `trades: pd.DataFrame`
  - `in_sample_trades: pd.DataFrame`
  - `out_of_sample_trades: pd.DataFrame`
  - `config: dict`
  - Metodo `save(path: str)`: salva in formato Parquet
  - Metodo `load(path: str) -> BacktestResult`: carica da file

**Cosa NON FA:**
- NON calcola metriche (Fase 24 usa `BacktestResult`)
- NON fa ottimizzazione (Fase 25)
- NON genera report (Fase 26)

### Criteri di completamento
- [ ] `BacktestEngine.run()` completa senza errori su 1 anno di dati SPY
- [ ] Hold-out split: 70% in-sample, 30% out-of-sample
- [ ] Trade log contiene: date, ticker, signal_type, entry_time, entry_price, exit_time, exit_price, pnl, mfe, mae, regime
- [ ] Equity curve parte da `initial_capital` e riflette tutti i trade
- [ ] Costi di transazione applicati a ogni trade
- [ ] SL/TP/EOD gestiti correttamente
- [ ] Partial fill: quantità eseguita <= quantità richiesta
- [ ] MFE/MAE calcolati per ogni trade
- [ ] Portfolio manager usato per approval/rejection
- [ ] `BacktestResult.save()` e `load()` round-trip funzionante
- [ ] Seed fissato → due run identiche producono stesso output (per Fase 33)

### Test richiesti
- **Integration test:** `tests/test_backtest.py`
  - Test backtest su 1 mese di dati SPY → produce equity curve non vuota
  - Test backtest su periodo senza trading day → 0 trade
  - Test hold-out split: OOS mai usato in calibrazione
  - Test con capitale insufficiente per qualsiasi trade → 0 trade, equity costante
  - Test con 1 solo ticker e dati noti → trade log verificabile manualmente
  - Test MFE/MAE su trade sintetico
  - Test `BacktestResult.save/load` round-trip
- **Unit test:** test helper functions (`_split_data`, `_build_equity_curve`, `_build_trade_log`)

### Dipendenze
Da questa fase dipendono: **Fase 24 (Metrics), Fase 25 (Optimization), Fase 26 (Reporting), Fase 33 (Determinism), Fase 34 (Replay)**

### Rischi
- **Rischio:** Performance: 10 anni × 500 ticker × 78 barre/giorno = potenzialmente milioni di iterazioni
  - **Mitigazione:** Early exit: se `gap_pct` fuori range, saltare signals; parallelizzare ticker nella watchlist (ThreadPoolExecutor)
- **Rischio:** Look-ahead bias nel backtest (usare dati del giorno T+1 per decidere il trade del giorno T)
  - **Mitigazione:** Per il giorno T, usare SOLO dati fino al giorno T; il segnale è calcolato sulle barre intraday del giorno T; l'OHLCV storico per indicatori (SMA, ADX) usa dati fino a T-1
- **Rischio:** Dati intraday mancanti per date storiche
  - **Mitigazione:** yfinance fornisce intraday solo per ~60 giorni; per backtest lunghi, usare dati giornalieri con OHLC come proxy dell'azione intraday (semplificazione documentata)

### Note implementative
- Il loop del backtest segue ESATTAMENTE lo pseudocodice della Sezione 5.2
- `BacktestResult` usa `@dataclass`
- Salvare i trade in `reports/backtest_trades.csv` e l'equity in `reports/backtest_equity.csv`
- Per i dati intraday mancanti: usare Open, High, Low, Close giornalieri come proxy delle barre 5min (es. High = max intraday, Low = min intraday). Questo è meno preciso ma permette backtest su 10 anni.

---

---

## Fase 26: Backtest Engine — Integration

> **Nota:** Seconda sotto-fase della decomposizione Fase 23.

### Titolo
Backtest Engine — Integration

### Obiettivo
Integrare il modulo costi (`costs.py`), il fill simulator (`fill_simulator.py`), e il portfolio manager nel backtest engine core (19a).

### Motivazione
Dopo aver implementato il loop base in 19a, questa fase integra i componenti di costo e gestione portafoglio per rendere il backtest realistico.

### Prerequisiti
- Fase 31 completata (core loop)
- Fase 21 completata (Costs)
- Fase 22 completata (Fill Simulator)
- Fase 19 completata (Portfolio Manager)

### Input
- `src/backtest/engine.py` (da 19a)
- `src/backtest/costs.py`
- `src/backtest/fill_simulator.py`
- `src/portfolio/manager.py`

### Output (file modificati)
- **Modify:** `src/backtest/engine.py` — integrare costs, fill, portfolio
- **Modify:** `tests/test_backtest.py` — aggiornare test con mock integration

### Componenti coinvolti
- `src/backtest/engine.py`

### Responsabilità
**Cosa FA:**
- Integrare `calculate_commission()` e `calculate_slippage()` nel loop
- Integrare `ExecutionQueue` per partial fill model
- Chiamare `portfolio.request_signal()` prima di ogni trade
- Applicare `portfolio.close_position()` alla exit
- Gestire vincoli di budget ed esposizione dal portfolio manager
- Calcolare P&L netto (prezzo - costi - slippage)

**Cosa NON FA:**
- NON modifica il loop base (19a)
- NON aggiunge nuove metriche (Fase 24)
- NON implementa ottimizzazione

### Criteri di completamento
- [ ] Costi di transazione applicati a ogni trade
- [ ] Partial fill: quantità eseguita <= quantità richiesta
- [ ] Portfolio manager usato per approval/rejection
- [ ] Vincolo budget: `sum(position_value) <= capital * max_position_size`
- [ ] P&L netto calcolato correttamente

### Test richiesti
- **Integration test:** `tests/test_backtest.py`
  - Test con costs: trade P&L < trade P&L senza costi
  - Test partial fill su trade sintetico
  - Test portfolio rejection quando max trades raggiunto

### Dipendenze
Da questa fase dipende: **Fase 33 (Validation)**

### Rischi
- **Rischio:** Costi duplicati (applicati due volte)
  - **Mitigazione:** Test specifico che verifica il costo totale

### Note implementative
- Le funzioni di costo vanno chiamate nel loop, non duplicate
- L'`ExecutionQueue` va istanziata una volta per sessione di backtest
- Documentare chiaramente il flusso: segnale → risk → portfolio → fill → costi → esecuzione

---

## Fase 27: Backtest Engine — Validation

> **Nota:** Terza sotto-fase della decomposizione Fase 23.

### Titolo
Backtest Engine — Determinism Validation

### Obiettivo
Verificare che il backtest engine sia deterministico: due run con gli stessi input producono output identici.

### Motivazione
La riproducibilità è essenziale per fidarsi dei risultati del backtest. Se due run identiche danno risultati diversi, il sistema ha una fonte di non-determinismo (seed non fissato, dipendenza da tempo, race condition) che invalida qualsiasi ottimizzazione.

### Prerequisiti
- Fase 31 completata (core loop)
- Fase 32 completata (integration)
- Fase 33 può essere eseguita in parallelo (test determinismo a livello sistema)

### Input
- `src/backtest/engine.py`
- Dati sintetici generati per il test

### Output (file creati)
- **Create:** `tests/test_backtest_determinism.py`
- **Modify:** `src/backtest/engine.py` — se necessario, aggiungere seed parameter

### Componenti coinvolti
- `src/backtest/engine.py`
- `tests/test_backtest_determinism.py`

### Responsabilità
**Cosa FA:**
- Generare dati sintetici deterministici (OHLCV giornalieri e intraday)
- Eseguire `BacktestEngine.run()` due volte con seed identico
- Verificare che: equity curve, trade log, MFE/MAE, metriche siano identici
- Verificare che `BacktestResult.save()` e `load()` siano round-trip deterministici
- Se viene trovato non-determinismo: investigare e fixare la fonte (es. `random` senza seed, `set` iteration order, timestamp)

**Cosa NON FA:**
- NON esegue backtest su dati reali (lo fa 19a/19b)
- NON calcola metriche complete (lo fa Fase 24)

### Criteri di completamento
- [ ] Due run identiche → equity curves identiche (assert bit-exact)
- [ ] Due run identiche → stessi trade (data, ticker, entry, exit, pnl)
- [ ] Due run identiche → stessi MFE/MAE
- [ ] `BacktestResult.save/load` round-trip preserva tutti i campi
- [ ] Nessuna fonte di non-determinismo trovata

### Test richiesti
- **Unit test:** `tests/test_backtest_determinism.py`
  - Test `run()` × 2 su dati sintetici → output identico
  - Test `save/load` round-trip
  - Test con seed diverso → output diverso (conferma che il seed funziona)

### Dipendenze
Da questa fase dipende: **Fase 25 (Optimization — richiede determinismo)**

### Rischi
- **Rischio:** Non-determinismo sottile (es. floating point, ordinamento dict)
  - **Mitigazione:** Usare `np.testing.assert_array_almost_equal` per float; `sort=False` in operazioni pandas; `PYTHONHASHSEED` fissato

### Note implementative
- Dati sintetici: generare con `numpy.random.RandomState(42)` OHLCV plausibili
- Il seed va passato esplicitamente a TUTTI i componenti random (costs, fill simulator)
- Aggiungere `random_seed` in `config/settings.yaml` sotto `backtest`
- Se il test di determinismo fallisce, NON procedere con l'ottimizzazione (Fase 25)

### Requisito Design Document
- Sezione 5 (Backtest Engine), Sezione 9.5 (Verifica e validazione)

## Fase 28: Walk Forward Analysis

### Titolo
Walk Forward Analysis (Train/Validation/Test Split)

### Obiettivo
Implementare la walk forward analysis con split temporale Train (2014-2018) / Validation (2019-2021) / Test (2022-2024). I parametri sono ottimizzati sul Train, validati sul Validation, e TESTATI UNA SOLA VOLTA sul Test set.

### Motivazione
Un singolo split 70/30 (hold-out) non e sufficiente per validare una strategia quantitativa. La walk forward analysis simula il processo reale: si ottimizza su dati passati, si valida su un periodo intermedio, e si testa su dati mai visti. Il Test set (2022-2024) NON deve MAI essere usato per ottimizzazione o selezione parametri.

### Prerequisiti
- Fase 33 completata (BT Validation)
- Fase 31 completata (BT Core)
- Fase 8 completata (Historical Universe)

### Input
- src/backtest/engine.py
- src/backtest/optimize.py
- src/backtest/metrics.py
- data/universe/sp500_history.csv

### Output (file creati)
- **Create:** src/backtest/walk_forward.py
- **Create:** reports/walk_forward/performance.csv
- **Create:** reports/walk_forward/equity_curve.png
- **Create:** reports/walk_forward/stability_report.md
- Test: tests/test_walk_forward.py (fase 28)

### Componenti coinvolti
- src/backtest/walk_forward.py

### Responsabilita
**Cosa FA:**
- walk_forward_analysis(tickers, train_period, val_period, test_period, param_grid) -> dict
- Train (2014-2018): Grid search -> best_params_train
- Validation (2019-2021): Backtest con best_params_train -> metriche_val
- Decision gate: Se metriche_val non soddisfano soglie (Sharpe > 0.5, MaxDD < 25%) -> STOP
- Test (2022-2024): Backtest con best_params_train -> metriche_test (ESEGUITO UNA SOLA VOLTA)
- Regola ferrea: Il Test set viene toccato SOLO dopo che tutti i parametri sono fissati
- stability_report.md: Confronto parametri ottimali per ogni finestra, analisi stabilita

**Cosa NON FA:**
- NON modifica il backtest engine
- NON ottimizza parametri sul Test set

### Criteri di completamento
- [ ] Walk forward completa con 3 periodi distinti
- [ ] Best params dal Train usati per Validation e Test (MAI riottimizzati)
- [ ] performance.csv mostra metriche per tutti e 3 i periodi
- [ ] Test set toccato UNA SOLA volta
- [ ] Se Validation Sharpe < 0.5: STOP con messaggio esplicito
- [ ] stability_report.md analizza stabilita parametri tra finestre

### Test richiesti
- **Unit test:** tests/test_walk_forward.py
  - Test split date: Train 2014-2018, Val 2019-2021, Test 2022-2024
  - Test che walk_forward_analysis non modifica best_params dopo aver visto Test
  - Test gate: Validation Sharpe < 0.5 -> funzione restituisce None

### Dipendenze
Da questa fase dipende: Fase 35 (Monte Carlo), Fase 38 (Reporting finale)

### Rischi
- **Rischio:** Overfitting sul Validation set (si itera finche Validation non e buono)
  - **Mitigazione:** Il Validation set viene usato UNA sola volta. Se non passa, si rivede la STRATEGIA, non i parametri.
- **Rischio:** Periodi troppo brevi (5 anni Train) -> parametri instabili
  - **Mitigazione:** 10 anni totali; per strategie intraday 5 anni di Train sono il minimo accettabile

### Note implementative
- Split date: Train 2014-01-01 -> 2018-12-31, Val 2019-01-01 -> 2021-12-31, Test 2022-01-01 -> 2024-12-31
- Ordine cronologico (non random): simula il processo reale di sviluppo strategia
- Se la strategia funziona nel Test 2022-2024 (bear market 2022), ha superato uno stress test reale

### Requisito Design Document
- Sezione 5 (Backtest Engine), Sezione 6 (Optimization), Sezione 0.3 (Gate Decision)

## Fase 29: Monte Carlo Simulation Engine

### Titolo
Monte Carlo Simulation Engine (Robustness Stress Testing)

### Obiettivo
Implementare un motore di simulazione Monte Carlo per stress-testare la strategia sotto scenari avversi: ordine casuale dei trade, variazione slippage e commissioni, sequenze di perdite consecutive, e scenario pessimistico.

### Motivazione
Un backtest deterministico mostra UNA realizzazione della strategia. La Monte Carlo simulation genera MIGLIAIA di realizzazioni alternative per rispondere a domande critiche: probabilita di perdere il 25% del capitale, sensibilita allo slippage, impatto dell'ordine dei trade.

### Prerequisiti
- Fase 34 completata (Walk Forward Analysis)
- Fase 36 completata (Metrics)
- Fase 31 completata (Backtest Core)

### Input
- src/backtest/engine.py (BacktestResult con trade list)
- src/backtest/metrics.py
- reports/walk_forward/performance.csv

### Output (file creati)
- **Create:** src/backtest/monte_carlo.py
- **Create:** reports/monte_carlo/drawdown_distribution.csv
- **Create:** reports/monte_carlo/drawdown_histogram.png
- **Create:** reports/monte_carlo/risk_of_ruin.md
- **Create:** reports/monte_carlo/slippage_sensitivity.csv
- Test: tests/test_monte_carlo.py (fase 29)

### Componenti coinvolti
- src/backtest/monte_carlo.py

### Responsabilita
**Cosa FA:**
- monte_carlo_simulation(trades, n_simulations=10000) -> dict: Trade order randomization, slippage random (normale attorno allo slippage medio), commissioni random (+-20%), equity curve simulata, distribuzione max drawdown/Sharpe/final return
- calculate_risk_of_ruin(drawdowns, ruin_threshold=0.25) -> float: P(max_drawdown > 25%)
- calculate_worst_case(returns, percentile=0.05) -> float: Rendimento al 5deg percentile peggiore
- calculate_consecutive_losses(trades, n_simulations=10000) -> dict: Distribuzione massima sequenza perdite consecutive
- slippage_sensitivity_analysis(trades, slippage_range) -> pd.DataFrame: Sharpe al variare dello slippage, identifica break-even point
- risk_of_ruin.md: report con probabilita di rovina, worst-case return, max perdite consecutive, break-even slippage, raccomandazione capitale minimo

**Cosa NON FA:**
- NON modifica la strategia (solo analisi)
- NON sostituisce il backtest (lo complementa)
- NON implementa Monte Carlo sui parametri (solo sui trade)

### Criteri di completamento
- [ ] 10,000 simulazioni completate senza errori
- [ ] drawdown_distribution.csv e histogram generati
- [ ] risk_of_ruin.md con probabilita e raccomandazioni
- [ ] slippage_sensitivity.csv con break-even point
- [ ] Probability of Ruin calcolata correttamente
- [ ] Worst-case return al 5deg percentile calcolato

### Test richiesti
- **Unit test:** tests/test_monte_carlo.py
  - Test monte_carlo_simulation con 100 trade sintetici -> 1000 simulazioni
  - Test calculate_risk_of_ruin con drawdown tutti sotto soglia -> 0%
  - Test calculate_worst_case con distribuzione nota
  - Test slippage_sensitivity_analysis con slippage crescente -> Sharpe decrescente
  - Test riproducibilita con seed fissato

### Dipendenze
Da questa fase dipende: Fase 38 (Reporting include Monte Carlo results), Fase 51 (Paper Trading -- decision gate)

### Rischi
- **Rischio:** Monte Carlo su pochi trade (N < 30) produce distribuzioni non affidabili
  - **Mitigazione:** Richiedere N >= 50 trade; documentare bassa potenza statistica se insufficienti
- **Rischio:** Bootstrap assume indipendenza dei trade -> non cattura autocorrelazione
  - **Mitigazione:** Block bootstrap (blocchi di 5 trade consecutivi) per preservare dipendenza temporale

### Note implementative
- Bootstrap: np.random.choice(trades, size=len(trades), replace=True)
- Block bootstrap: np.random.choice(blocks, size=n_blocks, replace=True)
- Slippage random: np.random.normal(loc=base_slippage, scale=0.3*base_slippage)
- Seed: np.random.seed(42) per riproducibilita
- Aggiungere monte_carlo_n_simulations: 10000 in config

### Requisito Design Document
- Sezione 5.3 (Metrics), Sezione 6 (Optimization), Sezione 13.2 (Acceptance Checklist)


## Fase 30: Metrics Calculator

### Titolo
Metrics Calculator

### Obiettivo
Implementare `src/backtest/metrics.py`: calcolo di TUTTE le metriche elencate nella Sezione 5.3 del Design Document, più rolling metrics, MFE/MAE aggregation, e bootstrap confidence intervals.

### Motivazione
Le metriche sono l'output principale del backtest: determinano se la strategia è profittevole, robusta, e pronta per il live. La Sezione 5.3 elenca 25+ metriche che vanno TUTTE implementate.

### Prerequisiti
- Fase 23 completata (BacktestResult disponibile)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 5.3, 5.4)
- `src/backtest/engine.py` (BacktestResult)

### Output (file creati)
- **Create:** `src/backtest/metrics.py`
- **Create:** `tests/test_metrics.py`

### Componenti coinvolti
- `src/backtest/metrics.py`

### Responsabilità
**Cosa FA:**
- Funzione `calculate_all_metrics(result: BacktestResult, risk_free_rate: float = 0.045) -> dict`: calcola TUTTE le metriche e restituisce un dizionario
- Metriche da implementare (Sezione 5.3):
  - **Performance:** Total Return, CAGR, Annual Returns, Monthly Returns
  - **Risk-Adjusted:** Sharpe Ratio, Sortino Ratio, Calmar Ratio, MAR Ratio, SQN
  - **Rischio:** Max Drawdown, VaR 95%, CVaR 95%, Volatilità, Ulcer Index, Skewness, Kurtosis
  - **Trade:** Total Trades, Win Rate, Profit Factor, Expectancy, Avg Win/Avg Loss, Max Consecutive Losses, Kelly Criterion (SOLO INFORMATIVO), Recovery Factor
  - **Execution:** MFE mean, MAE mean, Avg Holding Time, Avg Exposure
  - **Rolling:** Rolling Sharpe (6M), Rolling Sortino (6M), Rolling Max DD (6M)
- Funzione `calculate_sharpe(returns: pd.Series, risk_free_rate: float) -> float`
- Funzione `calculate_sortino(returns: pd.Series, risk_free_rate: float) -> float`
- Funzione `calculate_max_drawdown(equity: pd.Series) -> tuple[float, pd.Timestamp, pd.Timestamp]`
- Funzione `calculate_var_cvar(returns: pd.Series, confidence: float = 0.95) -> tuple[float, float]`
- Funzione `calculate_probability_of_ruin(returns: pd.Series, ruin_threshold: float = 0.25, n_simulations: int = 1000) -> float`: Monte Carlo + Bootstrap
- Funzione `calculate_rolling_metrics(equity: pd.Series, window: int = 126) -> pd.DataFrame`: rolling Sharpe, Sortino, MaxDD
- Funzione `aggregate_mfe_mae(trades: pd.DataFrame) -> dict`: MFE/MAE medi, massimi, per tipo segnale
- Funzione `bootstrap_confidence_intervals(returns: pd.Series, metric_fn, n_bootstrap: int = 1000, confidence: float = 0.95) -> tuple[float, float]`: intervallo di confidenza bootstrap

**Cosa NON FA:**
- NON genera visualizzazioni (Fase 26)
- NON fa grid search (Fase 25)
- NON scrive report formattati (Fase 26)

### Criteri di completamento
- [ ] `calculate_all_metrics` restituisce dict con almeno 30 metriche
- [ ] Sharpe Ratio calcolato correttamente (verificato su equity curve nota)
- [ ] Sortino Ratio > Sharpe Ratio per strategia con downside limitato
- [ ] Max Drawdown con date di picco e valle
- [ ] VaR 95%: perdita attesa nel 5% peggiore dei giorni
- [ ] CVaR 95%: perdita media oltre il VaR
- [ ] Profit Factor = gross_profit / gross_loss
- [ ] Win Rate = n_winning_trades / n_total_trades
- [ ] Rolling metrics: Series con indice temporale
- [ ] Bootstrap CI: intervallo ragionevole (non [-inf, +inf])
- [ ] Probability of Ruin: valore tra 0 e 1

### Test richiesti
- **Unit test:** `tests/test_metrics.py`
  - Test `calculate_sharpe` su equity curve lineare (rendimenti costanti) → valore noto
  - Test `calculate_sharpe` su equity curve piatta → ~0
  - Test `calculate_sortino` su equity con solo upside → infinito o molto alto
  - Test `calculate_max_drawdown` su equity con drawdown noto
  - Test `calculate_var_cvar` su distribuzione normale sintetica
  - Test `calculate_all_metrics` con 0 trade → gestione edge case
  - Test `calculate_all_metrics` con 1 trade vincente → Win Rate = 100%
  - Test `bootstrap_confidence_intervals` riproducibile con seed
  - Test `calculate_probability_of_ruin` con equity sempre crescente → ~0
  - Test `calculate_rolling_metrics` su 2 anni di dati → 4 finestre da 6 mesi

### Dipendenze
Da questa fase dipendono: **Fase 25 (Optimization), Fase 26 (Reporting)**

### Rischi
- **Rischio:** Sharpe Ratio annualizzato male → valore fuorviante
  - **Mitigazione:** `sharpe = (mean_daily_return - daily_rf) / std_daily_return * sqrt(252)`
- **Rischio:** Divisione per zero in metriche (es. Sortino con zero downside)
  - **Mitigazione:** Gestire tutti i casi: std=0 → Sharpe=0; nessuna perdita → Profit Factor=inf (o None)
- **Rischio:** Kelly Criterion usato per position sizing (il Design Document dice SOLO INFORMATIVO)
  - **Mitigazione:** Aggiungere warning nel docstring e nel report; non usare mai Kelly per calcoli automatici

### Note implementative
- `risk_free_rate` default = 0.045 (4.5%, T-bill attuale da Design Document Sezione 15)
- Annualizzazione: assumere 252 trading day/anno
- Per SQN (System Quality Number): `SQN = (expectancy / std(returns)) * sqrt(N)` dove N = numero di trade
- Ulcer Index: `sqrt(mean(drawdown^2))` dove drawdown è percentuale dal picco precedente
- Kelly Criterion: `Kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss)` — aggiungere `⚠️ SOLO INFORMATIVO` nel docstring

---

## Fase 31: Grid Search Optimizer

### Titolo
Grid Search Optimizer

### Obiettivo
Implementare `src/backtest/optimize.py`: grid search su parametri della strategia come da Sezione 6.1 del Design Document, con funzione obiettivo Sharpe Ratio e vincolo max drawdown < 25%.

### Motivazione
I parametri di default (gap 0.3%-2%, 3 barre opening range, 2 barre conferma) sono un punto di partenza. L'ottimizzazione trova la combinazione migliore sui dati in-sample, da validare poi sull'out-of-sample.

### Prerequisiti
- Fase 23 completata (Backtest Engine)
- Fase 24 completata (Metrics)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 6.1, 6.2)
- `src/backtest/engine.py`
- `src/backtest/metrics.py`
- `src/config.py`

### Output (file creati)
- **Create:** `src/backtest/optimize.py`
- **Create:** `tests/test_optimize.py`

### Componenti coinvolti
- `src/backtest/optimize.py`

### Responsabilità
**Cosa FA:**
- Funzione `grid_search(tickers, start, end, param_grid: dict, metric: str = "sharpe_ratio", constraint: dict = None) -> pd.DataFrame`: esegue grid search e restituisce DataFrame con risultati
  - Itera su tutte le combinazioni del `param_grid`
  - Per ogni combinazione: esegue backtest (in-sample only), calcola metriche
  - Applica vincolo: se `constraint` (es. max_drawdown < 0.25) non soddisfatto → scarta
  - Restituisce DataFrame ordinato per `metric` decrescente
- Funzione `get_best_params(results: pd.DataFrame, metric: str = "sharpe_ratio") -> dict`: estrae i migliori parametri
- Funzione `validate_out_of_sample(best_params: dict, tickers, start, end) -> BacktestResult`: valida i parametri ottimali sull'OOS
- Param grid di default (da Sezione 6.1):
  ```python
  DEFAULT_PARAM_GRID = {
      "gap_min_pct": [0.001, 0.002, 0.003, 0.005],
      "gap_max_pct": [0.01, 0.015, 0.02, 0.03],
      "opening_range_bars": [2, 3, 5, 10],
      "confirmation_bars": [1, 2, 3],
      "vix_max": [25, 30, 35],
      "sl_type": ["opening_range", "atr_1x", "atr_1.5x", "atr_2x"],
      "tp_type": ["prev_close", "atr_1x", "atr_2x"],
  }
  ```
- Supporto per SL/TP type alternativi (parametrizzare la logica in `signals.py` e `risk.py`)
- Funzione `save_results(results, path)`: salva i risultati in CSV
- Funzione `load_results(path) -> pd.DataFrame`: carica risultati

**Cosa NON FA:**
- NON esegue sensitivity analysis (Fase 26 richiama `optimize.py` per le heatmap)
- NON implementa Bayesian optimization (Optuna) — upgrade futuro
- NON modifica i parametri di default nel config

### Criteri di completamento
- [ ] `grid_search` con 2×2×2×2×2 = 32 combinazioni completa senza errori
- [ ] Vincolo max_drawdown < 25% applicato (combinazioni che lo violano scartate)
- [ ] `get_best_params` restituisce la combinazione con Sharpe più alto
- [ ] `validate_out_of_sample` esegue backtest SOLO su OOS
- [ ] Risultati salvabili e caricabili (CSV)
- [ ] Log dei progressi: "combinazione 15/32 completata, best Sharpe = 1.45"
- [ ] SL/TP type alternativi funzionanti (es. ATR-based SL invece di opening range)

### Test richiesti
- **Integration test:** `tests/test_optimize.py`
  - Test `grid_search` con griglia 2×2 su 1 anno SPY → risultati non vuoti
  - Test vincolo: tutte le combinazioni violano il vincolo → risultati vuoti + log WARNING
  - Test `get_best_params` su risultati noti
  - Test `validate_out_of_sample` non usa dati in-sample
  - Test `save_results` / `load_results` round-trip

### Dipendenze
Da questa fase dipende: **Fase 26 (Reporting include risultati ottimizzazione e sensitivity)**

### Rischi
- **Rischio:** Tempo di esecuzione: 4×4×4×3×3×4×3 = 6912 combinazioni, ~5 min/backtest = 576 ore
  - **Mitigazione:** Ridurre lo spazio di ricerca iniziale; parallelizzare (multiprocessing); usare risoluzione più grossolana, poi raffinare
- **Rischio:** Overfitting: parametri ottimizzati sull'in-sample ma falliscono sull'OOS
  - **Mitigazione:** Hold-out split + sensitivity analysis (Fase 26) + plateau detection (Fase 26)

### Note implementative
- La grid search può essere parallelizzata con `multiprocessing.Pool` o `concurrent.futures.ProcessPoolExecutor`
- Aggiungere `n_jobs` parametro per controllo parallelismo
- Per SL/TP type: modificare `signals.py` per accettare `sl_type` e `tp_type` come parametri (non solo opening_range e prev_close)

---

## Fase 32: Reporting & Visualization

### Titolo
Reporting & Visualization

### Obiettivo
Generare TUTTI gli output file della Sezione 5.5 e i sensitivity output della Sezione 5.4: report testuale, CSV trade/equity, grafici equity+drawdown, heatmap 2D, response surface, stability plot, plateau analysis.

### Motivazione
Senza report, i risultati del backtest sono solo numeri. I grafici e i report rendono i risultati comprensibili e permettono di identificare problemi (overfitting, cliff edge, regime dipendenza).

### Prerequisiti
- Fase 23 completata (BacktestResult)
- Fase 24 completata (Metrics)
- Fase 25 completata (Optimization results)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 5.4, 5.5, 6.2)
- `src/backtest/engine.py` (BacktestResult)
- `src/backtest/metrics.py`
- `src/backtest/optimize.py`

### Output (file creati)
- **Create:** `src/backtest/reporting.py`
- **Create:** `tests/test_reporting.py`
- Output in `reports/`:
  - `backtest_summary.txt`
  - `backtest_trades.csv`
  - `backtest_equity.csv`
  - `backtest_chart.png`
  - `sensitivity_heatmap.png`
  - `sensitivity_response_surface.png`
  - `sensitivity_stability.png`
  - `plateau_analysis.csv`
  - `regime_performance.csv`
  - `sharpe_by_regime.png`

### Componenti coinvolti
- `src/backtest/reporting.py`

### Responsabilità
**Cosa FA:**
- Funzione `generate_summary_report(metrics: dict, path: str)`: scrive report testuale formattato
- Funzione `generate_trade_csv(trades: pd.DataFrame, path: str)`: esporta trade log
- Funzione `generate_equity_csv(equity: pd.Series, path: str)`: esporta equity curve
- Funzione `generate_equity_chart(equity: pd.Series, trades: pd.DataFrame, path: str)`: grafico equity curve + drawdown con matplotlib
- Funzione `generate_sensitivity_heatmap(grid_results: pd.DataFrame, x_param: str, y_param: str, metric: str, path: str)`: heatmap 2D
- Funzione `generate_response_surface(grid_results: pd.DataFrame, path: str)`: superficie 3D `gap_min × gap_max`
- Funzione `generate_stability_plot(grid_results: pd.DataFrame, best_params: dict, path: str)`: Sharpe al variare di ogni parametro ±20%
- Funzione `calculate_plateau(grid_results: pd.DataFrame, metric: str = "sharpe_ratio", threshold: float = 0.95) -> dict`:
  - % dello spazio parametri con Sharpe ≥ 95% del massimo
  - Classificazione: picco isolato (< 5%) vs plateau (> 20%)
  - Salva `plateau_analysis.csv`
- Funzione `generate_regime_report(trades: pd.DataFrame, path: str)`: tabella Sharpe × Regime (Sezione 2.4)
- Funzione `generate_all_reports(result: BacktestResult, grid_results: pd.DataFrame, best_params: dict, output_dir: str = "reports")`: genera tutti i report in una volta

**Cosa NON FA:**
- NON esegue backtest (riceve risultati già calcolati)
- NON modifica parametri o risultati

### Criteri di completamento
- [ ] `backtest_summary.txt` contiene tutte le metriche formattate
- [ ] `backtest_trades.csv` ha le colonne: date, ticker, signal_type, entry_time, entry_price, exit_time, exit_price, pnl, mfe, mae, regime
- [ ] `backtest_equity.csv` ha colonne: date, equity, drawdown
- [ ] `backtest_chart.png` mostra equity curve (blu) e drawdown (rosso, area)
- [ ] `sensitivity_heatmap.png` generata con colorbar e annotazioni
- [ ] `regime_performance.csv` ha righe per regime con Sharpe, N trades, Win Rate, Profit Factor
- [ ] `plateau_analysis.csv` mostra % plateau e classificazione
- [ ] `sharpe_by_regime.png` mostra bar chart per regime

### Test richiesti
- **Unit test:** `tests/test_reporting.py`
  - Test `generate_summary_report` produce file non vuoto
  - Test `generate_trade_csv` ha intestazioni corrette
  - Test `calculate_plateau` su dati con plateau evidente → > 20%
  - Test `calculate_plateau` su dati con picco isolato → < 5%
  - Test `generate_regime_report` su trades con regimi noti
  - Test `generate_all_reports` crea tutti i file nella directory di output

### Dipendenze
Da questa fase non dipende nessuna fase (è terminale per il backtesting)

### Rischi
- **Rischio:** matplotlib richiede backend grafico → errore in ambiente headless
  - **Mitigazione:** Usare `matplotlib.use('Agg')` per backend non interattivo
- **Rischio:** File di report sovrascritti senza warning
  - **Mitigazione:** Aggiungere timestamp al filename o chiedere conferma (parametro `overwrite=False`)

### Note implementative
- Usare `matplotlib` con `seaborn` style
- Per l'heatmap: `seaborn.heatmap()`
- Per la response surface 3D: `matplotlib` `plot_surface` o `plotly` (opzionale)
- Grafico equity curve: doppio asse Y (sinistra: equity, destra: drawdown %)
- Colorare i trade sul grafico equity: marker verdi per win, rossi per loss

---

# MACRO FASE 6: EXECUTION LAYER

---
## Fase 33: API Documentation Generator

### Titolo
API Documentation Generator

### Obiettivo
Generare automaticamente la documentazione API del sistema usando `pdoc` o `mkdocstrings`, con output in `docs/API.md`.

### Motivazione
Un sistema di trading con 15+ moduli richiede documentazione API chiara per debugging, onboarding, e manutenzione. Senza docstring standardizzate, ogni modifica richiede reverse-engineering del codice.

### Prerequisiti
- Fase 32 completata (Reporting — il sistema è funzionante)
- Fase 2 completata (Config)
- Fase 4 completata (Logger)

### Input
- Tutti i moduli in `src/`
- `pyproject.toml` (configurazione tool)

### Output (file creati/modificati)
- **Create:** `docs/API.md` — documentazione API completa
- **Create:** `scripts/generate_docs.py` — script di generazione documentazione
- **Modify:** `pyproject.toml` — aggiungere dipendenze `pdoc` o `mkdocstrings`
- Test: `tests/test_api_docs.py` (fase 27)

### Componenti coinvolti
- `scripts/generate_docs.py`
- `docs/API.md`
- Tutti i moduli `src/` (per estrazione docstring)

### Responsabilità
**Cosa FA:**
- Installare `pdoc` (più leggero) o configurare `mkdocstrings` in `pyproject.toml`
- Creare `scripts/generate_docs.py` che:
  - Esegue `pdoc src/ -o docs/api/` o equivalente
  - Genera `docs/API.md` in formato Markdown
  - Include indice dei moduli, tree delle dipendenze, firme delle funzioni
- Verificare che OGNI funzione pubblica abbia docstring con:
  - Type hints dei parametri
  - Descrizione del valore di ritorno
  - Riferimento alla sezione del Design Document (es. `DD §4.3`)
  - Esempio di utilizzo (se applicabile)
- Aggiungere `pdoc` a `requirements-dev.txt`
- Integrare la generazione docs nel CI/CD (Fase 49)

**Cosa NON FA:**
- NON scrive docstring per funzioni private (prefisso `_`)
- NON genera documentazione per i test
- NON implementa un server di documentazione (solo file statici)

### Criteri di completamento
- [ ] `python scripts/generate_docs.py` genera `docs/API.md` senza errori
- [ ] `docs/API.md` contiene tutte le funzioni pubbliche di tutti i moduli `src/`
- [ ] Ogni funzione pubblica ha docstring con parametri, return value, e riferimento DD
- [ ] `pdoc` (o `mkdocstrings`) installato e funzionante
- [ ] La generazione docs è integrata nella CI/CD pipeline
- [ ] Nessun WARNING da pdoc su firme incomplete

### Test richiesti
- **Unit test:** `tests/test_api_docs.py`
  - Test che `docs/API.md` viene generato senza errori
  - Test che tutte le funzioni pubbliche sono documentate
  - Test che ogni funzione ha il riferimento DD nel docstring
  - Test che l'indice dei moduli è completo

### Dipendenze
Da questa fase dipende: **Fase 46 (Test Suite — verifica coverage docstring)**

### Rischi
- **Rischio:** pdoc non supporta tutte le feature di type hints Python 3.11+
  - **Mitigazione:** Verificare compatibilità prima di scegliere il tool; `mkdocstrings` (basato su mkdocs) è più robusto
- **Rischio:** Docstring non standardizzate -> documentazione generata di bassa qualità
  - **Mitigazione:** Definire un template di docstring (Google style o NumPy style); enforcement via pre-commit

### Note implementative
- Template docstring consigliato (Google style):
  ```python
  def func(param: Type) -> ReturnType:
      """Breve descrizione.
      
      Args:
          param: Descrizione parametro.
      
      Returns:
          Descrizione valore di ritorno.
      
      Ref: DD §X.Y
      """
  ```
- `pdoc` genera HTML; per Markdown usare `pdoc --output-dir docs/api/`
- Per CI/CD: aggiungere step `pdoc src/ --output-dir docs/api/` dopo i test

### Requisito Design Document
- Sezione 13 (Production Acceptance Checklist), Global Constraints (documentazione)
## Fase 34: Data Retention & Archiving

### Titolo
Data Retention & Archiving

### Obiettivo
Implementare `src/data/retention.py` per la gestione automatica della retention dei dati: log, cache OHLCV, report, trade log, e checkpoint.

### Motivazione
Senza una politica di retention, `data/cache/`, `logs/`, e `reports/` crescono indefinitamente fino a saturare il disco. La retention automatica previene questo problema e garantisce conformità con best practice di data management.

### Prerequisiti
- Fase 32 completata (Reporting)
- Fase 11 completata (OHLCV Cache)
- Fase 4 completata (Logger)
- Fase 13 completata (Calendar)

### Input
- `src/config.py`
- `src/logger.py`
- `src/data/calendar.py`
- `config/settings.yaml`

### Output (file creati/modificati)
- **Create:** `src/data/retention.py`
- **Modify:** `config/settings.yaml` — aggiungere sezione `retention`
- Test: `tests/test_retention.py` (fase 28)

### Componenti coinvolti
- `src/data/retention.py`
- `data/cache/`, `logs/`, `reports/`

### Responsabilità
**Cosa FA:**
- Funzione `cleanup_old_logs(log_dir: str, max_days: int = 30, max_size_mb: int = 10) -> int`: rimuove log più vecchi di `max_days` e file > `max_size_mb`
- Funzione `cleanup_old_cache(cache_dir: str, max_days: int = 90) -> int`: rimuove file OHLCV in cache più vecchi di 90 giorni
- Funzione `archive_reports(report_dir: str) -> int`: sposta i report in `reports/archive/YYYY-MM/` alla fine di ogni mese
- Funzione `append_trade_log(trade: dict, log_path: str)`: scrive trade in formato append-only (CSV o JSONL)
- Funzione `create_checkpoint(state: dict, checkpoint_dir: str)`: salva checkpoint ogni 7 giorni (stato portfolio, posizioni, equity)
- Funzione `cleanup_old_data(dry_run: bool = False) -> dict`: esegue tutte le pulizie e restituisce statistiche (file rimossi, spazio liberato)
- Integrare `cleanup_old_data()` nella CLI: `python -m src.cli cleanup --dry-run`
- Aggiungere sezione `retention` in `config/settings.yaml`:
  ```yaml
  retention:
    log_max_days: 30
    log_max_size_mb: 10
    cache_max_days: 90
    checkpoint_interval_days: 7
    archive_reports: true
  ```

**Cosa NON FA:**
- NON cancella dati senza dry-run preview
- NON modifica i log correnti (solo quelli archiviati/vecchi)
- NON implementa backup su cloud (S3, GCS) — v2

### Criteri di completamento
- [ ] `cleanup_old_logs()` rimuove log > 30 giorni e > 10MB
- [ ] `cleanup_old_cache()` rimuove file OHLCV > 90 giorni
- [ ] `archive_reports()` sposta report in `reports/archive/YYYY-MM/`
- [ ] `append_trade_log()` scrive in formato append-only
- [ ] `create_checkpoint()` salva stato ogni 7 giorni
- [ ] `cleanup_old_data(dry_run=True)` mostra anteprima senza cancellare
- [ ] `python -m src.cli cleanup` esegue senza errori
- [ ] `config/settings.yaml` ha sezione `retention` completa

### Test richiesti
- **Unit test:** `tests/test_retention.py`
  - Test `cleanup_old_logs` con log sintetici di varie età
  - Test `cleanup_old_cache` con file cache di date diverse
  - Test `archive_reports` crea directory `YYYY-MM/`
  - Test `append_trade_log` con trade di esempio
  - Test `create_checkpoint` serializza/deserializza stato
  - Test `cleanup_old_data(dry_run=True)` non cancella nulla
  - Test `cleanup_old_data(dry_run=False)` cancella effettivamente

### Dipendenze
Da questa fase dipende: **Fase 46 (Test Suite — verifica retention)**

### Rischi
- **Rischio:** Cancellazione accidentale di dati necessari per debug
  - **Mitigazione:** Dry-run obbligatorio prima di ogni cleanup reale; loggare ogni file rimosso
- **Rischio:** Trade log corrotto da scritture concorrenti (append-only)
  - **Mitigazione:** Usare `fcntl.flock()` o file locking; single-writer per v1

### Note implementative
- Usare `pathlib.Path` per tutte le operazioni su file
- Per l'append-only trade log: formato JSONL (una riga JSON per trade)
- Checkpoint: serializzare stato portfolio in JSON o Parquet
- Dry-run: loggare ogni file che SAREBBE stato rimosso, senza rimuoverlo
- Eseguire cleanup automaticamente ogni domenica alle 00:00 (o schedulare via cron)

### Requisito Design Document
- Sezione 7 (Data Pipeline), Sezione 10 (Monitoring & Alerting), Sezione 13.2 (Production Acceptance Checklist)

## Fase 35: Broker Base API

### Titolo
Broker Base API (Alpaca)

### Obiettivo
Implementare `src/execution/broker.py` con il wrapper per Alpaca Markets API: autenticazione, paper trading, operazioni base (account, posizioni, ordini, asset).

### Motivazione
Il broker layer è l'interfaccia tra la strategia e il mercato reale. La Sezione 9 del Design Document specifica Alpaca come broker target, con paper trading obbligatorio prima del live.

### Prerequisiti
- Fase 1 completata (config con `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 9)
- `src/config.py`

### Output (file creati)
- **Create:** `src/execution/broker.py`
- **Create:** `tests/test_broker.py`

### Componenti coinvolti
- `src/execution/broker.py`
- Alpaca API (esterna)

### Responsabilità
**Cosa FA:**
- Classe `AlpacaBroker`:
  - `__init__(config)`: inizializza client Alpaca con API key, secret, base URL (paper o live)
  - `get_account() -> dict`: restituisce info account (buying power, equity, margin)
  - `get_positions() -> list[dict]`: posizioni aperte
  - `get_position(ticker: str) -> dict | None`: posizione per ticker specifico
  - `get_orders(status: str = "open") -> list[dict]`: ordini aperti/chiusi
  - `get_order(order_id: str) -> dict`: dettaglio ordine
  - `get_asset(ticker: str) -> dict`: info asset (shortable, marginable, etc.)
  - `get_clock() -> dict`: orologio di mercato (is_open, next_open, next_close)
  - `get_bars(ticker: str, timeframe: str, start: str, end: str) -> pd.DataFrame`: dati OHLCV intraday (fallback live data)
  - `is_shortable(ticker: str) -> bool`: verifica se l'asset è shortable
- Gestione errori API: HTTP 4xx/5xx → retry con backoff
- Rate limiting: rispettare i limiti di Alpaca (200 chiamate/minuto per piano free)
- Paper trading: se `paper_trading: true` in config, usare `https://paper-api.alpaca.markets`

**Cosa NON FA:**
- NON invia ordini (Fase 30)
- NON implementa idempotenza (Fase 31)
- NON implementa state recovery (Fase 32)

### Criteri di completamento
- [ ] `AlpacaBroker` inizializzato correttamente con paper URL
- [ ] `get_account()` restituisce dict con `buying_power`, `equity`, `cash`
- [ ] `get_positions()` restituisce lista (vuota se nessuna posizione)
- [ ] `get_asset("AAPL").shortable` è True (AAPL è sempre shortable)
- [ ] `get_clock().is_open` è bool corretto
- [ ] `is_shortable("AAPL")` → True
- [ ] API key mancante → eccezione chiara all'inizializzazione
- [ ] HTTP 429 → retry dopo `Retry-After` header
- [ ] HTTP 503 → retry con backoff, poi log ERROR

### Test richiesti
- **Unit test:** `tests/test_broker.py`
  - Test `get_account` con mock HTTP 200
  - Test `get_positions` con mock (lista vuota e lista con 2 posizioni)
  - Test `get_asset` shortable e non shortable
  - Test `get_clock` mercato aperto e chiuso
  - Test HTTP 429 → retry
  - Test HTTP 503 → retry × 3 → eccezione
  - Test `is_shortable` True e False
  - Test inizializzazione senza API key → eccezione
- **Integration test (manuale):** Eseguire con paper API key reale e verificare `get_account()`

### Dipendenze
Da questa fase dipendono: **Fase 30 (Bracket Orders), Fase 31 (Idempotency), Fase 32 (Recovery)**

### Rischi
- **Rischio:** API key live usata accidentalmente in paper → trading reale non intenzionale
  - **Mitigazione:** `AlpacaBroker` controlla `paper_trading` config; se True, forza URL paper anche se la key è live
- **Rischio:** Dipendenza da `alpaca-py` vs `alpaca-trade-api` — API diverse
  - **Mitigazione:** Verificare quale package è più aggiornato; `alpaca-py` è l'SDK ufficiale più recente

### Note implementative
- Usare `alpaca-py` (più recente): `from alpaca.trading.client import TradingClient`
- Paper URL: `https://paper-api.alpaca.markets`
- Live URL: `https://api.alpaca.markets`
- Metodi asincroni? Per v1, usare API sincrona; migrare ad async in v2 per performance

---

## Fase 36: Bracket Order Construction

### Titolo
Bracket Order Construction

### Obiettivo
Aggiungere al broker la costruzione e l'invio di bracket order (stop-limit entry + TP limit + SL stop market) come da Sezioni 9.2 e 9.3 del Design Document.

### Motivazione
I bracket order sono il meccanismo di esecuzione: permettono di entrare, impostare take profit e stop loss in un unico ordine, riducendo il rischio di esecuzione parziale.

### Prerequisiti
- Fase 27 completata (Broker Base)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 9.2, 9.3)
- `src/execution/broker.py`
- `src/strategy/signals.py` (per entry_price, sl_price, tp_price)

### Output (file modificati)
- **Modify:** `src/execution/broker.py` — aggiungere metodi `submit_bracket_order()`, `submit_entry_order()`, `cancel_order()`
- **Modify:** `tests/test_broker.py` — test per bracket order

### Componenti coinvolti
- `src/execution/broker.py`

### Responsabilità
**Cosa FA:**
- Funzione `submit_bracket_order(ticker: str, qty: int, signal_type: str, entry_stop_price: float, entry_limit_price: float, tp_price: float, sl_price: float) -> dict`:
  - Costruisce bracket order con:
    - Entry: stop-limit order. `stop_price = entry_stop_price` (opening range breakout). `limit_price = entry_limit_price` (stop + 0.1%)
    - TP: limit order a `tp_price` (PrevClose)
    - SL: stop market order a `sl_price`
    - `time_in_force = "day"` (scade a fine giornata)
  - Invia a paper endpoint
  - Restituisce dict con `order_id`, `status`, `client_order_id`
- Funzione `submit_entry_only(ticker: str, qty: int, signal_type: str, entry_stop_price: float, entry_limit_price: float) -> dict`: solo entry (senza bracket, per testing)
- Funzione `cancel_order(order_id: str) -> bool`: cancella un ordine
- Funzione `cancel_all_orders() -> int`: cancella tutti gli ordini aperti
- Gestione errori: ordine rifiutato → log ERROR con motivo; retry con backoff
- Verifica pre-invio:
  - `is_shortable(ticker)` per segnali SHORT
  - `get_clock().is_open` (mercato aperto)
  - `get_account().buying_power` sufficiente

**Cosa NON FA:**
- NON implementa `client_order_id` deterministico (Fase 31)
- NON riconcilia ordini dopo invio (Fase 31)
- NON gestisce recovery (Fase 32)

### Criteri di completamento
- [ ] `submit_bracket_order("AAPL", 100, "LONG", 150.0, 150.15, 151.0, 149.0)` invia ordine (paper)
- [ ] Ordine SHORT senza disponibilità short → rifiutato con log ERROR
- [ ] `cancel_order(order_id)` cancella ordine esistente
- [ ] `cancel_all_orders()` cancella tutti gli ordini
- [ ] Mercato chiuso → ordine rifiutato con log WARNING
- [ ] Buying power insufficiente → ordine rifiutato con log WARNING
- [ ] `time_in_force = "day"` su tutti gli ordini

### Test richiesti
- **Unit test:** `tests/test_broker.py` (aggiunte)
  - Test `submit_bracket_order` LONG con mock HTTP 200
  - Test `submit_bracket_order` SHORT con mock HTTP 200
  - Test `submit_bracket_order` con ticker non shortable → rifiutato
  - Test `submit_bracket_order` con mercato chiuso → rifiutato
  - Test `cancel_order` con mock HTTP 200
  - Test `cancel_all_orders` con mock
  - Test HTTP 422 (unprocessable) → log ERROR con dettagli

### Dipendenze
Da questa fase dipendono: **Fase 31 (Idempotency), Fase 32 (Recovery), Fase 36 (Paper Trading)**

### Rischi
- **Rischio:** Prezzo stop-limit troppo vicino al mercato → ordine eseguito immediatamente a prezzo peggiore
  - **Mitigazione:** `limit_price = stop_price * 1.001` (0.1% sopra lo stop per LONG, sotto per SHORT)
- **Rischio:** Ordine parzialmente eseguito → bracket TP/SL non proporzionali alla quantità eseguita
  - **Mitigazione:** Alpaca gestisce automaticamente il bracket OCO (One-Cancels-Other); se entry è partial fill, TP/SL si applicano solo alla quantità eseguita

### Note implementative
- Alpaca supporta bracket order nativamente: `OrderSide.BUY`, `OrderType.STOP_LIMIT`, `OrderClass.BRACKET`
- `take_profit` e `stop_loss` sono parametri del bracket order
- Verificare la sintassi esatta nell'SDK `alpaca-py`

---

## Fase 37: Order Idempotency & Reconciliation

### Titolo
Order Idempotency & Reconciliation

### Obiettivo
Implementare idempotenza ordini (client_order_id deterministico) e riconciliazione ordini locale-vs-broker, come da Sezioni 9.6 e 9.7 del Design Document.

### Motivazione
In caso di timeout o disconnessione, il retry di un ordine NON deve creare duplicati. La riconciliazione periodica assicura che lo stato locale rifletta sempre lo stato reale del broker.

### Prerequisiti
- Fase 27 completata (Broker Base)
- Fase 30 completata (Bracket Orders)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 9.6, 9.7)
- `src/execution/broker.py`

### Output (file modificati)
- **Modify:** `src/execution/broker.py` — aggiungere `generate_client_order_id()`, `reconcile()`, `sync_from_broker()`
- **Modify:** `tests/test_broker.py`

### Componenti coinvolti
- `src/execution/broker.py`

### Responsabilità
**Cosa FA:**
- Funzione `generate_client_order_id(date: date, ticker: str, signal_type: str, attempt: int) -> str`:
  - Formato: `{date}_{ticker}_{signal_type}_{attempt}`
  - Esempio: `2026-07-09_AAPL_LONG_1`
- Modificare `submit_bracket_order` per usare `generate_client_order_id` automaticamente
- Funzione `reconcile(local_positions: list[dict], local_orders: list[dict]) -> dict`:
  - Recupera posizioni e ordini da Alpaca
  - Confronta con stato locale
  - Restituisce `mismatches` (differenze) e `actions` (azioni correttive)
  - Se mismatch: logga ERROR, invia alert webhook, sincronizza
- Funzione `sync_from_broker(broker_positions: list[dict], broker_orders: list[dict])`: aggiorna stato locale dal broker (broker è source of truth)
- Funzione `verify_clock_sync() -> bool`: verifica che l'orologio di sistema sia sincronizzato con Alpaca entro ±100ms
- Retry idempotente: se `submit_bracket_order` va in timeout, il retry con lo stesso `client_order_id` è sicuro (Alpaca riconosce l'idempotenza)

**Cosa NON FA:**
- NON implementa la logica di recovery completa (Fase 32)
- NON modifica il portfolio manager (la riconciliazione aggiorna il broker, il PM viene aggiornato separatamente)

### Criteri di completamento
- [ ] `generate_client_order_id(date(2026,7,9), "AAPL", "LONG", 1)` → `"2026-07-09_AAPL_LONG_1"`
- [ ] Due chiamate `generate_client_order_id` con stessi parametri → stesso ID
- [ ] `submit_bracket_order` include `client_order_id` nell'ordine
- [ ] `reconcile` senza mismatch → `mismatches` vuoto
- [ ] `reconcile` con posizione in più sul broker → `mismatches` contiene la differenza
- [ ] `sync_from_broker` aggiorna stato locale con posizioni del broker
- [ ] `verify_clock_sync()` restituisce True se drift < 100ms

### Test richiesti
- **Unit test:** `tests/test_broker.py` (aggiunte)
  - Test `generate_client_order_id` formato corretto
  - Test `generate_client_order_id` idempotente
  - Test `reconcile` con stato identico → nessun mismatch
  - Test `reconcile` con broker che ha posizione extra → mismatch rilevato
  - Test `reconcile` con broker che NON ha posizione che il locale pensa di avere → mismatch rilevato
  - Test `sync_from_broker` con 2 posizioni broker → stato locale aggiornato
  - Test `verify_clock_sync` (mock `alpaca.get_clock()`)

### Dipendenze
Da questa fase dipendono: **Fase 32 (Recovery), Fase 36 (Paper Trading)**

### Rischi
- **Rischio:** `client_order_id` non accettato da Alpaca (formato o lunghezza)
  - **Mitigazione:** Alpaca accetta stringhe fino a 48 caratteri; il formato `YYYY-MM-DD_TICKER_TYPE_N` è sicuro
- **Rischio:** Riconciliazione troppo frequente → rate limiting
  - **Mitigazione:** Eseguire riconciliazione ogni 60 secondi (non a ogni tick)

### Note implementative
- Alpaca supporta `client_order_id` personalizzato; se già usato, restituisce l'ordine esistente (idempotenza)
- Per la sincronizzazione orologio: `abs(alpaca.get_clock().timestamp - datetime.now(EST)).total_seconds() < 0.1`
- La riconciliazione va schedulata (es. `threading.Timer` o loop principale) — non bloccante

---

## Fase 38: State Recovery (Crash Recovery)

### Titolo
State Recovery (Crash Recovery)

### Obiettivo
Implementare la logica di recovery dopo crash/disconnessione come da Sezione 9.7 del Design Document: recupero posizioni aperte, ordini pendenti, riconciliazione, e ripristino monitoraggio.

### Motivazione
Se il sistema crasha a metà giornata con posizioni aperte, al restart deve recuperare lo stato dal broker e riprendere il monitoraggio, non lasciare posizioni aperte incustodite.

### Prerequisiti
- Fase 19 completata (Portfolio Manager)
- Fase 31 completata (Reconciliation)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 9.7)
- `src/execution/broker.py`
- `src/portfolio/manager.py`

### Output (file creati/modificati)
- **Create:** `src/execution/recovery.py`
- **Modify:** `src/execution/broker.py` — aggiungere `recover_state()`
- **Create:** `tests/test_recovery.py`

### Componenti coinvolti
- `src/execution/recovery.py`

### Responsabilità
**Cosa FA:**
- Funzione `recover_state(broker: AlpacaBroker, portfolio: PortfolioManager, logger) -> dict`:
  - Step 1: Recupera posizioni aperte da Alpaca (`broker.get_positions()`)
  - Step 2: Recupera ordini aperti da Alpaca (`broker.get_orders(status='open')`)
  - Step 3: Riconcilia con stato locale (`broker.reconcile(local, broker)`)
  - Step 4: Per ogni posizione aperta sul broker, crea entry nel portfolio manager
  - Step 5: Per ogni ordine aperto sul broker, imposta stato PENDING nel portfolio
  - Step 6: Ripristina monitoraggio TP/SL per posizioni attive
  - Step 7: Logga l'evento (INFO: "Recovery completato: X posizioni, Y ordini")
  - Restituisce dict con `recovered_positions`, `recovered_orders`, `errors`
- Funzione `emergency_close_all(broker: AlpacaBroker) -> int`: chiude TUTTE le posizioni a mercato (pulsante di emergenza)
- Funzione `save_checkpoint(portfolio: PortfolioManager, path: str)`: salva stato portfolio su disco
- Funzione `load_checkpoint(path: str) -> PortfolioManager`: ripristina portfolio da checkpoint

**Cosa NON FA:**
- NON modifica la logica di trading (solo recovery)
- NON decide autonomamente se chiudere posizioni (salvo `emergency_close_all` che è esplicito)

### Criteri di completamento
- [ ] `recover_state` con broker senza posizioni → portfolio vuoto, 0 posizioni recuperate
- [ ] `recover_state` con broker che ha 1 posizione AAPL LONG → portfolio ripristinato con quella posizione
- [ ] `recover_state` con broker che ha 1 ordine pending → portfolio in stato PENDING per quel ticker
- [ ] `emergency_close_all` invia ordini market per tutte le posizioni
- [ ] `save_checkpoint` / `load_checkpoint` round-trip: portfolio identico
- [ ] Loggato ogni step della recovery con dettagli
- [ ] Webhook alert inviato se recovery rileva anomalie (es. posizioni senza ordini corrispondenti)

### Test richiesti
- **Unit test:** `tests/test_recovery.py`
  - Test `recover_state` con broker vuoto
  - Test `recover_state` con 1 posizione, 0 ordini
  - Test `recover_state` con 1 posizione, 1 ordine (entry pending)
  - Test `recover_state` con broker irraggiungibile → eccezione gestita
  - Test `emergency_close_all` con 3 posizioni → 3 ordini market inviati
  - Test `save_checkpoint` / `load_checkpoint` round-trip
  - Test `load_checkpoint` con file corrotto → eccezione gestita
- **Integration test:** `tests/test_replay.py` (Fase 35) include recovery scenario

### Dipendenze
Da questa fase dipendono: **Fase 36 (Paper Trading), Fase 39 (Final Validation)**

### Rischi
- **Rischio:** Recovery failisce → posizioni rimangono aperte senza monitoring
  - **Mitigazione:** Se recovery fallisce dopo 3 tentativi, esegui `emergency_close_all` e logga CRITICAL
- **Rischio:** Stato locale corrotto → recovery carica stato inconsistente
  - **Mitigazione:** Il broker è SEMPRE source of truth; lo stato locale viene completamente sovrascritto dal broker durante recovery

### Note implementative
- Il checkpoint va salvato dopo ogni transizione di stato significativa (entry, exit)
- Formato checkpoint: JSON o pickle (JSON preferibile per debugging)
- Recovery va chiamato automaticamente all'avvio del sistema live

---

## Fase 39: Central CLI

### Titolo
Central CLI

### Obiettivo
Implementare `src/cli.py` come entry point unificato con i comandi: `backtest`, `optimize`, `scan`, `run`, `eda`.

### Motivazione
La CLI è il punto di ingresso per l'utente e per l'agente AI. Unifica tutte le funzionalità in un'interfaccia a riga di comando coerente.

### Prerequisiti
- Fase 23 (Backtest), Fase 25 (Optimize), Fase 15 (Scanner), Fase 26 (Reporting), Fase 4 (EDA) — ognuno per il proprio comando

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 3, 3.1)
- Tutti i moduli del sistema

### Output (file creati)
- **Create:** `src/cli.py`
- **Create:** `tests/test_cli.py`

### Componenti coinvolti
- `src/cli.py`

### Responsabilità
**Cosa FA:**
- Comando `backtest`:
  - `python -m src.cli backtest --tickers AAPL,MSFT,GOOGL --start 2023-01-01 --end 2024-12-31 --output reports/`
  - Esegue `BacktestEngine.run()`, calcola metriche, genera report
- Comando `optimize`:
  - `python -m src.cli optimize --tickers SPY --start 2020-01-01 --end 2024-12-31`
  - Esegue grid search, stampa best params, valida OOS
- Comando `scan`:
  - `python -m src.cli scan --tickers AAPL,MSFT,TSLA`
  - Esegue `Scanner.scan_premarket()` e stampa watchlist
- Comando `run`:
  - `python -m src.cli run --mode paper`
  - Avvia l'esecuzione live (paper trading)
- Comando `eda`:
  - `python -m src.cli eda --mode simple|conditional`
  - Esegue EDA
- Opzioni globali:
  - `--config`: path alternativo a `settings.yaml`
  - `--log-level`: DEBUG/INFO/WARNING/ERROR
  - `--seed`: seed per random number generator (riproducibilità)
- Help per ogni comando: `python -m src.cli backtest --help`

**Cosa NON FA:**
- NON implementa logica di business (delega ai moduli)
- NON fa parsing complesso (usa `argparse`, non framework pesanti)

### Criteri di completamento
- [ ] `python -m src.cli --help` mostra tutti i comandi
- [ ] `python -m src.cli backtest --help` mostra le opzioni
- [ ] `python -m src.cli scan --tickers AAPL` esegue senza errori
- [ ] `python -m src.cli eda --mode simple` esegue EDA
- [ ] `--config` override funzionante
- [ ] `--seed` passato a tutti i moduli che usano random
- [ ] Errori gestiti con messaggi chiari (non traceback grezzi)

### Test richiesti
- **Integration test:** `tests/test_cli.py`
  - Test `backtest` con parametri validi → exit code 0
  - Test `scan` con ticker validi → output non vuoto
  - Test `--config` con file inesistente → messaggio errore chiaro
  - Test comando inesistente → messaggio help
  - Test `--log-level DEBUG` → log più verboso

### Dipendenze
Da questa fase dipende: **Nessuna (è terminale, ma usata per test manuali di tutte le fasi)**

### Rischi
- **Rischio:** `argparse` diventa complesso con troppi sottocomandi
  - **Mitigazione:** Usare `argparse` con `subparsers`; se diventa troppo complesso, migrare a `click` in v2
- **Rischio:** Comando `run` parte in produzione accidentalmente
  - **Mitigazione:** Richiedere flag `--confirm` o `--mode live` esplicito per live trading

### Note implementative
- Usare `argparse` con `ArgumentParser` e `add_subparsers()`
- Ogni comando è una funzione separata (`cmd_backtest`, `cmd_scan`, etc.)
- Il main è `if __name__ == "__main__"` in `cli.py`, o entry point in `pyproject.toml`
- Per `--seed`, propagare a `random.seed()`, `numpy.random.seed()`, e a tutti i moduli che accettano `seed`

---

# MACRO FASE 7: OPERATIONS

---

## Fase 40: Alerting & Monitoring Hub

### Titolo
Alerting & Monitoring Hub

### Obiettivo
Estendere `src/logger.py` con webhook Discord/Slack e implementare il daily summary come da Sezione 10.2 del Design Document.

### Motivazione
Il sistema deve notificare errori critici (API down, ordini rifiutati, crash) e inviare un riepilogo giornaliero. Senza alerting, un problema potrebbe passare inosservato per ore.

### Prerequisiti
- Fase 2 completata (Logger base)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 10.2)
- `src/logger.py`
- `src/config.py` (DISCORD_WEBHOOK_URL, SLACK_WEBHOOK_URL)

### Output (file creati/modificati)
- **Create:** `src/alerting.py`
- **Modify:** `src/logger.py` — aggiungere hook per alerting
- **Create:** `tests/test_alerting.py`

### Componenti coinvolti
- `src/alerting.py`
- `src/logger.py`

### Responsabilità
**Cosa FA:**
- Funzione `send_discord_webhook(message: str, webhook_url: str, username: str = "GapMR Bot") -> bool`: invia messaggio Discord
- Funzione `send_slack_webhook(message: str, webhook_url: str) -> bool`: invia messaggio Slack
- Funzione `send_alert(message: str, level: str = "ERROR")`: invia a tutti i canali configurati (Discord + Slack + log file)
- Funzione `send_daily_summary(trades: list[dict], pnl: float, date: date, webhook_url: str)`: formatta e invia riepilogo giornaliero con:
  - Data, N trades, P&L giornaliero, P&L cumulativo
  - Miglior trade, Peggior trade
  - Errori della giornata
  - Formattazione Markdown (Discord) o Block Kit (Slack)
- Funzione `add_loguru_alert_sink()`: aggiunge un sink a `loguru` che inoltra ERROR e CRITICAL ai webhook
- Gestione errori webhook: timeout, HTTP error → log WARNING locale (non cascata di errori)
- Rate limiting: non più di 1 alert ogni 60 secondi per lo stesso tipo di errore

**Cosa NON FA:**
- NON modifica la logica di trading
- NON implementa monitoring avanzato (Prometheus, Grafana) — v2

### Criteri di completamento
- [ ] `send_discord_webhook("Test message", url)` invia messaggio (verificabile manualmente)
- [ ] `send_daily_summary` formatta correttamente con emoji, grassetti, codice
- [ ] `add_loguru_alert_sink` intercetta log ERROR e li inoltra ai webhook
- [ ] Rate limiting: due ERROR identici entro 60s → solo il primo inviato
- [ ] Webhook down → log WARNING locale, nessun crash
- [ ] Webhook URL non configurato → log INFO "alerting non configurato", nessun errore

### Test richiesti
- **Unit test:** `tests/test_alerting.py`
  - Test `send_discord_webhook` con mock HTTP 204 → True
  - Test `send_discord_webhook` con mock HTTP 429 → retry, poi False
  - Test `send_daily_summary` formattazione con dati noti
  - Test `send_daily_summary` con 0 trade
  - Test `add_loguru_alert_sink`: log.error() → webhook chiamato
  - Test rate limiting: due chiamate in 30s → solo una inviata
  - Test webhook URL vuoto → nessun tentativo di invio

### Dipendenze
Da questa fase dipende: **Fase 36 (Paper Trading usa alerting)**

### Rischi
- **Rischio:** Webhook URL esposto nei log →泄露 canale Discord/Slack
  - **Mitigazione:** Non loggare mai il webhook URL completo; oscurare con `***`
- **Rischio:** Troppi alert → canale Discord/Slack inondato
  - **Mitigazione:** Rate limiting + raggruppamento (batch alert ogni 5 minuti)

### Note implementative
- Usare `requests.post()` per webhook
- Discord: `{"content": message}`, max 2000 caratteri
- Slack: `{"text": message}` (semplice) o Block Kit per formattazione avanzata
- Colori/emoji: Discord supporta ```` ```diff ``` ```` per blocchi codice colorati
- Daily summary: schedulare alle 16:30 EST (dopo market close)

---
## Fase 41: Health Check & Heartbeat

### Titolo
Health Check & Heartbeat

### Obiettivo
Implementare `src/health.py` con health check JSON e heartbeat periodico per monitoring del sistema in produzione.

### Motivazione
In produzione, è critico sapere se il sistema è vivo, se il broker è raggiungibile, e se le API keys sono valide. Un heartbeat mancante per >10 minuti deve generare un alert immediato.

### Prerequisiti
- Fase 40 completata (Alerting — per inviare alert su heartbeat mancante)
- Fase 35 completata (Broker Base API)
- Fase 2 completata (Config)
- Fase 4 completata (Logger)

### Input
- `src/config.py`
- `src/logger.py`
- `src/execution/broker.py`

### Output (file creati/modificati)
- **Create:** `src/health.py`
- Test: `tests/test_health.py` (fase 35)

### Componenti coinvolti
- `src/health.py`

### Responsabilità
**Cosa FA:**
- Funzione `health_check() -> dict`: restituisce JSON con:
  ```json
  {
    "status": "healthy" | "degraded" | "unhealthy",
    "uptime_seconds": 123456,
    "last_trade_time": "2026-07-09T15:30:00-04:00",
    "checks": {
      "broker_connected": true,
      "api_keys_valid": true,
      "disk_space_gb": 45.2,
      "memory_usage_pct": 62.3,
      "open_positions": 2,
      "pending_orders": 0
    }
  }
  ```
- Funzione `send_heartbeat() -> bool`: invia heartbeat ogni 5 minuti (scrive timestamp in file o chiama webhook)
- Funzione `check_heartbeat(max_missing_minutes: int = 10) -> bool`: verifica che l'ultimo heartbeat sia entro `max_missing_minutes`; se mancante -> alert CRITICAL
- Endpoint HTTP opzionale: se `health_port` configurato, avvia un server HTTP minimale che espone `/health` e `/heartbeat`
- Verifica broker: `broker.get_account()` non solleva eccezioni
- Verifica API keys: test di autenticazione senza eseguire trade
- Verifica disco: `shutil.disk_usage()` su `data/` e `logs/`
- Integrare con Alerting (Fase 40): heartbeat mancante -> `alerting.send_alert("CRITICAL", "Heartbeat missing for 15 minutes")`

**Cosa NON FA:**
- NON sostituisce il kill switch (Fase 50)
- NON esegue trade o modifica lo stato del sistema
- NON implementa un server HTTP completo (solo endpoint minimali)

### Criteri di completamento
- [ ] `health_check()` restituisce JSON valido con tutti i campi
- [ ] `health_check()` rileva broker disconnesso -> `status: "unhealthy"`
- [ ] `health_check()` rileva API keys invalide -> `status: "degraded"`
- [ ] `send_heartbeat()` scrive timestamp e chiama webhook
- [ ] `check_heartbeat()` rileva heartbeat mancante > 10 minuti
- [ ] Heartbeat mancante -> alert CRITICAL inviato
- [ ] Endpoint HTTP risponde su porta configurabile (se abilitato)
- [ ] `health_port` in `config/settings.yaml`

### Test richiesti
- **Unit test:** `tests/test_health.py`
  - Test `health_check()` con broker mock funzionante -> healthy
  - Test `health_check()` con broker mock disconnesso -> unhealthy
  - Test `send_heartbeat()` scrive timestamp
  - Test `check_heartbeat()` con heartbeat recente -> OK
  - Test `check_heartbeat()` con heartbeat vecchio -> CRITICAL alert
  - Test endpoint HTTP `/health` restituisce 200
  - Test endpoint HTTP `/heartbeat` aggiorna timestamp

### Dipendenze
Da questa fase dipendono: **Fase 46 (Test Suite — health check integration test), Fase 51 (Paper Trading — monitoring continuo)**

### Rischi
- **Rischio:** Health check HTTP endpoint esposto senza autenticazione -> information leak
  - **Mitigazione:** Binding su `localhost` only di default; opzionale basic auth
- **Rischio:** False positive su API keys (test autenticazione fallisce per rate limiting, non per key invalida)
  - **Mitigazione:** Distinguere HTTP 401/403 (key invalida) da HTTP 429 (rate limit); loggare chiaramente

### Note implementative
- HTTP server: usare `http.server` della stdlib (nessuna dipendenza esterna)
- Heartbeat file: `data/heartbeat.txt` con timestamp ISO 8601
- Uptime: `time.time() - start_time` (salvato all'avvio del processo)
- Aggiungere sezione `health` in `config/settings.yaml`:
  ```yaml
  health:
    heartbeat_interval_minutes: 5
    heartbeat_timeout_minutes: 10
    health_port: null  # 8080 per abilitare
  ```

### Requisito Design Document
- Sezione 10 (Monitoring & Alerting), Sezione 13.2 (Production Acceptance Checklist)

## Fase 42: Pre-commit Hooks

### Titolo
Pre-commit Hooks (Black, Ruff, MyPy)

### Obiettivo
Configurare pre-commit hooks per formatting (Black), linting (Ruff), e type checking (MyPy) da eseguire automaticamente a ogni commit.

### Motivazione
Code quality enforcement automatico previene che codice non formattato o con type error venga committato, riducendo il carico di review.

### Prerequisiti
- Fase 0.5 completata (dependency lock con black, ruff, mypy installati)
- Fase 1 completata (config)

### Input
- `pyproject.toml` (configurazioni tool)
- `requirements-dev.txt`

### Output (file creati/modificati)
- **Create:** `.pre-commit-config.yaml`
- **Modify:** `pyproject.toml` — verificare sezioni `[tool.black]`, `[tool.ruff]`, `[tool.mypy]`
- Test: verifica manuale (`pre-commit run --all-files`)

### Componenti coinvolti
- `.pre-commit-config.yaml`
- `pyproject.toml`

### Responsabilità
**Cosa FA:**
- Creare `.pre-commit-config.yaml` con:
  - `black` (line-length=100, target-version=py311)
  - `ruff` (con regole `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM`)
  - `mypy` (strict mode, ma con `ignore_missing_imports = true` per pacchetti senza stubs)
- Configurare `pyproject.toml` con tutte le opzioni necessarie
- Installare hooks: `pre-commit install`
- Verificare: `pre-commit run --all-files` passa senza errori

**Cosa NON FA:**
- NON esegue test (Fase 36)
- NON configura CI/CD (Fase 49)

### Criteri di completamento
- [ ] `.pre-commit-config.yaml` creato e valido
- [ ] `pre-commit install` eseguito con successo
- [ ] `pre-commit run --all-files` passa su tutti i file esistenti
- [ ] Black formatta automaticamente senza errori
- [ ] Ruff non riporta errori di linting
- [ ] MyPy type checking passa

### Test richiesti
- Verifica manuale: `pre-commit run --all-files`

### Dipendenze
Da questa fase dipende: **Fase 49 (CI/CD Workflow)**

### Rischi
- **Rischio:** MyPy troppo restrittivo su codice esistente → centinaia di errori
  - **Mitigazione:** Configurazione graduale: `ignore_missing_imports = true`, `disallow_untyped_defs = false` inizialmente
- **Rischio:** Black riformatta tutto il codice al primo commit → diff enorme
  - **Mitigazione:** Eseguire `black .` separatamente e committare la riformattazione come commit dedicato

### Note implementative
- `.pre-commit-config.yaml` usa `rev: stable` per black
- Ruff rules: `select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]`
- MyPy: `python_version = "3.11"`, `strict = false` inizialmente

### Requisito Design Document
- Sezione 13 (Production Acceptance Checklist), Global Constraints

---

## Fase 43: GitHub Actions CI/CD Workflow

> **NOTA ORDINE ESECUZIONE:** La Fase 43 (CI/CD) viene configurata PRIMA della Fase 46 (Test Suite). Il CI/CD pipeline e definito con placeholder per i test; i test reali vengono aggiunti in Fase 46. L ordine di esecuzione e: Fase 42 (Pre-commit) -> Fase 43 (CI/CD setup) -> ... -> Fase 46 (Test Suite) -> CI/CD viene aggiornato con i test reali.

### Titolo
GitHub Actions CI/CD Workflow

### Obiettivo
Configurare una GitHub Actions pipeline per test automatici, coverage, e type checking a ogni push e PR.

### Motivazione
CI/CD garantisce che ogni modifica sia testata automaticamente prima del merge, prevenendo regressioni e mantenendo la qualità del codice.

### Prerequisiti
- Fase 48 completata (pre-commit hooks)
- Fase 36 completata (test suite)
- Repository Git inizializzato e connesso a GitHub

### Input
- Configurazioni da `pyproject.toml`
- `requirements.txt`, `requirements-dev.txt`
- Test suite

### Output (file creati)
- **Create:** `.github/workflows/ci.yml`
- **Create:** `.github/workflows/daily-scan.yml` (opzionale — smoke test giornaliero)
- Test: CI/CD pipeline testata con un push

### Componenti coinvolti
- `.github/workflows/ci.yml`

### Responsabilità
**Cosa FA:**
- Creare `.github/workflows/ci.yml` con job:
  - **Lint:** black --check, ruff check, mypy
  - **Test:** pytest con coverage report
  - **Coverage gate:** coverage ≥ 80% (warning se sotto, fail se sotto 60%)
- Matrix testing: Python 3.11, 3.12
- Caching: pip cache, pre-commit cache
- Upload coverage a GitHub Actions artifacts
- Trigger: push su `main` e `develop`, PR su `main`

**Cosa NON FA:**
- NON deploya in produzione (Fase 52)
- NON esegue test su Windows/macOS (solo ubuntu-latest per v1)

### Criteri di completamento
- [ ] `.github/workflows/ci.yml` creato e valido
- [ ] Push su branch attiva la pipeline
- [ ] Tutti i job passano (lint, test, coverage)
- [ ] Coverage report generato e visibile
- [ ] PR con test falliti → merge bloccato (branch protection rule)

### Test richiesti
- Integration test: push su branch di test e verifica pipeline

### Dipendenze
Da questa fase dipende: **Fase 50 (Docker), Fase 52 (Production Release)**

### Rischi
- **Rischio:** Test troppo lenti → CI/CD timeout
  - **Mitigazione:** Separare unit test (veloci) da integration test (lenti); eseguire unit test a ogni push, integration test solo su PR
- **Rischio:** Secrets non configurati (API keys per test)
  - **Mitigazione:** Mockare tutte le API esterne nei test; documentare i secrets necessari

### Note implementative
- Usare `actions/setup-python@v5` e `actions/cache@v4`
- Coverage con `pytest-cov`: `pytest --cov=src --cov-report=term --cov-report=xml`
- Branch protection: richiedere CI passante prima del merge (da configurare su GitHub)
- Secrets: `FINNHUB_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` come GitHub Secrets

### Requisito Design Document
- Sezione 13.2 (Production Acceptance Checklist)

---

## Fase 44: Docker Containerization

### Titolo
Docker Containerization

### Obiettivo
Creare un Dockerfile multi-stage per il deployment della strategia in container.

### Motivazione
Docker garantisce un ambiente di esecuzione identico tra sviluppo, CI/CD, e produzione. Semplifica il deployment su VPS/cloud e il rollback.

### Prerequisiti
- Fase 49 completata (CI/CD)
- Docker installato

### Input
- `requirements.txt`
- `requirements-dev.txt`
- Codice sorgente in `src/`

### Output (file creati)
- **Create:** `Dockerfile`
- **Create:** `.dockerignore`
- **Create:** `docker-compose.yml` (opzionale, per orchestrazione)
- Test: `docker build` e `docker run` smoke test

### Componenti coinvolti
- `Dockerfile`
- `.dockerignore`

### Responsabilità
**Cosa FA:**
- Creare `Dockerfile` multi-stage:
  - **Stage 1 (builder):** installa dipendenze
  - **Stage 2 (runtime):** copia solo artefatti necessari, user non-root
- Includere entrypoint che esegue lo script paper/live
- Health check endpoint (opzionale): `curl localhost:8080/health`
- `.dockerignore`: esclude `data/cache/`, `logs/`, `reports/`, `.git/`, `.venv/`
- `docker-compose.yml`: servizio con volume mounts per config e dati

**Cosa NON FA:**
- NON configura orchestrazione (Kubernetes) — v2
- NON implementa auto-scaling

### Criteri di completamento
- [ ] `docker build -t gap-mr .` completa senza errori
- [ ] `docker run --rm gap-mr python -m pytest` esegue i test
- [ ] Container size < 1GB
- [ ] User non-root nel container
- [ ] `.dockerignore` esclude file sensibili e cache
- [ ] `docker-compose up` avvia il servizio

### Test richiesti
- Integration test: `docker build && docker run` smoke test

### Dipendenze
Da questa fase dipende: **Fase 52 (Production Release — deployment containerizzato)**

### Rischi
- **Rischio:** Dimensione container eccessiva (> 2GB)
  - **Mitigazione:** Multi-stage build; escludere cache e file non necessari; usare `python:3.11-slim`
- **Rischio:** Secrets nel container
  - **Mitigazione:** Usare env vars o Docker secrets; MAI hardcodare API keys nel Dockerfile

### Note implementative
- Base image: `python:3.11-slim` (più leggera di `python:3.11`)
- Non copiare `.env` nel container (usare env vars o volume mount)
- Entrypoint: `python -m src.cli run --mode ${TRADE_MODE:-paper}`
- Health check: se il sistema espone un endpoint HTTP, `HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1`

### Requisito Design Document
- Sezione 13 (Production Acceptance Checklist)
---

## Fase 45: Secrets Management & Security Audit

### Titolo
Secrets Management & Security Audit

### Obiettivo
Eseguire un audit di sicurezza completo e implementare best practice per la gestione dei secrets: nessuna API key hardcodata, `.env` in `.gitignore`, log senza secrets, Docker senza `.env`.

### Motivazione
Una singola API key committata in un repository pubblico può causare perdite finanziarie (uso non autorizzato di Alpaca) o violazioni di dati (Finnhub). L'audit di sicurezza è un requisito obbligatorio della Production Acceptance Checklist (DD §13.2).

### Prerequisiti
- Fase 44 completata (Docker)
- Tutti i moduli che usano API keys (News, Broker, Alerting)
- Fase 2 completata (Config)

### Input
- Tutto il codice in `src/`
- `config/settings.yaml`
- `.gitignore`
- `.env.example`
- `Dockerfile`
- `docker-compose.yml`

### Output (file creati/modificati)
- **Create:** `docs/SECURITY.md` — report di audit e policy
- **Modify:** `.gitignore` — verificare esclusioni
- **Modify:** `.env.example` — verificare placeholder
- **Modify:** `Dockerfile` — verificare nessun `.env` copiato
- Test: `tests/test_security.py` (fase 39)

### Componenti coinvolti
- Tutto il progetto (audit globale)

### Responsabilità
**Cosa FA:**
- **Audit hardcoded secrets:**
  - `grep -r "api_key\|API_KEY\|secret\|SECRET\|token\|TOKEN\|password\|PASSWORD" src/ --include="*.py"` -> nessun match in string literals
  - Verificare che TUTTE le API keys siano lette da `os.environ` o `config.py`
- **Audit `.gitignore`:**
  - `.env` presente
  - `*.key`, `*.pem`, `*.p12` presenti
  - `data/cache/`, `logs/`, `reports/` presenti
- **Audit `.env.example`:**
  - Contiene TUTTE le variabili d'ambiente necessarie con placeholder
  - Placeholder sono `your_key_here` o `change_me`, MAI valori reali
- **Audit log:**
  - `grep -r "logger\|loguru" src/ --include="*.py"` -> verificare che nessun log contenga API keys o secrets
  - Aggiungere filter a `loguru` per redarre automaticamente pattern di API keys
- **Audit Docker:**
  - `Dockerfile` non copia `.env`
  - `docker-compose.yml` usa `env_file` o `environment` (non hardcoded)
  - `.dockerignore` include `.env`
- **Audit `config/settings.yaml`:**
  - Nessun valore reale di API key
  - Placeholder o riferimenti a env vars
- **Creare `docs/SECURITY.md`:**
  - Checklist di audit con risultati
  - Policy di gestione secrets
  - Procedura di rotazione API keys
  - Contatti per incident response

**Cosa NON FA:**
- NON ruota automaticamente le API keys (operazione manuale)
- NON implementa encryption at rest (v2)
- NON esegue penetration testing

### Criteri di completamento
- [ ] `grep -r "api_key\|API_KEY\|secret" src/ --include="*.py" | grep -v "os.environ\|config\."` -> nessun output
- [ ] `.env` in `.gitignore` confermato
- [ ] `.env.example` aggiornato con tutte le variabili necessarie
- [ ] `Dockerfile` non contiene `.env` o secrets
- [ ] `config/settings.yaml` non contiene valori reali di API keys
- [ ] Log filter per secrets configurato in `logger.py`
- [ ] `docs/SECURITY.md` scritto e revisionato
- [ ] Nessun secret in `git log` (verificare con `git log -p | grep -i secret`)

### Test richiesti
- **Unit test:** `tests/test_security.py`
  - Test `assert_no_hardcoded_secrets()`: scansiona `src/` per pattern di API keys
  - Test `assert_env_in_gitignore()`: verifica `.env` in `.gitignore`
  - Test `assert_env_example_complete()`: verifica tutte le variabili in `.env.example`
  - Test `assert_no_secrets_in_config_yaml()`: verifica `settings.yaml`
  - Test `assert_logger_redacts_secrets()`: verifica che il filter loguru funzioni
  - Test `assert_dockerfile_no_env()`: verifica Dockerfile

### Dipendenze
Da questa fase dipendono: **Fase 46 (Test Suite — security test), Fase 51 (Paper Trading), Fase 52 (Production Release)**

### Rischi
- **Rischio:** Secrets già committati nella history di git
  - **Mitigazione:** Se trovati: ruotare IMMEDIATAMENTE le keys su Alpaca/Finnhub; usare `git filter-branch` o `BFG Repo-Cleaner`; documentare l'incidente in `SECURITY.md`
- **Rischio:** False negative: grep non trova secrets in formati non standard
  - **Mitigazione:** Audit manuale aggiuntivo; regex multiple per pattern diversi

### Note implementative
- Pattern grep per secrets: `(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['"][^'"\s]{8,}['"]`
- Per il log filter loguru: `logger.add(sink, filter=lambda record: not any(secret in record["message"] for secret in SECRETS_LIST))`
- `docs/SECURITY.md` template: includere data audit, risultati per categoria, azioni correttive, firmato da
- Pre-commit hook aggiuntivo: `detect-secrets` o `git-secrets` per prevenire commit di secrets

### Requisito Design Document
- Sezione 13.2 (Production Acceptance Checklist — Security)

## Fase 46: Unit & Integration Test Suite

### Titolo
Unit & Integration Test Suite

### Obiettivo
Completare la suite di test: tutti i test file (`test_signals.py`, `test_risk.py`, `test_metrics.py`, `test_backtest.py`, `test_portfolio.py`, `test_scanner.py`, `test_news_filter.py`, `test_broker.py`) con coverage > 90% unit, > 80% integration.

### Motivazione
I test sono l'ultima linea di difesa prima del paper trading e del live. La Sezione 14 del Design Document e la Production Acceptance Checklist (Sezione 13) richiedono coverage > 90% e > 80%.

### Prerequisiti
- Tutte le fasi di implementazione completate (0–29)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 14)
- Tutti i moduli del sistema

### Output (file creati/modificati)
- **Modify:** Tutti i file `tests/test_*.py` — completare i test mancanti
- **Create:** `tests/conftest.py` — fixtures comuni (mock dati, mock API, configurazione test)
- **Create:** `tests/test_integration.py` — test end-to-end su dati reali
- **Create:** `pytest.ini` o `pyproject.toml` [tool.pytest] — configurazione pytest

### Componenti coinvolti
- Tutti i file in `tests/`

### Responsabilità
**Cosa FA:**
- Completare TUTTI i test descritti nelle fasi precedenti (quelli non ancora implementati)
- `tests/conftest.py` con fixtures:
  - `sample_ohlcv_data`: DataFrame OHLCV sintetico (20 giorni, trend rialzista)
  - `sample_intraday_data`: DataFrame intraday 5min sintetico
  - `mock_finnhub_client`: mock del client Finnhub
  - `mock_alpaca_client`: mock del client Alpaca
  - `sample_config`: config dizionario con parametri di test
  - `sample_trades`: lista di trade sintetici
  - `sample_equity_curve`: equity curve sintetica
- `tests/test_integration.py`:
  - Test full pipeline: dati → scanner → signals → risk → portfolio → equity curve
  - Test backtest end-to-end su 1 mese SPY
  - Test hold-out split: OOS non usato in-sample
  - Test con dati reali limitati (1 ticker, 1 mese)
- Configurare pytest: `pytest.ini` con `--strict-markers`, `--verbose`, coverage config
- Eseguire TUTTI i test e verificare che passino

**Cosa NON FA:**
- NON implementa test di determinismo (Fase 37)
- NON implementa chaos test (Fase 38)
- NON implementa replay test (Fase 39)

### Criteri di completamento
- [ ] `pytest tests/` esegue senza errori
- [ ] Coverage unit test > 90%
- [ ] Coverage integration test > 80%
- [ ] `conftest.py` contiene fixtures per tutti i mock comuni
- [ ] `test_integration.py` copre la pipeline completa
- [ ] Nessun test skipped senza motivazione
- [ ] `pytest.ini` configurato

### Test richiesti
Questi sono i test DA SCRIVERE in questa fase (se non già scritti nelle fasi precedenti):
- [ ] `test_signals.py`: tutti gli scenari della Fase 16
- [ ] `test_risk.py`: tutti gli scenari delle Fasi 13-14
- [ ] `test_metrics.py`: tutti gli scenari della Fase 24
- [ ] `test_backtest.py`: tutti gli scenari della Fase 23
- [ ] `test_portfolio.py`: tutti gli scenari delle Fasi 15-16
- [ ] `test_scanner.py`: tutti gli scenari della Fase 15
- [ ] `test_news_filter.py`: tutti gli scenari della Fase 13
- [ ] `test_broker.py`: tutti gli scenari delle Fasi 23-25
- [ ] `test_ohlcv.py`: tutti gli scenari della Fase 8
- [ ] `test_calendar.py`: tutti gli scenari della Fase 11
- [ ] `test_regime.py`: tutti gli scenari della Fase 12
- [ ] `test_costs.py`: tutti gli scenari della Fase 21
- [ ] `test_fill_simulator.py`: tutti gli scenari della Fase 22
- [ ] `test_optimize.py`: tutti gli scenari della Fase 25
- [ ] `test_reporting.py`: tutti gli scenari della Fase 26
- [ ] `test_recovery.py`: tutti gli scenari della Fase 32
- [ ] `test_cli.py`: tutti gli scenari della Fase 33
- [ ] `test_alerting.py`: tutti gli scenari della Fase 34
- [ ] `test_eda_simple.py`: tutti gli scenari della Fase 5
- [ ] `test_eda_conditional.py`: tutti gli scenari della Fase 7
- [ ] `test_rvol.py`: tutti gli scenari della Fase 14
- [ ] `test_config.py`: tutti gli scenari della Fase 1
- [ ] `test_logger.py`: tutti gli scenari della Fase 2
- [ ] `test_performance.py`: tutti gli scenari della Fase 35

### Dipendenze
Da questa fase dipendono: **Fase 37, 32, 33 (test specializzati), Fase 40 (Paper Trading)**

### Rischi
- **Rischio:** Test passano in locale ma falliscono in CI/CD → ambiente diverso
  - **Mitigazione:** Usare path relativi; non dipendere da variabili d'ambiente globali; mockare tutte le API esterne
- **Rischio:** Coverage misurato su file sbagliati (es. include `tests/`)
  - **Mitigazione:** Configurare `--source=src` in pytest-cov

### Note implementative
- Usare `pytest-cov` per coverage: `pip install pytest-cov`
- Comando: `pytest tests/ --cov=src --cov-report=term --cov-report=html`
- Mock API esterne con `unittest.mock.patch` o `pytest-mock`
- I test NON devono chiamare API reali (Finnhub, Alpaca, yfinance) — usare mock o dati sintetici
- ECCEZIONE: `test_integration.py` può usare dati reali da `data/cache/` se disponibili

---

## Fase 47: Backtest Determinism Test

### Titolo
Backtest Determinism Test

### Obiettivo
Implementare `tests/test_determinism.py` che verifica che due esecuzioni identiche del backtest (stessi dati, stessi parametri, stesso seed) producano lo STESSO risultato bit-per-bit.

### Motivazione
La Sezione 14.2 del Design Document richiede un test di determinismo: se il backtest non è deterministico, i risultati non sono riproducibili e qualsiasi ottimizzazione è inaffidabile. Questo test è nella Production Acceptance Checklist (Sezione 13.5).

### Prerequisiti
- Fase 23 completata (Backtest Engine)
- Fase 36 completata (Test Suite)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 14.2)
- `src/backtest/engine.py`

### Output (file creati)
- **Create:** `tests/test_determinism.py`

### Componenti coinvolti
- `tests/test_determinism.py`

### Responsabilità
**Cosa FA:**
- Test `test_backtest_deterministic`:
  - Esegue `BacktestEngine.run()` due volte con:
    - Stessi ticker
    - Stesso date range
    - Stessi parametri config
    - Stesso seed
  - Confronta:
    - `equity_curve` → `pd.testing.assert_series_equal(run1.equity_curve, run2.equity_curve)`
    - `trades` → `pd.testing.assert_frame_equal(run1.trades, run2.trades)`
    - `metrics` → `assert run1.metrics == run2.metrics`
  - Se fallisce, stampa le differenze esatte
- Test `test_backtest_deterministic_different_seed`:
  - Due run con seed diversi DEVONO produrre risultati diversi (o almeno potenzialmente diversi per partial fill)
  - Verifica che il seed venga effettivamente usato
- Test `test_backtest_deterministic_with_partial_fill`:
  - Con partial fill e seed fissato, il modello probabilistico è deterministico
- Documenta i requisiti per il determinismo nel codice:
  - Tutti i RNG usano `random.Random(seed)` o `numpy.random.RandomState(seed)`
  - Nessuna dipendenza da `time.time()`, `datetime.now()`, o risorse esterne
  - Ordine di processing deterministico (ticker ordinati alfabeticamente)

**Cosa NON FA:**
- NON modifica il backtest engine (se il test fallisce, il bug è nell'engine)

### Criteri di completamento
- [ ] `test_backtest_deterministic` passa (due run identiche → stesso output)
- [ ] `test_backtest_deterministic_different_seed` passa
- [ ] `test_backtest_deterministic_with_partial_fill` passa
- [ ] Il test usa dati sintetici (non dipende da dati esterni)
- [ ] Il test è veloce (< 10 secondi)

### Test richiesti
(I test sono il deliverable stesso di questa fase)

### Dipendenze
Da questa fase dipende: **Fase 39 (Final Validation include test di determinismo)**

### Rischi
- **Rischio:** Test fallisce → backtest engine non deterministico → bug da investigare
  - **Mitigazione:** Se fallisce, verificare: RNG non seedato, ordine di processing non deterministico (es. `set` usato al posto di `list`), dipendenza da tempo di sistema
- **Rischio:** Test troppo lento (backtest su molti dati) → CI/CD timeout
  - **Mitigazione:** Usare 1 ticker, 1 mese di dati sintetici

### Note implementative
- Dati sintetici generati con seed fissato
- Usare `pd.testing.assert_series_equal(check_exact=True)` per confronto esatto
- Il seed va propagato a: `random`, `numpy.random`, e qualsiasi modulo che usa numeri casuali (partial fill, slippage)
- Se il backtest engine non è deterministico, questa fase è un blocker → risolvere PRIMA di procedere

---

## Fase 48: Chaos Engineering Tests

### Titolo
Chaos Engineering Tests

### Obiettivo
Implementare `tests/test_chaos.py` che simula scenari di failure come da Sezione 14.3 del Design Document: Finnhub down, Alpaca down, timeout, clock drift, duplicate messages, reconnect storm.

### Motivazione
Il sistema deve essere resiliente: se Finnhub è down, non deve crashare. Se Alpaca è down, deve retry e alertare. La Production Acceptance Checklist (Sezione 13.4) richiede chaos test superati.

### Prerequisiti
- Fase 13 (News Filter), Fase 27-25 (Broker), Fase 34 (Alerting)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 14.3)
- `src/data/news_filter.py`
- `src/execution/broker.py`
- `src/alerting.py`

### Output (file creati)
- **Create:** `tests/test_chaos.py`

### Componenti coinvolti
- `tests/test_chaos.py`

### Responsabilità
**Cosa FA:**
- Test `test_finnhub_offline`:
  - Mock Finnhub HTTP 503
  - Verifica: `filter_tickers` restituisce lista vuota (conservativo) o applica fallback RVOL
  - Verifica: log WARNING generato
  - Verifica: nessun crash
- Test `test_alpaca_offline`:
  - Mock Alpaca HTTP 503
  - Verifica: `submit_bracket_order` ritenta con backoff esponenziale
  - Verifica: dopo max retry, log ERROR + alert webhook
  - Verifica: nessun crash
- Test `test_alpaca_retry_idempotent`:
  - Mock Alpaca timeout → retry con stesso `client_order_id`
  - Verifica: non viene creato un ordine duplicato
- Test `test_network_latency`:
  - Aggiungere 5s delay a tutte le chiamate API
  - Verifica: timeout handling, nessun crash
  - Verifica: operazioni completano (anche se lentamente)
- Test `test_clock_drift`:
  - Alterare `datetime.now()` di +5 minuti
  - Verifica: `verify_clock_sync()` rileva drift
  - Verifica: log ERROR generato
- Test `test_api_rate_limit`:
  - 100 chiamate consecutive
  - Verifica: rate limiting rispettato (non più di X chiamate/minuto)
  - Verifica: nessun HTTP 429 non gestito
- Test `test_all_services_down`:
  - Finnhub + Alpaca entrambi down
  - Verifica: sistema non crasha
  - Verifica: alert inviato per entrambi i servizi

**Cosa NON FA:**
- NON testa scenari non elencati nella Sezione 14.3
- NON modifica il codice di produzione (solo test)

### Criteri di completamento
- [ ] `test_finnhub_offline` passa
- [ ] `test_alpaca_offline` passa
- [ ] `test_alpaca_retry_idempotent` passa
- [ ] `test_network_latency` passa
- [ ] `test_clock_drift` passa
- [ ] `test_api_rate_limit` passa
- [ ] `test_all_services_down` passa
- [ ] Tutti i test usano mock (nessuna chiamata API reale)
- [ ] Alert webhook verificato (mock HTTP 200)

### Test richiesti
(I test sono il deliverable stesso di questa fase)

### Dipendenze
Da questa fase dipende: **Fase 39 (Final Validation include chaos test)**

### Rischi
- **Rischio:** Mock non realistico → test passa ma in produzione il comportamento è diverso
  - **Mitigazione:** I mock devono restituire esattamente ciò che l'API reale restituisce in caso di errore (HTTP status, headers, body)
- **Rischio:** Test modifica lo stato globale (es. `datetime.now()`) → interferisce con altri test
  - **Mitigazione:** Usare `unittest.mock.patch` come context manager; ripristinare dopo ogni test

### Note implementative
- Usare `unittest.mock.patch` per mockare `requests.post`, `finnhub.Client`, `alpaca.trading.client.TradingClient`
- Per mockare il tempo: `unittest.mock.patch('datetime.datetime')` o libreria `freezegun`
- I test chaos devono essere indipendenti (non condividere stato)
- Eseguire i test chaos in una CI pipeline separata (sono più lenti)

---

## Fase 49: Data Replay Test

### Titolo
Data Replay Test

### Obiettivo
Implementare `tests/test_replay.py` che registra una giornata di dati e la rigioca nel backtest engine, verificando che i segnali siano identici a quelli generati live.

### Motivazione
La Sezione 14.4 del Design Document descrive il replay testing come tecnica per debuggare discrepanze backtest-vs-live. Questo test è nella Production Acceptance Checklist (Sezione 13.4).

### Prerequisiti
- Fase 23 completata (Backtest Engine)
- Fase 36 completata (Test Suite)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 14.4)
- `src/backtest/engine.py`

### Output (file creati)
- **Create:** `tests/test_replay.py`
- **Create:** `scripts/record_day.py` — script per registrare una giornata di dati

### Componenti coinvolti
- `tests/test_replay.py`
- `scripts/record_day.py`

### Responsabilità
**Cosa FA:**
- Script `scripts/record_day.py`:
  - Scarica dati intraday 5min per un giorno specifico da Polygon/Alpaca
  - Salva in `data/replay/{date}.parquet`
  - Registra anche VIX, news filter results, scanner output
- Test `test_replay_consistent`:
  - Carica un file di replay registrato
  - Esegue backtest engine su quel singolo giorno
  - Esegue `signals.generate_signals` sullo stesso DataFrame
  - Verifica: segnali identici (stesso numero, stesse barre)
- Test `test_replay_vs_backtest`:
  - Esegue backtest normale su un ticker per 1 mese
  - Per ogni giorno, isola i dati intraday
  - Rigioca ogni giorno separatamente
  - Verifica: il P&L totale del backtest = somma dei P&L dei replay giornalieri
- Test `test_replay_recovery`:
  - Simula crash a metà giornata
  - Esegue recovery
  - Verifica: il replay dal punto di recovery produce gli stessi segnali finali

**Cosa NON FA:**
- NON richiede dati reali per funzionare (usa dati sintetici per i test unit)
- NON modifica il backtest engine

### Criteri di completamento
- [ ] `scripts/record_day.py` eseguibile e funzionante
- [ ] `test_replay_consistent` passa con dati sintetici
- [ ] `test_replay_vs_backtest` passa (backtest = somma replay)
- [ ] `test_replay_recovery` passa
- [ ] I file di replay sono in formato Parquet
- [ ] La directory `data/replay/` è nel `.gitignore`

### Test richiesti
(I test sono il deliverable stesso di questa fase)

### Dipendenze
Da questa fase dipende: **Fase 40 (Paper Trading)**

### Rischi
- **Rischio:** Dati di replay non disponibili per date storiche
  - **Mitigazione:** Generare dati sintetici per i test; usare dati reali solo per validazione manuale
- **Rischio:** Replay non identico a causa di differenze nei dati (es. yfinance vs Polygon)
  - **Mitigazione:** Il test di replay usa gli STESSI dati, non dati da fonti diverse

### Note implementative
- Formato file replay: Parquet con colonne `timestamp, open, high, low, close, volume, ticker`
- Includere metadati: `date, tickers, vix, news_filter_results`
- Il replay test è particolarmente utile durante il paper trading (Fase 40) per debuggare discrepanze

---

## Fase 50: Kill Switch & Circuit Breaker

### Titolo
Kill Switch & Circuit Breaker

### Obiettivo
Implementare `src/execution/kill_switch.py` con meccanismi di arresto automatico e manuale della strategia.

### Motivazione
Un kill switch è l'ultima linea di difesa contro perdite catastrofiche. Senza di esso, un bug nel codice o un evento di mercato estremo possono erodere l'intero capitale prima che un operatore umano possa intervenire.

### Prerequisiti
- Fase 27 completata (Broker)
- Fase 2 completata (Logger)
- Fase 1 completata (Config)

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 10, 13.2)
- `src/config.py`
- `src/logger.py`

### Output (file creati/modificati)
- **Create:** `src/execution/kill_switch.py`
- Test: `tests/test_kill_switch.py`

### Componenti coinvolti
- `src/execution/kill_switch.py`

### Responsabilità
**Cosa FA:**
- Classe `KillSwitch`:
  - `__init__(config)`: inizializza con soglie da config
  - `check_max_drawdown(equity_curve: pd.Series) -> bool`: True se max drawdown > 25%
  - `check_consecutive_rejections(recent_orders: list[dict], threshold: int = 3) -> bool`: True se N ordini rifiutati consecutivi
  - `check_clock_drift(max_drift_seconds: float = 1.0) -> bool`: True se clock drift > 1 secondo
  - `check_manual_override() -> bool`: True se pulsante manuale attivato (file flag o env var)
  - `is_killed() -> bool`: verifica tutte le condizioni
  - `trigger_shutdown(reason: str)`: arresta il sistema:
    - Cancella tutti gli ordini pendenti su Alpaca
    - Chiude tutte le posizioni aperte a mercato
    - Invia alert (Discord/Slack) con reason
    - Scrive `KILL_SWITCH_ACTIVE` flag file
    - Logga CRITICAL con tutti i dettagli
- Funzione `emergency_liquidate(broker, positions) -> list[dict]`: chiude TUTTE le posizioni a mercato
- Funzione `send_shutdown_alert(reason, stats)`: invia alert via webhook
- Meccanismo manuale: file flag `config/kill_switch.flag` o env var `KILL_SWITCH=true`

**Cosa NON FA:**
- NON implementa il monitoraggio in tempo reale (Fase 40)
- NON sostituisce il controllo max drawdown già in Fase 40 (lo complementa con un enforcement esplicito)

### Criteri di completamento
- [ ] `KillSwitch.is_killed()` restituisce True quando max drawdown > 25%
- [ ] `KillSwitch.is_killed()` restituisce True dopo 3 ordini rifiutati consecutivi
- [ ] `KillSwitch.is_killed()` restituisce True quando clock drift > 1 secondo
- [ ] `KillSwitch.is_killed()` restituisce True quando file flag esiste
- [ ] `trigger_shutdown()` cancella ordini e chiude posizioni
- [ ] Alert inviato via webhook con motivo dello shutdown
- [ ] `KillSwitch` in stato normale → `is_killed()` False

### Test richiesti
- **Unit test:** `tests/test_kill_switch.py`
  - Test max drawdown kill: equity con -30% → killed
  - Test max drawdown safe: equity con -10% → not killed
  - Test consecutive rejections: 3 rifiuti → killed
  - Test consecutive rejections reset: 2 rifiuti + 1 successo → not killed
  - Test clock drift: drift 2s → killed
  - Test manual override: file flag presente → killed
  - Test `trigger_shutdown()`: verifica stato post-shutdown
  - Test `emergency_liquidate()`: tutte le posizioni chiuse

### Dipendenze
Da questa fase dipendono: **Fase 40 (Paper Trading), Fase 52 (Production Release)**

### Rischi
- **Rischio:** False positive: kill switch attivato da drift di clock innocuo
  - **Mitigazione:** Soglia di 1 secondo; se drift è ricorrente, investigare causa (NTP sync, VM clock)
- **Rischio:** Kill switch non si attiva quando dovrebbe (bug nella condizione)
  - **Mitigazione:** Test esaustivi; loggare TUTTI i check a livello DEBUG per post-mortem

### Note implementative
- Il kill switch va eseguito PRIMA di ogni operazione di trading
- `is_killed()` deve essere chiamato all'inizio di ogni ciclo principale
- Il file flag `config/kill_switch.flag` permette shutdown anche senza processo Python running
- Usare `loguru.logger.critical()` per gli eventi di shutdown
- Aggiungere sezione `kill_switch` in `config/settings.yaml`:
  ```yaml
  kill_switch:
    max_drawdown_pct: 0.25
    max_consecutive_rejections: 3
    max_clock_drift_seconds: 1.0
  ```

### Requisito Design Document
- Sezione 10 (Monitoring & Alerting), Sezione 13.2 (Production Acceptance Checklist)

---


# MACRO FASE 9: PRODUCTION READINESS

---

## Fase 51: Paper Trading Deployment

### Titolo
Paper Trading Deployment

### Obiettivo
Eseguire la strategia in paper trading su Alpaca per almeno 30-60 giorni, monitorare metriche, verificare slippage reale, fill rate, e assenza di bug.

### Motivazione
La Sezione 9.1 e la Production Acceptance Checklist (Sezione 13.2) richiedono paper trading obbligatorio prima del live. È l'ultimo gate prima di mettere capitale reale a rischio.

### Prerequisiti
- Fase 0–33 completate (tutto il sistema)
- Fase 36 completata (test suite passa)
- Account Alpaca con paper trading abilitato
- Finnhub API key configurata

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezioni 9.1, 13.2)
- Tutto il sistema
- Alpaca paper API keys

### Output (file creati)
- **Create:** `scripts/run_paper_trading.py` — script di avvio paper trading
- **Create:** `reports/paper_trading_daily.csv` — log giornaliero paper
- **Create:** `reports/paper_trading_summary.md` — report finale paper

### Componenti coinvolti
- Tutto il sistema in modalità paper

### Responsabilità
**Cosa FA:**
- Script `run_paper_trading.py`:
  - Avvia il loop giornaliero (08:00–16:00 EST)
  - Esegue la pipeline completa: news filter → scanner → signals → risk → portfolio → broker (paper)
  - Logga ogni trade con tutti i dettagli
  - Invia daily summary alle 16:30 EST
  - Salva report giornaliero in `reports/paper_trading_daily.csv`
- Monitoraggio continuo:
  - Max drawdown: se supera il 25%, STOP automatico + alert
  - Fill rate: % ordini eseguiti vs inviati (target > 80%)
  - Slippage reale vs slippage modellato (confronto)
  - Metriche daily: P&L, Win Rate, N trades
- Report finale dopo 30-60 giorni:
  - Confronto metriche paper vs backtest OOS
  - Analisi slippage reale
  - Lista bug/issues trovati
  - Raccomandazione: procedere al live / ritardare / modificare parametri

**Cosa NON FA:**
- NON esegue trading con capitale reale
- NON modifica parametri automaticamente
- NON sostituisce il giudizio umano sulla decisione go/no-go

### Criteri di completamento
- [ ] Paper trading eseguito per almeno 30 giorni di mercato
- [ ] `reports/paper_trading_daily.csv` popolato per ogni giorno
- [ ] Max drawdown durante il paper ≤ 25%
- [ ] Fill rate ≥ 80%
- [ ] Slippage reale misurato e documentato
- [ ] Nessun ordine duplicato (idempotenza funzionante)
- [ ] Recovery testato almeno una volta (kill e restart)
- [ ] `reports/paper_trading_summary.md` scritto con analisi completa
- [ ] Decisione go/no-go documentata
- [ ] Smoke test: verifica che il processo non crashi dopo 1 ora di esecuzione continua in paper trading mode
- [ ] Smoke test: verifica che il processo non crashi dopo 1 ora di esecuzione continua in paper trading mode

### Test richiesti
Nessun test automatico in questa fase (validazione manuale/osservazionale)

### Dipendenze
Da questa fase dipende: **Fase 52: Production Release**

### Rischi
- **Rischio:** Paper trading non rappresentativo del live (es. fill rate diverso, slippage diverso)
  - **Mitigazione:** Alpaca paper simula execution realisticamente; differenze documentate nel report finale
- **Rischio:** Periodo di paper troppo breve (30 giorni possono essere un regime di mercato atipico)
  - **Mitigazione:** Obiettivo minimo 30 giorni, raccomandato 60 giorni; estendere se il periodo è atipico
- **Rischio:** Bug scoperto durante il paper → stop e fix
  - **Mitigazione:** Questo è lo scopo del paper trading; ogni bug trovato è un successo (evitato in live)

### Note implementative
- Il paper trading usa ESATTAMENTE lo stesso codice del live, solo con URL endpoint diverso
- Configurare `paper_trading: true` e `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- Eseguire in un ambiente separato (es. VPS, Raspberry Pi, server dedicato) per testare affidabilità 24/7
- Configurare monitoring esterno (es. healthchecks.io) per rilevare crash del processo

---

# FINAL: Production Release

## Fase 52: Production Release

### Titolo
Production Release

### Obiettivo
Rilasciare la strategia in produzione con capitale reale, dopo aver superato TUTTI i checkpoint della Production Acceptance Checklist (Sezione 13 del Design Document).

### Motivazione
Questo è l'obiettivo finale del progetto: trading algoritmico live con capitale reale.

### Prerequisiti
- Fase 40 completata con successo (paper trading validato)
- TUTTI i checkpoint della Sezione 13 verificati
- Decisione go/no-go positiva

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 13: Production Acceptance Checklist)
- Report paper trading
- Tutti i test superati

### Output
- Sistema in esecuzione live su Alpaca
- Monitoring attivo (webhook alerting)
- Documentazione finale

### Componenti coinvolti
- Tutto il sistema in modalità live

### Responsabilità
**Cosa FA:**
- Verificare TUTTI i 24 checkpoint della Sezione 13:
  - **13.1 Edge Validation (6 checkpoint):** EDA, expectancy condizionale, Monte Carlo, bootstrap, WFA/rolling, plateau detection
  - **13.2 Paper Trading (6 checkpoint):** 30-60 giorni, max DD < 25%, slippage misurato, fill rate > 80%, no duplicati, riconciliazione testata
  - **13.3 Monitoring & Alerting (4 checkpoint):** webhook configurato, daily summary, alert automatici, audit trail
  - **13.4 Resilience (6 checkpoint):** recovery testato, failover testato, Finnhub down → fallback, API stress test, chaos test superati, replay test superati
  - **13.5 Code Quality (6 checkpoint):** test coverage > 90%/80%, backtest deterministico, no bug critici, type hints, performance benchmark
  - **13.6 Security (5 checkpoint):** API keys in .env, .env.example aggiornato, no keys hardcodate, rate limiting, paper/live separati
- Switch a endpoint live: `ALPACA_BASE_URL=https://api.alpaca.markets`
- Avviare con capitale reale (iniziare con capitale minimo, aumentare gradualmente)
- Monitoring intensivo prime 2 settimane
- Loggare ogni dettaglio per audit

**Cosa NON FA:**
- NON modifica parametri senza validazione
- NON esegue con capitale che non ci si può permettere di perdere

### Criteri di completamento
- [ ] TUTTI i 24 checkpoint della Sezione 13 spuntati
- [ ] Sistema live funzionante
- [ ] Primo trade eseguito con successo
- [ ] Monitoring confermato funzionante
- [ ] Daily summary ricevuto
- [ ] `README.md` aggiornato con istruzioni production
- [ ] Tag Git creato: `v1.0.0-production`

### Test richiesti
Nessun test automatico (già tutti superati nelle fasi precedenti)

### Dipendenze
Nessuna (fase terminale)

### Rischi
- **Rischio:** Emotività: il trading live è psicologicamente diverso dal backtest/paper
  - **Mitigazione:** Fidarsi del sistema; non intervenire manualmente; se si interviene, documentare e analizzare
- **Rischio:** Regime change: la strategia smette di funzionare
  - **Mitigazione:** Monitoring continuo; kill switch se max DD > 25% o Sharpe rolling < 0 per 3 mesi
- **Rischio:** Costi nascosti (API fees, data fees, margin interest)
  - **Mitigazione:** Verificare tutti i costi Alpaca prima del live; includerli nel P&L

### Note implementative
- Iniziare con capitale ridotto (es. $5,000) e aumentare solo dopo 3 mesi di performance coerenti
- Tenere un diario di trading separato per annotare osservazioni qualitative
- NON modificare il codice in produzione senza ripetere paper trading
- Ogni modifica ai parametri richiede un mini-backtest e validazione OOS

---

---

## Riepilogo Dipendenze tra le Fasi

```
Fase 0 (Setup)
  └▶ Fase 1 (Config)
       └▶ Fase 2 (Logger)
            └▶ Fase 4 (EDA Download)
                 └▶ Fase 5 (EDA Simple) ──▶ Fase 7 (EDA Gate)
                                                │
                           ┌────────────────────┘
                           ▼
                      Fase 8 (OHLCV) ◀── Fase 1
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Fase 11      Fase 12       Fase 13 (News)
       (Calendar)   (Regime)         │
              │            │         ▼
              │            │    Fase 14 (RVOL)
              │            │         │
              └────────────┼─────────┘
                           ▼
                      Fase 15 (Scanner)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Fase 16      Fase 17      Fase 21
        (Signals)     (Risk)       (Costs)
              │            │            │
              │            ▼            │
              │       Fase 18          │
              │    (Vol Scaling)       │
              │            │            │
              └────────────┼────────────┘
                           ▼
                      Fase 19 (Portfolio)
                           │
                           ▼
                      Fase 20 (Constraints)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Fase 22      Fase 23      Fase 27
      (Fill Sim)    (Backtest)    (Broker)
              │            │            │
              └────────────┘            ▼
                           │       Fase 30 (Orders)
                           ▼            │
                      Fase 24      Fase 31 (Idempotency)
                     (Metrics)          │
                           │            ▼
                      Fase 25      Fase 32 (Recovery)
                    (Optimize)
                           │
                      Fase 26
                    (Reporting)

Fase 33 (CLI) ── dipende da 23, 25, 15, 26
Fase 34 (Alerting) ── dipende da 2
Fase 35 (Performance) ── dipende da 8, 12, 16, 23

Fase 36 (Test Suite) ── dipende da tutte le fasi 0-35
Fase 37 (Determinism) ── dipende da 23, 36
Fase 38 (Chaos) ── dipende da 13, 27, 34
Fase 39 (Replay) ── dipende da 23, 36

Fase 40 (Paper Trading) ── dipende da 0-39
Fase 52 (Production) ── dipende da 40
```

---

*Documento generato il 2026-07-09. Versione Roadmap 1.0.*
*Basato su Design Document v2.0 (`docs/specs/2026-07-09-gap-mean-reversion-design.md`).*

---

## Fase 53: Performance Optimization — Polars/DuckDB Migration (Post-Production)

> **⚠️ FASE POST-PRODUCTION — OPZIONALE, NON BLOCCANTE PER IL RILASCIO**
> Questa fase è stata spostata qui dalla posizione originale (ex-Fase 35) per evitare regressioni prima dei test di accettazione.

### Titolo
Polars/DuckDB Performance Migration (Post-Production)

### Obiettivo
Migrare le operazioni critiche (calcolo indicatori, join, aggregazioni) da Pandas a Polars/DuckDB come da Sezione 12 del Design Document.

### Motivazione
Pandas è efficace fino a ~10M barre. Per backtest multi-anno su 500 ticker servono performance superiori. Polars offre 10-100x speedup su operazioni vettorizzate. **Tuttavia, questa migrazione è opzionale e non deve ritardare il rilascio.**

### Prerequisiti
- **Fase 52 completata (sistema in produzione)**
- Backtest stabile su Pandas

### Input
- `docs/specs/2026-07-09-gap-mean-reversion-design.md` (Sezione 12)
- Moduli: `ohlcv.py`, `scanner.py`, `signals.py`, `backtest/engine.py`

### Output (file modificati)
- **Modify:** `src/data/ohlcv.py` — supporto backend Polars (con fallback Pandas)
- **Modify:** `src/data/scanner.py` — indicatori in Polars
- **Modify:** `src/strategy/signals.py` — calcoli segnali in Polars
- **Modify:** `src/backtest/engine.py` — loop con Polars DataFrame
- **Create:** `tests/test_performance.py` — benchmark comparativi
- Test: `tests/test_performance.py`

### Componenti coinvolti
- `src/data/ohlcv.py`, `src/data/scanner.py`, `src/strategy/signals.py`, `src/backtest/engine.py`

### Responsabilità
**Cosa FA:**
- Implementare conversioni Pandas ↔ Polars nei moduli critici
- Riscrivere calcoli indicatori (SMA, ATR, ADX) in Polars
- Usare DuckDB per join tra timeframe (daily + intraday)
- Benchmark comparativi: Pandas vs Polars su dataset 10 anni × 500 ticker
- Mantenere il backend Pandas come fallback (parametro `backend="pandas"`)

**Cosa NON FA:**
- NON riscrive l'intero sistema in Polars
- NON rimuove il supporto Pandas
- NON modifica le API pubbliche dei moduli

### Criteri di completamento
- [ ] Speedup ≥ 5x nello scanner su 500 ticker
- [ ] Risultati identici tra Pandas e Polars per `generate_signals()`
- [ ] DuckDB query per join daily/intraday < 100ms
- [ ] Test esistenti passano con entrambi i backend
- [ ] Benchmark documentato in `reports/performance_benchmark.csv`

### Test richiesti
- **Performance test:** `tests/test_performance.py`
  - Test speedup scanner: Polars vs Pandas su 500 ticker
  - Test equivalenza segnali: output identico
  - Test benchmark DuckDB join
  - Test fallback Pandas quando Polars non disponibile

### Dipendenze
Nessuna (fase post-production, indipendente)

### Rischi
- **Rischio:** Differenze API Polars vs Pandas → risultati diversi
  - **Mitigazione:** Test di equivalenza esaustivi; usare Polars solo dove si misura un vantaggio
- **Rischio:** Aumento complessità per doppio backend
  - **Mitigazione:** Accettabile come trade-off; il backend Pandas rimane il default

### Note implementative
- Conversione: `pl.from_pandas(df)` e `df.to_pandas()`
- SMA: `pl.col("close").rolling_mean(200)`
- DuckDB: `import duckdb; duckdb.sql("SELECT ... FROM df1 JOIN df2 ON ...")`
- Salvare benchmark in Parquet per confronto storico

### Requisito Design Document
- Sezione 12 (Performance & Scalability Stack)

---


---


---

# Grafo delle Dipendenze (Versione 5.1)

Il grafo seguente mostra le dipendenze tra le fasi. Le frecce indicano "dipende da".
Le fasi senza dipendenze possono essere eseguite in parallelo.

```
Fase 0 (Project Setup)
 +-> Fase 1 (Dependency Lock)
      +-> Fase 2 (Config)
           +-> Fase 4 (Logger)
           |    +-> Fase 5 (EDA Download)
           |         +-> Fase 7 (EDA Simple)
           |         |    +-> Fase 8 (EDA Conditional) [GATE: se Sharpe < 0.5 -> STOP]
           |         +-> Fase 11 (OHLCV Cache)
           |              +-> Fase 12 (Data Quality) --- dipende da Fase 11 e Fase 13
           |              |    +-> Fase 17 (Scanner)
           |              +-> Fase 14 (Regime)
           |              |    +-> Fase 17 (Scanner)
           |              +-> Fase 16 (RVOL)
           |                   +-> Fase 17 (Scanner)
           +-> Fase 13 (Calendar)
           |    +-> Fase 12 (Data Quality)
           |    +-> Fase 17 (Scanner)
           |    +-> Fase 25 (Backtest Core)
           |    +-> Fase 35 (Broker)
           +-> Fase 15 (News Filter)
                +-> Fase 17 (Scanner)

Fase 17 (Scanner)
 +-> Fase 18 (Signals)
      +-> Fase 19 (Risk Base)
      |    +-> Fase 20 (Risk Vol Scaling)
      |    |    +-> Fase 21 (Portfolio SM)
      |    +-> Fase 21 (Portfolio SM)
      +-> Fase 21 (Portfolio SM)
      |    +-> Fase 22 (Portfolio Sector)
      +-> Fase 25 (Backtest Core)

Fase 19 (Risk Base)
 +-> Fase 23 (Costs)
      +-> Fase 24 (Fill Simulator)
      |    +-> Fase 25 (Backtest Core)
      +-> Fase 25 (Backtest Core)

Fase 25 (Backtest Core) --- dipende da 21/23/24/25
 +-> Fase 26 (Backtest Integration) --- dipende da 25/23/24/21
 |    +-> Fase 27 (Backtest Validation) --- dipende da 26
 +-> Fase 30 (Metrics)
      +-> Fase 31 (Optimization)
           +-> Fase 32 (Reporting)

Fase 32 (Reporting)
 +-> Fase 33 (API Docs Generator)
 +-> Fase 34 (Data Retention)

Fase 35 (Broker Base)
 +-> Fase 36 (Bracket Orders)
 |    +-> Fase 37 (Idempotency)
 |         +-> Fase 38 (State Recovery)
 +-> Fase 39 (Central CLI)

Fase 40 (Alerting)
 +-> Fase 41 (Health Check) [NEW]

Fase 42 (Pre-commit Hooks)
 +-> Fase 43 (CI/CD Workflow)
      +-> Fase 44 (Docker)
           +-> Fase 45 (Secrets Audit) [NEW]

Fase 46 (Test Suite) --- dipende da 33/34/38/41/45
 +-> Fase 47 (Backtest Determinism)
      +-> Fase 48 (Chaos Engineering)
           +-> Fase 49 (Data Replay)
                +-> Fase 50 (Kill Switch)

Fase 51 (Paper Trading) --- dipende da TUTTE le fasi 0–50
 +-> Fase 52 (Production Release) --- dipende da 51
      +-> Fase 53 (Performance Migration) [POST-PRODUCTION, OPZIONALE]
```

## Dipendenze Dettagliate per Riferimento Incrociato

| Fase | Titolo | Dipende da | Richiesta da |
|---|---|---|---|
| 0 | Project Setup | — | 1, 2, 4, 5, 11 |
| 1 | Dependency Lock | 0 | 2 |
| 2 | Config | 0, 1 | 4, 13, 15, 17, 18, 19, 23, 25 |
| 3 | Logger | 0, 2 | 5, 7, 8, 11, 13, 15, 17, 21, 23, 30, 35, 40 |
| 4 | EDA Download | 0, 3 | 7, 8 |
| 5 | EDA Simple | 4 | 8 |
| 6 | EDA Conditional [GATE] | 4, 5 | TUTTE (se gate NO -> STOP) |
| 7 | OHLCV Cache | 0, 2, 3 | 14, 17, 25 |
| 8 | Data Quality | 7, 9 | 17 |
| 9 | Calendar | 0, 2, 3 | 12, 17, 25, 35 |
| 10 | Regime | 2, 3, 7 | 17, 25 |
| 11 | News Filter | 2, 3 | 17 |
| 12 | RVOL | 2, 7 | 17 |
| 13 | Scanner | 7, 8, 9, 10, 11, 12 | 18, 21, 25 |
| 14 | Signals | 2, 3 | 19, 21, 25 |
| 15 | Risk Base | 2, 14 | 20, 21, 23, 25 |
| 16 | Risk Vol Scaling | 15 | 21 |
| 17 | Portfolio SM | 2, 3, 15 | 22, 25, 35, 38 |
| 18 | Portfolio Sector | 7, 17 | 25 |
| 19 | Costs | 15 | 24, 25, 26 |
| 20 | Fill Simulator | 19 | 25, 26 |
| 21 | Backtest Core | 7, 9, 10, 13, 14, 15, 17, 18, 19, 20 | 26, 30, 47 |
| 22 | Backtest Integration | 17, 19, 20, 21 | 27 |
| 23 | Backtest Validation | 22 | 31 |
| 24 | Metrics | 21 | 31, 32 |
| 25 | Optimization | 21, 23, 24 | 32 |
| 26 | Reporting | 24, 25 | 33, 34 |
| 27 | API Docs [NEW] | 26 | 46 |
| 28 | Data Retention [NEW] | 3, 7, 9, 26 | 46 |
| 29 | Broker Base | 2, 9, 17 | 36, 39, 41 |
| 30 | Bracket Orders | 29 | 37 |
| 31 | Idempotency | 30 | 38 |
| 32 | State Recovery | 17, 31 | 39, 46 |
| 33 | Central CLI | 29, 32 | 51 |
| 34 | Alerting | 2, 3, 29 | 41, 51 |
| 35 | Health Check [NEW] | 2, 3, 29, 34 | 46, 51 |
| 36 | Pre-commit Hooks | 1, 2 | 43 |
| 37 | CI/CD | 36, 40 | 44 |
| 38 | Docker | 37 | 45 |
| 39 | Secrets Audit [NEW] | 38 | 46, 51 |
| 40 | Test Suite | 27, 28, 32, 35, 39 | 43, 47 |
| 41 | Backtest Determinism | 21, 40 | 48 |
| 42 | Chaos Engineering | 41 | 49 |
| 43 | Data Replay | 42 | 50, 51 |
| 44 | Kill Switch | 2, 3, 29, 43 | 51, 52 |
| 45 | Paper Trading | 0–44 (TUTTE) | 52 |
| 46 | Production Release | 45 | — |
| 47 | Performance Migration | 46 (opzionale) | — |

---


# Decision Log

Registro delle decisioni architetturali significative prese durante lo sviluppo della roadmap.

| Data | Decisione | Motivazione | Impatto |
|---|---|---|---|
| 2026-07-09 | **Fix v5.0 -> v5.1: Unificazione numerazione e riferimenti incrociati** | La v5.0 aveva headers corretti (0-53) ma i riferimenti incrociati nel testo usavano ancora la vecchia numerazione v4.0, causando ambiguita critica per l'agente AI. | Tutti i riferimenti "Fase X" nel testo corretti per matchare gli headers 0-53. Rimossi riferimenti a "Fase 19a/b/c", "Fase 7.5a/b/c", "Fase Final". Aggiunta nota dati premium e fix dipendenza circolare CI/CD/Test Suite. |
| 2026-07-09 | **Data Provider Abstraction Layer** | yfinance insufficiente per backtest intraday. Interfaccia comune per switch tra Yahoo/Alpaca/Polygon. | Nuova Fase nel Data Layer. Scanner/strategy/backtester disaccoppiati dalla fonte dati. |
| 2026-07-09 | **Historical Universe Reconstruction** | Survivorship bias: S&P 500 corrente per backtest 2014-2024 gonfia performance. Universe storico include delisted/falliti. | Nuova Fase dopo EDA Download. 600+ ticker unici invece di 500. Backtest su universe puntuale. |
| 2026-07-09 | **Walk Forward Analysis** | Hold-out 70/30 non basta. Walk forward Train/Val/Test simula processo reale. | Nuova Fase dopo BT Validation. 3 periodi: 2014-2018, 2019-2021, 2022-2024. Test set toccato UNA volta. |
| 2026-07-09 | **Monte Carlo Simulation Engine** | Backtest deterministico = UNA realizzazione. 10,000 simulazioni per robustness reale. | Nuova Fase dopo Walk Forward. Probability of Ruin, worst-case, slippage sensitivity. |
| 2026-07-09 | **Feature Selection & Robustness** | Ogni filtro deve dimostrare miglioramento statisticamente significativo o viene rimosso. | Nuova Fase dopo EDA Conditional. Bootstrap CI per delta Sharpe. Filtri non significativi -> REMOVE. |
| 2026-07-09 | **Strategy Versioning & Experiment Tracking** | Parametri senza versioning = risultati non riproducibili. Experiment tracking lega ogni run a config immutabile. | Nuova Fase dopo Config. v1.yaml immutabile. Experiment ID + dataset hash + param snapshot. |
| 2026-07-09 | **Spostamento Performance Migration (Polars/DuckDB) a Post-Production (Fase 53)** | La migrazione Pandas->Polars introduce regressioni potenziali. Ritardarla al post-rilascio evita di bloccare i test di accettazione. La strategia è già validata su Pandas; le performance sono accettabili per la v1. | Fase opzionale, non bloccante. Il sistema va in produzione con stack Pandas. La migrazione è un upgrade di performance post-rilascio. |
| 2026-07-09 | **Decomposizione Backtest Engine in 3 sotto-fasi (Fase 25, 22, 23)** | La Fase 23 originale era troppo complessa per un'agente AI: integrava loop, costi, fill simulator, e portfolio in un'unica fase. La decomposizione in Core->Integration->Validation permette un'implementazione incrementale con test a ogni step. | 3 fasi atomiche invece di 1 monolitica. Ogni fase è indipendentemente testabile. Il validation gate (Fase 27) blocca l'ottimizzazione se il backtest non è deterministico. |
| 2026-07-09 | **Aggiunta Data Quality Validation (Fase 12)** | Dati di scarsa qualità (gap, outlier, timezone errate) producono backtest inaffidabili. La validazione esplicita dei dati prima dello scanner previene errori silenziosi. | Ogni ticker viene validato prima di entrare nella pipeline. Ticker con dati corrotti vengono flaggati ed esclusi. Il report di qualità è input per decisioni manuali (riscaricare o escludere). |
| 2026-07-09 | **Aggiunta Kill Switch & Circuit Breaker (Fase 50)** | Un bug nel codice o un evento di mercato estremo possono causare perdite superiori al 25% prima che un operatore intervenga. Il kill switch automatico è l'ultima linea di difesa. | Shutdown automatico su: max drawdown > 25%, 3 ordini rifiutati consecutivi, clock drift > 1s, pulsante manuale. Il kill switch è testato nel paper trading prima del live. |
| 2026-07-09 | **Aggiunta Macro Fase DevOps & CI/CD (Fasi 36-38)** | Code quality enforcement (pre-commit), CI/CD pipeline (GitHub Actions), e containerizzazione (Docker) sono best practice che riducono bug in produzione e semplificano il deployment. | Lint e type checking automatici a ogni commit. Test eseguiti a ogni push e PR. Deployment containerizzato riproducibile. |
| 2026-07-09 | **Aggiunta API Documentation Generator (Fase 33)** | Un sistema con 15+ moduli richiede documentazione API per debugging e onboarding. Senza docstring standardizzate, ogni modifica richiede reverse-engineering. | Docstring obbligatorie per ogni funzione pubblica con riferimento al Design Document. Documentazione generata automaticamente e integrata in CI/CD. |
| 2026-07-09 | **Aggiunta Data Retention & Archiving (Fase 34)** | Log, cache, e report crescono indefinitamente. La retention automatica previene saturazione del disco e mantiene il sistema gestibile. | Cleanup automatico di log (>30gg), cache (>90gg), archiviazione report mensile, trade log append-only, checkpoint settimanali. |
| 2026-07-09 | **Aggiunta Health Check & Heartbeat (Fase 41)** | In produzione, è critico sapere se il sistema è vivo. Un heartbeat mancante indica un crash silenzioso che potrebbe lasciare posizioni aperte senza monitoring. | Health check JSON con stato broker, API keys, disco, memoria. Heartbeat ogni 5 minuti. Alert se heartbeat mancante > 10 minuti. |
| 2026-07-09 | **Aggiunta Secrets Management & Security Audit (Fase 45)** | Una API key committata è un rischio finanziario e di sicurezza. L'audit è obbligatorio prima del live (DD §13.2). | Audit automatico di tutti i file per secrets hardcodati. Verifica `.gitignore`, `.env.example`, Dockerfile, log. Report di sicurezza documentato. |
| 2026-07-09 | **Rinumerazione continua 0->47** | La numerazione precedente usava decimali (0.5, 6.5, 33.5) e lettere (7.5a, 19a, 19b, 19c) che rendono ambiguo l'ordine di esecuzione per un agente AI. La numerazione continua elimina ogni ambiguità. | 48 fasi numerate 0->47. Ogni numero corrisponde a esattamente una fase. Ordine di esecuzione deterministico. |

---


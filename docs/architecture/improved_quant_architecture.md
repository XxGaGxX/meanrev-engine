# Gap Mean Reversion — Improved Quant Architecture v5.0

**Data:** 2026-07-09
**Baseline:** Roadmap v4.0 → Upgrade v5.0
**Scopo:** Documentare l'architettura migliorata con data provider abstraction, event-driven backtest, e validazione quantitativa professionale

---

## 1. Panoramica dell'Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION LAYER                       │
│  config/settings.yaml  │  config/strategies/v1.yaml, v2.yaml    │
│  Strategy Versioning   │  Experiment Tracking                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER (Improved)                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          Data Provider Abstraction Layer                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ Yahoo    │  │ Alpaca   │  │ Polygon  │               │   │
│  │  │ (EDA)    │  │ (Backtest│  │ (Premium)│               │   │
│  │  │          │  │  Paper)  │  │          │               │   │
│  │  └──────────┘  └──────────┘  └──────────┘               │   │
│  │         │             │             │                     │   │
│  │         └─────────────┼─────────────┘                     │   │
│  │                       ▼                                   │   │
│  │              MarketDataProvider                           │   │
│  │         (Interface: get_daily, get_intraday,             │   │
│  │          get_pre_market, get_universe)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                │                                  │
│  ┌─────────────────────────────┼──────────────────────────────┐  │
│  │    Historical Universe     │    OHLCV Cache Pipeline       │  │
│  │    Reconstruction          │    (Parquet, versioned)       │  │
│  │    (SP500 2014-2024)       │                               │  │
│  └─────────────────────────────┴──────────────────────────────┘  │
│                                │                                  │
│  ┌─────────────────────────────┼──────────────────────────────┐  │
│  │  Data Quality    │  Calendar  │  Regime   │  News/RVOL    │  │
│  │  Validation      │            │  Classifier│  Filter       │  │
│  └─────────────────────────────┴──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PRE-MARKET PIPELINE                         │
│                                                                  │
│  Scanner → Watchlist (gap%, VIX, ADX, 200EMA, RVOL, regime)     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       STRATEGY CORE                              │
│                                                                  │
│  Signal Generator → Risk Manager → Portfolio Manager            │
│  (LONG/SHORT)      (1% risk,     (State Machine,                │
│                     ATR scaling)   Sector/Correlation            │
│                                    Constraints)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                 BACKTESTING SUITE (Event-Driven v5.0)            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Event-Driven Backtest Engine                │    │
│  │                                                          │    │
│  │  Market Event (bar 5min)                                 │    │
│  │       │                                                  │    │
│  │       ▼                                                  │    │
│  │  Signal Detection                                        │    │
│  │       │                                                  │    │
│  │       ▼                                                  │    │
│  │  Order Generation (Market/Limit)                         │    │
│  │       │                                                  │    │
│  │       ▼                                                  │    │
│  │  Fill Simulation (partial/full, queue)                   │    │
│  │       │                                                  │    │
│  │       ▼                                                  │    │
│  │  Position Update                                         │    │
│  │       │                                                  │    │
│  │       ▼                                                  │    │
│  │  Portfolio Revaluation                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Walk Forward     │  │ Monte Carlo      │                     │
│  │ Analysis         │  │ Simulation       │                     │
│  │ (Train/Val/Test) │  │ (Robustness)     │                     │
│  └──────────────────┘  └──────────────────┘                     │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Feature Selection│  │ Metrics          │                     │
│  │ & Robustness     │  │ (Enhanced)       │                     │
│  └──────────────────┘  └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                             │
│                                                                  │
│  Broker API → Bracket Orders → Idempotency → State Recovery    │
│  (Alpaca)                                                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OPERATIONS                                  │
│                                                                  │
│  Central CLI  │  Alerting  │  Health Check  │  Kill Switch      │
│  Pre-commit   │  CI/CD     │  Docker        │  Secrets Audit    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow

```
[External Data Sources]
    │
    ├── Yahoo Finance (EDA, prototipazione)
    ├── Alpaca Data API (backtest, paper)
    └── Polygon.io (premium, produzione)
    │
    ▼
[Data Provider Abstraction Layer]
    │ get_daily_data(ticker, start, end) → pd.DataFrame
    │ get_intraday_data(ticker, date, interval="5m") → pd.DataFrame
    │ get_pre_market_data(ticker, date) → dict
    │ get_historical_universe(index, date) → list[ticker]
    │
    ▼
[OHLCV Cache Pipeline]
    │ Parquet format, versioned by provider+date
    │
    ▼
[Data Quality Validation]
    │ Completeness, outliers, timezone, alignment
    │
    ▼
[Pre-Market Scanner]
    │ gap%, VIX, ADX, 200EMA, RVOL, regime → watchlist
    │
    ▼
[Strategy Engine]
    │ Signals → Risk → Portfolio → Orders
    │
    ▼
[Execution / Backtest]
    │ Broker API (live) or Broker Simulator (backtest)
    │
    ▼
[Monitoring & Logging]
    │ Trade log, equity curve, alerts
```

---

## 3. Event-Driven Backtest Flow (v5.0)

```
for each trading_day in backtest_period:
    │
    ├── [08:00 EST] Pre-Market Scan
    │   ├── DataProvider.get_pre_market_data()
    │   ├── Scanner.scan_premarket() → watchlist
    │   └── NewsFilter.filter_tickers()
    │
    ├── [09:30 EST] Market Open
    │   │
    │   for each 5min bar:
    │   │
    │   ├── MARKET EVENT: new bar (OHLCV)
    │   │   │
    │   │   ├── SignalGenerator.generate_signals() → signals
    │   │   │
    │   │   ├── for each signal:
    │   │   │   │
    │   │   │   ├── RiskManager.calculate_position_size()
    │   │   │   │
    │   │   │   ├── PortfolioManager.request_signal() → approved/rejected
    │   │   │   │
    │   │   │   ├── ORDER GENERATION
    │   │   │   │   ├── BracketOrder(symbol, qty, entry, tp, sl)
    │   │   │   │   └── OrderQueue.enqueue()
    │   │   │   │
    │   │   │   └── (continue to next signal)
    │   │   │
    │   │   ├── FILL SIMULATION
    │   │   │   ├── OrderQueue.process_bar(bar) → fills
    │   │   │   ├── FillSimulator.calculate_fill()
    │   │   │   └── SlippageModel.apply()
    │   │   │
    │   │   ├── POSITION UPDATE
    │   │   │   ├── PortfolioManager.open_position()
    │   │   │   ├── Check TP/SL/EOD
    │   │   │   └── PortfolioManager.close_position()
    │   │   │
    │   │   └── PORTFOLIO REVALUATION
    │   │       ├── Calculate P&L
    │   │       ├── Update equity curve
    │   │       └── Log trade
    │   │
    │   └── [15:50 EST] Forced Exit (EOD)
    │
    └── End of day
```

---

## 4. Execution Flow (Production)

```
[08:00 EST] Daily Startup
    │
    ├── Health Check (broker, API keys, disk, memory)
    ├── Kill Switch Check (drawdown, rejections, clock drift)
    ├── State Recovery (reconcile with broker)
    │
    ├── Pre-Market Scan
    │   ├── DataProvider (Alpaca/Polygon)
    │   ├── Scanner → watchlist
    │   └── PortfolioManager.rank_and_allocate()
    │
    ├── [09:30 EST] Market Open
    │   │
    │   for each signal:
    │   │
    │   ├── RiskManager.calculate_position_size()
    │   ├── KillSwitch.check_before_order()
    │   ├── Broker.submit_bracket_order()
    │   ├── Monitor fill status
    │   └── Log order
    │
    ├── Intraday Monitoring
    │   ├── Health Check (every 5 min)
    │   ├── Heartbeat (every 5 min)
    │   ├── Position monitoring (TP/SL)
    │   └── Kill Switch continuous check
    │
    ├── [15:50 EST] Forced Exit
    │   ├── Close all open positions
    │   └── Cancel all pending orders
    │
    └── [16:00 EST] Daily Shutdown
        ├── Trade log (append-only)
        ├── Equity curve update
        ├── Daily summary alert (Discord/Slack)
        ├── Data retention cleanup
        └── Checkpoint save
```

---

## 5. Key Architectural Improvements (v4.0 → v5.0)

| Component | v4.0 | v5.0 |
|---|---|---|
| **Data Source** | yfinance only | Data Provider Abstraction (Yahoo, Alpaca, Polygon) |
| **Universe** | S&P 500 corrente | Ricostruzione storica (ticker entrati/usciti/delisted) |
| **Backtest** | Loop giornaliero | Event-driven (Market Event → Signal → Order → Fill → Position → Portfolio) |
| **Validation** | Hold-out split 70/30 | Walk Forward Analysis (Train/Val/Test) + Monte Carlo |
| **Overfitting** | Grid search + sensitivity | Feature Selection + Plateau Detection + Deflated Sharpe |
| **Config** | settings.yaml singolo | Strategy Versioning (v1.yaml, v2.yaml) + experiment tracking |
| **Metrics** | ~30 metriche | Enhanced con Deflated Sharpe, PSR, benchmark-relative |

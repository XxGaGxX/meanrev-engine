# Fase 5 — Backtest Engine: risultati (DEV set 70%)

**Data:** 2026-07-11 · **Workflow:** TDD + ad-hoc verify + gate
**Moduli:** `src/backtest/engine.py`, `src/backtest/metrics.py`,
`src/strategy/filters.py`, `scripts/backtest_dev.py`

## Gate Fase 5 (ROADMAP_MVP.md)
- [x] Il backtest gira senza errori sul development set (70%) — 1094 trade, 80 ticker
- [x] Nessun trade ha entry <= signal (anti-look-ahead) — **0 violazioni**
      (verificato sia dentro `simulate_trade` che post-hoc nel report)

## Metodologia
- Dati: cache parquet daily (80 ticker S&P500, 2019-2024), split 70/30,
  backtest solo sul DEV (OOS-lock rispettato; Fase 6 userà il 30%).
- Pipeline: `signals.generate_entry_signal` → `risk.compute_position`
  (ATR stop 2x, partial TP 50%) → `filters.regime_allows_trade` (ADX>25)
  → `engine.simulate_trade` → `metrics.compute_metrics`.
- **Proxy giornaliero**: entry al close del giorno del segnale, exit al
  close del giorno successivo (i dati in cache sono daily, non 5min).
  Il gate (anti-look-ahead + metriche) è identico al backtest 5min reale
  (`scripts/backtest_proxy.py`); cambia solo la granularità della barra.

## Risultati DEV set
| Metrica | Valore |
|---------|--------|
| n_trades | 1094 |
| win_rate | 29.6% |
| profit_factor | 0.25 |
| total_pnl (netto costi Alpaca) | -21.958 |
| sharpe | -6.36 |
| max_drawdown | 87.8% |
| equity finale (cap 25000) | 3.042 |

## Interpretazione
**Il motore è onesto e il gate passa, ma la strategia sul DEV set NON è
profittevole.** PF 0.25 e Sharpe -6.36 indicano che i pochi loss sono
~4x i win (R:R strutturale <1, già diagnosticato in Fase 4). Il DD 88%
conferma che nei regime avversi (trend) la strategia distrugge capitale.

Questo è coerente con:
1. La ricerca giornaliera (Fase 2/ricerca): edge +0.6-4.8 bp/trade,
   SOTTO i costi di slippage reali (~2-3 bp).
2. Il backtest 5min (proxy): PF 0.10-0.14, azzerato dal regime filter in
   bull trend.

## Verdetto Fase 5
La **infrastruttura di backtest è valida e pronta** (engine, metriche,
anti-look-ahead lock, regime filter, split dev/OOS). La **strategia no**.
Per la roadmap, il checkpoint critico è la **Fase 6 (OOS)**: se anche l'OOS
è negativo → STOP, non costruire oltre. Se l'OOS fosse positivo (edge reale
nei dati non toccati) → si va a walk-forward.

**Raccomandazione:** prima della Fase 6, rivedere i filtri (Fase 3/design §2.4)
— il regime filter attuale taglia troppo poco sul daily proxy. Inoltre
l'R:R va portato >1 (TP esteso a prev_close + NxATR, non solo prev_close)
prima di fidarsi di qualsiasi split.
